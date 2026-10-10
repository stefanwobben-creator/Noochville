"""De Critical Numbers van het kwartaal als tegels op de kring (10 oktober 2026).

ÉÉN PLEK VOOR DOELEN EN GRENZEN: `config/critical_numbers.json`. Geen getal in de code; wie een doel
of grens wil verschuiven, past dat bestand aan en draait `village cn_zaad --apply` opnieuw.

Een nummer wordt een tegel (`MetricStore.add_tile`) met zijn niveau, doel en oranje-drempel
(`set_tile_grens`) en het DOMEIN van zijn eigenaar (`eigenaar_domein`) — zodat de eigenaar meeverhuist
als governance het domein verplaatst. De tegel draagt ook de `cn`-sleutel van het nummer: daaraan
herkent een volgende run hem terug.

IDEMPOTENT: een tegel met dezelfde `cn`-sleutel op dezelfde kring wordt bijgewerkt, niet verdubbeld.
Dry-run tenzij `apply`. Een nummer dat nog niet gezaaid mag worden (`"zaai": false`, bijv. CN1 zolang
de startdatum van Batch 4 niet vastligt), wordt overgeslagen en zo gemeld.
"""
from __future__ import annotations

import json
import os

_PAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config",
                    "critical_numbers.json")


def laad(pad: str = "") -> dict:
    """Het seed-bestand. Fail-closed: zonder bestand of zonder nummers is er niets te zaaien."""
    with open(pad or _PAD, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d.get("nummers"), list) or not d.get("kring"):
        raise ValueError("critical_numbers.json mist 'kring' of 'nummers'")
    return d


def _kpi(metrics, kring: str, n: dict) -> dict:
    """Een nummer met `"soort": "kpi"` is een HANDMATIGE meting (cash): eerst de KPI zelf, met zijn
    `cn`-sleutel en zicht-groep, dan de tegel die hem toont. Bestaat hij al, dan dezelfde KPI."""
    it = metrics.by_cn(n["sleutel"])
    if it is None:
        it = metrics.add_kpi(kring, n.get("naam") or n["titel"], n.get("eenheid", ""),
                             direction=n.get("richting", ""), definition=n.get("definitie", ""))
    metrics.set_item_extra(it["id"], cn=n["sleutel"], zicht=n.get("zicht", ""))
    return it


def zaai(metrics, cfg: dict, *, apply: bool = False) -> list[dict]:
    """[{sleutel, titel, actie}] — actie ∈ add | update | ongewijzigd | overgeslagen (reden)."""
    kring = cfg["kring"]
    rapport = []
    for n in cfg["nummers"]:
        if n.get("zaai") is False:
            rapport.append({"sleutel": n["sleutel"], "titel": n["titel"],
                            "actie": f"overgeslagen: {n.get('reden') or 'zaai=false'}"})
            continue
        lijn = None
        if n.get("lijn"):
            from nooch_village.metrics import maak_lijn
            lijn = maak_lijn(**n["lijn"])
            if lijn is None:
                rapport.append({"sleutel": n["sleutel"], "titel": n["titel"],
                                "actie": "fout: ongeldige lijn in het seed-bestand"})
                continue
        bestaand = next((t for t in metrics.tiles_of(kring) if t.get("cn") == n["sleutel"]), None)
        if lijn is not None and bestaand is not None and bestaand.get("lijn_handmatig") and bestaand.get("lijn"):
            # IN DE UI VERZET (CN1: de startdatum van de batch) wint van de voorlopige seed-waarde.
            lijn = {**lijn, "van": bestaand["lijn"]["van"]}
        gewenst = {"niveau": n.get("niveau", ""), "target": n.get("target"), "oranje": n.get("oranje"),
                   "eigenaar_domein": n.get("eigenaar_domein", ""),
                   "eigenaar_rol": n.get("eigenaar_rol", ""), "zicht": n.get("zicht", ""),
                   "lijn": lijn}
        if bestaand is None:
            actie = "add"
        elif all(bestaand.get(k) == (None if v is None else float(v)) if k in ("target", "oranje")
                 else bestaand.get(k) == v if k == "lijn"
                 else (bestaand.get(k) or "") == (v or "") for k, v in gewenst.items()):
            actie = "ongewijzigd"
        else:
            actie = "update"
        rapport.append({"sleutel": n["sleutel"], "titel": n["titel"], "actie": actie})
        if not apply or actie == "ongewijzigd":
            continue
        extra = {k: gewenst[k] for k in ("eigenaar_domein", "eigenaar_rol", "zicht", "lijn")}
        if bestaand is None:
            source = f"kpi:{_kpi(metrics, kring, n)['id']}" if n.get("soort") == "kpi" else n["source"]
            bestaand = metrics.add_tile(kring, source, n["measure"], n.get("dim", "totaal"),
                                        n.get("form", "getal"), extra={"cn": n["sleutel"], **extra})
        else:
            if n.get("soort") == "kpi":
                _kpi(metrics, kring, n)
            metrics.set_tile_extra(kring, bestaand["id"], **extra)
        fout = metrics.set_tile_grens(kring, bestaand["id"], n.get("niveau", ""), n.get("target"),
                                      n.get("oranje"))
        if fout:
            rapport[-1]["actie"] = f"fout: {fout}"
    return rapport


def rapport_tekst(rapport: list[dict], cfg: dict) -> str:
    kop = f"{cfg.get('kwartaal', {}).get('naam', '')} · kring {cfg['kring']}"
    return "\n".join([kop] + [f"  {r['actie']:<12} {r['sleutel']}  ({r['titel']})" for r in rapport])
