"""Het terugkerende ritme van een rol, afgeleid uit de state die de skills zelf al bijhouden.

Geen nieuwe opslag: de wekelijkse scan schrijft zijn weekmarker en de wetscheck zijn
meetreeks — die lezen we terug. Zo kan de weergave nooit uit de pas lopen met wat er echt
gebeurde, want er is maar één bron.

De kern van dit bestand is de **overtijd-regel**. Een "laatste run: 3 juni" die er netjes uitziet
terwijl het nu juli is, wekt vertrouwen dat er niet is. Daarom rekent elk ritme zijn eigen
periode uit en zegt het expliciet wanneer het over tijd is.
"""
from __future__ import annotations

import datetime
import time

from nooch_village.checklists import period_key


def _periodes_geleden(laatste_sleutel: str, cadans: str, nu: float | None = None) -> int:
    """Hoeveel periodes zit de laatste run achter? 0 = deze periode, 1 = vorige, enz.

    Werkt op de periode-sleutel zelf (2026-W29, 2026-07), niet op de tijdstempel: dan telt
    hetzelfde ankerpunt als de idempotentie-poort van de skill."""
    if not laatste_sleutel:
        return 999
    nu = nu or time.time()
    moment = datetime.datetime.fromtimestamp(nu, datetime.timezone.utc)
    stap = datetime.timedelta(weeks=1) if cadans == "week" else datetime.timedelta(days=28)
    for n in range(0, 60):                               # ruim een jaar terugkijken
        if period_key(cadans, moment) == laatste_sleutel:
            return n
        moment -= stap
    return 999


def _stempel(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.datetime.fromtimestamp(ts).strftime("%-d %b %Y")


def _site_scan(data_dir: str) -> dict | None:
    from nooch_village.skills_impl.claims_site_scan import laatste_run
    run = laatste_run(data_dir)
    achter = _periodes_geleden(run.get("last_week", ""), "week")
    if run.get("nieuw"):
        uitkomst = (f"{run['nieuw']} nieuwe bevinding(en) → taken; "
                    f"{run.get('overgeslagen', 0)} liepen al")
    elif run:
        uitkomst = (f"{run.get('gescand', 0)} pagina's gescand, niets nieuws "
                    f"({run.get('overgeslagen', 0)} bekende bevindingen)")
    else:
        uitkomst = "draait bij de eerstvolgende dagpuls"
    if run.get("statussen"):
        uitkomst += f" · {run['statussen']} werklijst-status(sen) automatisch bijgewerkt"
    return {"naam": "Wekelijkse site-scan", "cadans": "week",
            "laatst": f"laatste run {_stempel(run.get('at'))}" if run.get("at") else "",
            "uitkomst": uitkomst,
            "overtijd": bool(run) and achter >= 2,
            "overtijd_tekst": f"{achter} weken niet gedraaid" if achter < 900 else "nooit gedraaid"}


def _wetscheck(data_dir: str) -> dict | None:
    from nooch_village.skills_impl.regulation_watch import lees_log
    rijen = [r for r in lees_log(data_dir) if r.get("soort") == "meting"]
    if not rijen:
        return {"naam": "Maandelijkse wetscheck", "cadans": "maand", "laatst": "",
                "uitkomst": "draait bij de eerstvolgende dagpuls",
                "overtijd": False, "overtijd_tekst": ""}
    laatste_maand = rijen[-1].get("maand", "")
    vandeze = [r for r in rijen if r.get("maand") == laatste_maand]
    fout = [r for r in vandeze if r.get("status") != "ok"]
    # "Gewijzigd" = deze maand een andere hash dan de vorige geslaagde meting van diezelfde bron.
    gewijzigd = 0
    for r in vandeze:
        if r.get("status") != "ok":
            continue
        eerder = [x for x in rijen
                  if x.get("url") == r.get("url") and x.get("maand") != laatste_maand
                  and x.get("status") == "ok"]
        if eerder and eerder[-1].get("hash") != r.get("hash"):
            gewijzigd += 1
    achter = _periodes_geleden(laatste_maand, "maand")
    if gewijzigd:
        uitkomst = f"{gewijzigd} bron(nen) gewijzigd — beoordeling staat als taak"
    else:
        uitkomst = f"{len(vandeze) - len(fout)} bron(nen) ongewijzigd"
    if fout:
        uitkomst += f" · {len(fout)} onbereikbaar"
    return {"naam": "Maandelijkse wetscheck", "cadans": "maand",
            "laatst": f"laatste run {_stempel(vandeze[-1].get('at'))}",
            "uitkomst": uitkomst,
            "overtijd": achter >= 2,
            "overtijd_tekst": f"{achter} maanden niet gedraaid" if achter < 900 else "nooit gedraaid"}


# Skill in het DNA van de rol → het ritme dat je op haar pagina ziet. Geen aparte registratie:
# wie de skill gegrant kreeg, laat het ritme zien.
_RITMES = {
    "claims_site_scan": _site_scan,
    "regulation_watch": _wetscheck,
}


def ritmes_voor(rol_id: str, record, data_dir: str) -> list[dict]:
    """De terugkerende ritmes van deze rol, in DNA-volgorde. Leeg = deze rol heeft er geen."""
    try:
        skills = list(getattr(getattr(record, "definition", None), "skills", []) or [])
    except Exception:
        return []
    uit = []
    for skill in skills:
        maker = _RITMES.get(skill)
        if maker is None:
            continue
        try:
            ritme = maker(data_dir)
        except Exception:
            continue                                     # weergave mag nooit een pagina breken
        if ritme:
            uit.append(ritme)
    return uit
