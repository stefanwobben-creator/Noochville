"""De vastgelopen projectvoorstellen opruimen (21 september 2026, eenmalig).

WAT ER LAG. Op productie stonden 10 projecten met status `proposed`, de oudste 43 dagen. Ze waren
gemaakt door de voorstel-generator die elke dagpuls draaide, en de enige plek waar een mens ze kon
aannemen of afwijzen — de Founder Flow — is in de opruiming van fase 1-9 verwijderd. Ze konden dus
niet vooruit en niet weg: werk dat wacht op een oordeel dat niemand kan geven.

De lus zelf is in dezelfde beurt opgeheven (besluit Stefan). Dit ruimt op wat hij heeft
achtergelaten.

ARCHIVEREN, NIET WISSEN, en om dezelfde reden als bij de radar-items: het zijn echte voorstellen
met een herkomst en een tekst, en `archived=True` haalt ze uit élke lijst zonder de geschiedenis op
te eten. `reject_proposal` deed vroeger wél een harde `del` — precies wat hier niet hoort.

DE DISCIPLINE IS DIE VAN PIJPLIJNSTAP 6: vingerafdruk vooraf, droge run standaard, en achteraf een
veldvergelijking die zegt WAT er is veranderd. Een sha256 zegt alleen dát er iets veranderde.

    python -m nooch_village.village voorstel_opruiming            # droge run
    python -m nooch_village.village voorstel_opruiming --apply
"""
from __future__ import annotations

import json
import logging
import os

from nooch_village.radar_archief import sha256, verschil

log = logging.getLogger("village.voorstel_opruiming")

STATUS = "proposed"


def _projecten(data_dir: str) -> dict:
    pad = os.path.join(data_dir, "projects.json")
    if not os.path.exists(pad):
        return {}
    with open(pad, encoding="utf-8") as fh:
        return json.load(fh) or {}


def plan(data_dir: str) -> dict:
    """Wat zou er gebeuren? Read-only."""
    alle = _projecten(data_dir)
    open_voorstellen = sorted(
        (p for p in alle.values()
         if isinstance(p, dict) and p.get("status") == STATUS and not p.get("archived")),
        key=lambda p: p.get("created_at", 0))
    return {"totaal": len(alle), "ids": [p["id"] for p in open_voorstellen],
            "rijen": [{"id": p["id"], "owner": p.get("owner", ""),
                       "titel": str(p.get("scope") or "")[:70],
                       "created_at": p.get("created_at", 0)} for p in open_voorstellen],
            "sha": sha256(os.path.join(data_dir, "projects.json"))}


def voer_uit(data_dir: str, *, apply: bool = False) -> dict:
    from nooch_village.projects import ProjectLedger

    v = plan(data_dir)
    verslag = {**v, "toegepast": bool(apply), "gewijzigd": 0, "mislukt": [], "onverwacht": []}
    if not apply:
        return verslag

    voor = _projecten(data_dir)
    led = ProjectLedger(os.path.join(data_dir, "projects.json"))
    for pid in v["ids"]:
        if led.archive(pid):
            verslag["gewijzigd"] += 1
        else:
            verslag["mislukt"].append(pid)

    # `archive()` zet `archived` én raakt `updated_at` aan (`_touch`) — beide verwacht. Alles wat
    # daarbuiten verandert, hoort hier op te vallen.
    verwacht = {f"{pid}.{veld}" for pid in v["ids"] for veld in ("archived", "updated_at")}
    verslag["onverwacht"] = [r for r in verschil(voor, _projecten(data_dir))
                             if r.split(":")[0] not in verwacht]
    verslag["sha_na"] = sha256(os.path.join(data_dir, "projects.json"))
    return verslag


def rapport(data_dir: str, *, apply: bool = False) -> dict:
    v = voer_uit(data_dir, apply=apply)
    print(f"projects.json sha256 {v['sha'][:16]}… ({v['totaal']} projecten)")
    print(f"\n{'gearchiveerd' if apply else 'zou archiveren'}: {len(v['ids'])} vastgelopen "
          f"voorstel(len)")
    import time
    nu = time.time()
    for r in v["rijen"]:
        dagen = int((nu - float(r["created_at"] or nu)) / 86400)
        print(f"   {dagen:4d}d  {r['owner'].split('__')[-1][:22]:22s} {r['titel']}")
    if apply:
        print(f"\n  daadwerkelijk gewijzigd: {v['gewijzigd']}"
              + (f" · MISLUKT: {v['mislukt']}" if v["mislukt"] else ""))
        print(f"  sha256 ná: {v.get('sha_na','')[:16]}…")
        print(f"  onverwachte veldwijzigingen: {len(v['onverwacht'])}"
              + ("" if not v["onverwacht"] else f" → {v['onverwacht'][:5]}"))
    else:
        print("\nDROGE RUN — er is niets geschreven. Draai met --apply.")
    return v
