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
import time

from nooch_village import claims_board, claims_db, claims_verify, safe_fetch
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


def markeer_week(data_dir: str, week: str, uitkomst: dict | None = None) -> None:
    """Zet de weekmarker. Naast `last_week` gaat de uitkomst mee, zodat de rolpagina kan tonen
    wanneer de scan draaide en wat hij vond — zonder een tweede opslagplek."""
    from nooch_village.util import atomic_write_json
    try:
        atomic_write_json(os.path.join(data_dir, MARKER),
                          {"last_week": week, "at": time.time(), **(uitkomst or {})})
    except Exception:
        pass                      # markeren mislukt = hooguit een dubbele scan, nooit een crash


def laatste_run(data_dir: str) -> dict:
    """Wat de rolpagina nodig heeft: de laatste weekmarker, of leeg als er nog niets draaide."""
    import json
    try:
        with open(os.path.join(data_dir, MARKER), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def scan_paginas(db: dict) -> list[dict]:
    """De vaste pagina-set uit de claims-database (compliance beheert die lijst, niet de code)."""
    return [p for p in (db.get("meta") or {}).get("scan_paginas", [])
            if isinstance(p, dict) and p.get("url")]


def verzamel(paginas: list[dict], db: dict, _fetch=None) -> tuple[list[dict], list[str], dict]:
    """Scan elke pagina en geef (bevindingen, fouten, paginateksten) terug. Elke bevinding draagt
    de pagina waar hij vandaan komt, zodat de taak een vindplaats heeft; de teksten gaan mee
    zodat de werklijst-verificatie tegen dezelfde waarneming kan toetsen."""
    bevindingen, fouten, teksten = [], [], {}
    for pagina in paginas:
        try:
            opgehaald = safe_fetch.haal_tekst(pagina["url"], _fetch=_fetch)
        except (safe_fetch.FetchGeweigerd, safe_fetch.FetchMislukt) as e:
            fouten.append(f"{pagina.get('label', pagina['url'])}: {e}")
            continue
        teksten[pagina.get("label", pagina["url"])] = opgehaald["tekst"]
        uitslag = claims_db.check_tekst(opgehaald["tekst"], db)
        for b in uitslag["bevindingen"]:
            if b["stoplicht"] == "green":
                continue
            bevindingen.append({**b, "pagina": pagina.get("label", ""), "url": pagina["url"]})
    return bevindingen, fouten, teksten


def _wie_fixte(ledger, nr: int) -> str | None:
    """De rol die aan dit werklijst-item gewerkt heeft — die moet een regressie als eerste weten."""
    try:
        for p in ledger.all():
            if p.get("origin") == claims_board.ORIGIN and f"#{nr}" in str(p.get("description", "")):
                return p.get("owner")
    except Exception:
        pass
    return None


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

    def _verifieer_werklijst(self, context, db: dict, paginateksten: dict) -> list[dict]:
        """Toets de werklijst tegen wat we net zagen en sla de uitkomst op.

        Dit is de enige plek waar een skill de claims-database schrijft, en alleen het
        status-veld: termen, herformuleringen en landenregels blijven compliance-domein.
        Elke automatische wijziging krijgt `status_bron: auto`, zodat een mens altijd kan zien
        wie wat vond."""
        voorstellen = claims_verify.verifieer(db, paginateksten)
        if not voorstellen:
            return []
        try:
            levend = claims_db.load()                    # verse kopie: niet op onze scan-dict schrijven
        except claims_db.ClaimsDbError:
            return []
        gewijzigd = claims_verify.pas_toe(levend, voorstellen)
        if not gewijzigd:
            return []
        claims_db.bump_versie(levend)
        claims_db.save(levend)
        claims_verify.pas_toe(db, voorstellen)           # de scan-dict meetrekken
        for v in gewijzigd:
            if v["naar"] != claims_db.AUTO_REGRESSIE:
                continue
            # Een regressie gaat naar wie hem gefixt had én altijd naar compliance.
            tekst = f"↩️ Werklijst #{v['nr']} staat weer op de site — {v['reden']}"
            eigenaar = _wie_fixte(context.projects, v["nr"])
            if eigenaar:
                claims_board.bericht_aan_rol(context, eigenaar, tekst)
            claims_board.bericht_aan_rol(context, "compliance", tekst)
        return gewijzigd

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

        bevindingen, fouten, paginateksten = verzamel(paginas, db, _fetch=payload.get("_fetch"))
        if len(fouten) == len(paginas):
            # Alle pagina's onbereikbaar: dat is geen 'schone site', dat is een kapotte scan.
            return {"ok": False, "week": week, "gescand": 0,
                    "escalate": {"reason": "geen enkele pagina kon worden opgehaald: "
                                           + "; ".join(fouten[:3])}}

        if getattr(context, "projects", None) is None:
            return {"ok": False, "week": week,
                    "escalate": {"reason": "geen projectenbord beschikbaar in de context"}}
        verslag = claims_board.zet_op_bord(
            context, db, bevindingen,
            bron=f"wekelijkse site-scan {week}", rol_voor=_rol_voor, trigger="role")
        statussen = self._verifieer_werklijst(context, db, paginateksten)

        markeer_week(data_dir, week, {"nieuw": len(verslag["aangemaakt"]),
                                      "overgeslagen": verslag["overgeslagen"],
                                      "gescand": len(paginas) - len(fouten),
                                      "statussen": len(statussen)})
        # `headsup` is wat de mens moet zien; de generieke pulslaag stuurt het door naar de
        # founder. Alleen bij ROOD — oranje is werk voor de rol, geen alarm voor de founder.
        regressies = [s for s in statussen if s["naar"] == claims_db.AUTO_REGRESSIE]
        headsup = None
        if regressies:
            # Een teruggekeerde claim weegt zwaarder dan een nieuwe: iemand dacht dat dit af was.
            headsup = (f"↩️ Claim-regressie: {len(regressies)} eerder opgeloste claim(s) staan "
                       f"weer op de site (#{', #'.join(str(r['nr']) for r in regressies)})")
        elif verslag["rood"]:
            headsup = (f"🔴 Claim-scan: {verslag['rood']} nieuwe verboden claim(s) op nooch.earth "
                       f"({len(verslag['aangemaakt'])} taak/taken op het bord)")
        return {"ok": True, "week": week, "skipped": False, "headsup": headsup,
                "statussen": statussen,
                "gescand": len(paginas) - len(fouten), "fouten": fouten,
                "nieuw": len(verslag["aangemaakt"]), "aangemaakt": verslag["aangemaakt"],
                "overgeslagen": verslag["overgeslagen"], "rood": verslag["rood"],
                "escalate": None}
