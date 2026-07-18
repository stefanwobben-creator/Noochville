"""claims_site_scan — de wekelijkse zelf-scan van nooch.earth door compliance.

Verschil met `claims_check`: die skill is puur lokaal en toetst tekst die je hem geeft. Deze
skill haalt zélf de vaste pagina-set op (server-side, via `safe_fetch` met SSRF-guardrail) en
levert alleen NIEUWE bevindingen — wat al in de werklijst staat of al als taak loopt, telt niet.

Drie regels:
1. **Idempotent per week.** Een tweede puls in dezelfde ISO-week doet niets. De weekmarker
   wordt pas ná een geslaagde run gezet, zodat een mislukte run volgende puls opnieuw mag.
2. **Fail-closed.** Alle pagina's onbereikbaar of de database corrupt → `escalate`, nooit een
   stille nul. "Geen bevindingen" moet betekenen dat er niets was, niet dat er niets werkte.
3. **Geen bord-ruis.** Niets nieuws → één logregel, geen taken, geen heads-up.
"""
from __future__ import annotations

import os

from nooch_village import claims_board, claims_db, safe_fetch
from nooch_village.checklists import period_key
from nooch_village.skills import Skill

MARKER = "claims_site_scan_last_week.json"


def _rol_voor(categorie: str) -> str:
    """De rol-routing van de checker, hier hergebruikt zodat een wekelijkse bevinding bij
    dezelfde rol landt als een handmatige."""
    from nooch_village.views.claims import rol_voor
    return rol_voor(categorie)


def week_gedaan(data_dir: str, week: str) -> bool:
    """Is deze ISO-week al gescand?"""
    import json
    try:
        with open(os.path.join(data_dir, MARKER), encoding="utf-8") as f:
            return json.load(f).get("last_week") == week
    except Exception:
        return False


def markeer_week(data_dir: str, week: str) -> None:
    from nooch_village.util import atomic_write_json
    try:
        atomic_write_json(os.path.join(data_dir, MARKER), {"last_week": week})
    except Exception:
        pass                      # markeren mislukt = hooguit een dubbele scan, nooit een crash


def scan_paginas(db: dict) -> list[dict]:
    """De vaste pagina-set uit de claims-database (compliance beheert die lijst, niet de code)."""
    return [p for p in (db.get("meta") or {}).get("scan_paginas", [])
            if isinstance(p, dict) and p.get("url")]


def verzamel(paginas: list[dict], db: dict, _fetch=None) -> tuple[list[dict], list[str]]:
    """Scan elke pagina en geef (bevindingen, fouten) terug. Elke bevinding draagt de pagina
    waar hij vandaan komt, zodat de taak een vindplaats heeft."""
    bevindingen, fouten = [], []
    for pagina in paginas:
        try:
            opgehaald = safe_fetch.haal_tekst(pagina["url"], _fetch=_fetch)
        except (safe_fetch.FetchGeweigerd, safe_fetch.FetchMislukt) as e:
            fouten.append(f"{pagina.get('label', pagina['url'])}: {e}")
            continue
        uitslag = claims_db.check_tekst(opgehaald["tekst"], db)
        for b in uitslag["bevindingen"]:
            if b["stoplicht"] == "green":
                continue
            bevindingen.append({**b, "pagina": pagina.get("label", ""), "url": pagina["url"]})
    return bevindingen, fouten


class ClaimsSiteScanSkill(Skill):
    name = "claims_site_scan"
    cost = "free"
    side_effect_free = False           # maakt taken aan op het bord
    required_env = ()
    description = ("Scant de vaste pagina-set van nooch.earth tegen de claims-database en zet "
                   "alleen NIEUWE rode/oranje bevindingen als taak bij de juiste rol. Eén keer "
                   "per ISO-week; wat al in de werklijst of op het bord staat wordt overgeslagen.")
    input_schema = "geen (optioneel: force: bool om de week-gate over te slaan)"
    output_schema = "ok, week, skipped, gescand, nieuw, aangemaakt[], overgeslagen, escalate"

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        data_dir = getattr(context, "data_dir", ".")
        week = period_key("week")
        if not payload.get("force") and week_gedaan(data_dir, week):
            return {"ok": True, "week": week, "skipped": True, "reden": "deze week al gescand"}

        try:
            db = claims_db.load()
        except claims_db.ClaimsDbError as e:
            return {"ok": False, "week": week, "escalate": {"reason": f"claims-database onleesbaar: {e}"}}

        paginas = scan_paginas(db)
        if not paginas:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen scan-paginas in de claims-database (meta.scan_paginas)"}}

        bevindingen, fouten = verzamel(paginas, db, _fetch=payload.get("_fetch"))
        if len(fouten) == len(paginas):
            # Alle pagina's onbereikbaar: dat is geen 'schone site', dat is een kapotte scan.
            return {"ok": False, "week": week, "gescand": 0,
                    "escalate": {"reason": "geen enkele pagina kon worden opgehaald: "
                                           + "; ".join(fouten[:3])}}

        ledger = getattr(context, "projects", None)
        if ledger is None:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen projectenbord beschikbaar in de context"}}
        records = getattr(context, "records", None)
        verslag = claims_board.zet_op_bord(
            ledger, records, db, bevindingen,
            bron=f"wekelijkse site-scan {week}", rol_voor=_rol_voor, trigger="role")

        markeer_week(data_dir, week)
        # `headsup` is wat de mens moet zien; de generieke pulslaag stuurt het door naar de
        # founder. Alleen bij ROOD — oranje is werk voor de rol, geen alarm voor de founder.
        headsup = (f"🔴 Claim-scan: {verslag['rood']} nieuwe verboden claim(s) op nooch.earth "
                   f"({len(verslag['aangemaakt'])} taak/taken op het bord)"
                   if verslag["rood"] else None)
        return {"ok": True, "week": week, "skipped": False, "headsup": headsup,
                "gescand": len(paginas) - len(fouten), "fouten": fouten,
                "nieuw": len(verslag["aangemaakt"]), "aangemaakt": verslag["aangemaakt"],
                "overgeslagen": verslag["overgeslagen"], "rood": verslag["rood"],
                "escalate": None}
