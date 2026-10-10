"""CO2e per paar uit /bom — een productmetric naast de dorps-CO2 van `co2.py` (10 oktober 2026).

Wat het IS: de som over de componenten van gewicht × `co2e_per_kg` van de materiaalpagina — precies de
CO2e-tegel van `/bom`, uit `bom_reken.bereken`. Alleen de MATERIALEN; geen productie, transport of
einde-leven. Daarom een eigen definitie, en niet de LCA-definitie "CO2 per paar" (2030calculator).

NOOIT STILZWIJGEND NUL (zelfde principe als `co2.py`). Een component zonder factor of zonder gewicht
telt niet mee, en dan is het getal een ONDERGRENS — zo gelabeld, met welke materialen nog geen factor
hebben. Telt er helemaal niets mee, dan is er geen getal: `kg=None`, geen 0.

DE SAMENSTELLING ALS MARKERING, GEEN REEKSBREUK. Een `break` in de catalogus betekent: we meten op een
andere manier. Een andere stuklijst is geen andere meting, het is een ander PRODUCT — en dat is precies
wat deze reeks moet laten zien. Dus de reeks loopt door, en elk punt draagt de vingerafdruk van de
samenstelling waarop hij rekende (`samenstelling`) plus de volledigheid (`n`/`m`). Waar de vingerafdruk
wisselt, veranderde het product; waar alleen `n` stijgt, veranderde de dekking.

Puur: rekent op de uitkomst van `bom_reken.bereken`, leest niets van schijf.
"""
from __future__ import annotations

import hashlib
import json

from nooch_village import bom_reken


def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def co2_per_paar(uit: dict) -> dict:
    """{kg, ondergrens, materialen, met_factor, zonder_factor, componenten, met_gewicht,
    zonder_gewicht, samenstelling} voor één stuklijst (de uitkomst van `bom_reken.bereken`).

    `materialen` = het aantal verschillende materialen; een materiaal "heeft een factor" als zijn
    pagina precies één `co2e_per_kg` draagt (dezelfde regel als `bom_reken`). `kg` = de som van wat
    meetelt, of None als niets meetelt."""
    rijen = uit.get("rijen", [])
    mats: dict[str, dict] = {}
    for r in rijen:
        k = _norm(r["materiaal"])
        if k and k not in mats:
            factor, _reden = bom_reken._factor(r.get("mat"), "co2e_per_kg")
            mats[k] = {"naam": r["materiaal"], "factor": factor}
    bijdragen = [r["bijdrage"].get("co2e") for r in rijen]
    telt = [b for b in bijdragen if b is not None]
    zonder_gewicht = [r["part"] for r in rijen if r.get("gram_eigen") is None]
    zonder_factor = [m["naam"] for m in mats.values() if m["factor"] is None]
    vingerafdruk = json.dumps(sorted((_norm(r["part"]), _norm(r["materiaal"]), r.get("gram_eigen"))
                                     for r in rijen), default=str)
    return {
        "kg": round(sum(telt), 4) if telt else None,
        "ondergrens": len(telt) < len(rijen),
        "materialen": len(mats),
        "met_factor": len(mats) - len(zonder_factor),
        "zonder_factor": zonder_factor,
        "componenten": len(rijen),
        "met_gewicht": len(rijen) - len(zonder_gewicht),
        "zonder_gewicht": zonder_gewicht,
        "samenstelling": hashlib.sha1(vingerafdruk.encode("utf-8")).hexdigest()[:10],
    }


def tekst(res: dict) -> str:
    """De volledigheid in één zin, Engels (systeemoutput). Altijd, ook als het getal compleet is."""
    if res["kg"] is None:
        kop = "No CO2e per pair yet"
    else:
        kop = (f"{res['kg']:.2f} kg CO2e per pair"
               + (" (lower bound)" if res["ondergrens"] else ""))
    delen = [f"based on {res['met_factor']} of {res['materialen']} materials"]
    if res["zonder_factor"]:
        delen.append(f"{len(res['zonder_factor'])} have no factor yet: "
                     + ", ".join(res["zonder_factor"]))
    if res["zonder_gewicht"]:
        delen.append(f"{len(res['zonder_gewicht'])} of {res['componenten']} components have no "
                     f"weight yet")
    return f"{kop}, " + "; ".join(delen) + ". Materials only, not a full LCA."
