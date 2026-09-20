"""Pijplijn stap 6: de wachtrij leeghalen zonder de geschiedenis weg te gooien.

WAT HIER GEBEURT EN WAT NIET. De radar-wachtrij draagt 339 items met status `wacht`: signalen die
ooit zijn binnengekomen en waar nooit een mens ja of nee tegen heeft gezegd. Ze staan er sinds de
triage-keten verviel en de nieuwe stroom (de weekmemo) een andere weg neemt. Ze blijven BESTAAN;
alleen hun status gaat naar `gearchiveerd`, waardoor ze uit `all_pending()` vallen.

WAAROM NIET LEGEN, en dit is Stefans besluit uit het bouwplan: de goedgekeurde en afgewezen items
zijn het REFERENTIEMATERIAAL. `materiaal_memo` leest de goedgekeurde signalen, `reeds_bekend` en de
dedup in `RadarStore.add` kijken over álle statussen heen — een leeggemaakte bak betekent dat
hetzelfde nieuws morgen opnieuw als nieuw binnenkomt. Archiveren haalt de VRAAG weg, niet het
geheugen.

DEZELFDE DISCIPLINE ALS BIJ DE SPANNING-GESCHIEDENIS: eerst meten en tonen, dan pas schrijven, en
achteraf veld-voor-veld verifiëren dat er niets anders is geraakt dan de status. De sha256 van het
bestand vóór de wijziging staat in het verslag; dat is geen ceremonie maar de enige manier om
later hard te maken dát de rest onaangeroerd bleef. Een sha256 zegt alleen "er is iets veranderd" —
de veldvergelijking zegt WAT.

    python -m nooch_village.village radar_archief            # droge run, schrijft niets
    python -m nooch_village.village radar_archief --apply
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

log = logging.getLogger("village.radar_archief")

#: De status die we leeghalen, en de status die we ervoor in de plaats zetten.
VAN, NAAR = "wacht", "gearchiveerd"

#: De claims-taken die de oude uitgang (`claims_board.zet_op_bord`) heeft achtergelaten. Ze horen
#: bij dezelfde opruiming: het pad dat ze aanmaakte bestaat sinds stap 3 niet meer, dus wat er nog
#: open staat is werk waar niemand meer achter zit. `done` blijft staan — dat is afgerond werk.
CLAIMS_ORIGIN = "claims_fix"


def sha256(pad: str) -> str:
    """De vingerafdruk van een bestand vóór we het aanraken. Leeg als het niet bestaat."""
    if not os.path.exists(pad):
        return ""
    h = hashlib.sha256()
    with open(pad, "rb") as fh:
        for blok in iter(lambda: fh.read(65536), b""):
            h.update(blok)
    return h.hexdigest()


def _radar_items(data_dir: str) -> dict:
    """De ruwe items uit radar.json, buiten de store om — we willen de staat op schijf vergelijken
    en niet wat een store ervan maakt."""
    pad = os.path.join(data_dir, "radar.json")
    if not os.path.exists(pad):
        return {}
    with open(pad, encoding="utf-8") as fh:
        return (json.load(fh) or {}).get("items", {}) or {}


def plan(data_dir: str) -> dict:
    """Wat zou er gebeuren? Read-only. Geeft de tellingen én de id's die zouden wijzigen."""
    items = _radar_items(data_dir)
    per_status: dict = {}
    for it in items.values():
        st = str(it.get("status") or "?")
        per_status[st] = per_status.get(st, 0) + 1
    radar_ids = sorted(k for k, it in items.items() if str(it.get("status") or "") == VAN)

    projecten, pids = [], []
    pad = os.path.join(data_dir, "projects.json")
    if os.path.exists(pad):
        with open(pad, encoding="utf-8") as fh:
            projecten = list((json.load(fh) or {}).values())
    for p in projecten:
        if not isinstance(p, dict):
            continue
        if p.get("origin") != CLAIMS_ORIGIN or p.get("archived"):
            continue
        if str(p.get("status") or "") == "done":
            continue                                   # afgerond werk blijft afgerond werk
        pids.append(p["id"])
    return {"radar_per_status": per_status, "radar_ids": radar_ids,
            "project_ids": sorted(pids),
            "sha_radar": sha256(os.path.join(data_dir, "radar.json")),
            "sha_projects": sha256(pad)}


def verschil(voor: dict, na: dict) -> list[str]:
    """Wat is er tussen twee momentopnamen van radar.json ECHT veranderd, veld voor veld?

    Dit is de verificatie die een sha256 niet kan geven. Alles wat hier terugkomt en niet
    `<id>.status: wacht → gearchiveerd` is, is een onbedoelde wijziging."""
    uit = []
    for iid in sorted(set(voor) | set(na)):
        a, b = voor.get(iid), na.get(iid)
        if a is None:
            uit.append(f"{iid}: NIEUW item verschenen")
            continue
        if b is None:
            uit.append(f"{iid}: VERDWENEN")
            continue
        for sleutel in sorted(set(a) | set(b)):
            if a.get(sleutel) != b.get(sleutel):
                uit.append(f"{iid}.{sleutel}: {a.get(sleutel)!r} → {b.get(sleutel)!r}")
    return uit


def voer_uit(data_dir: str, *, apply: bool = False) -> dict:
    """De ronde. `apply=False` (default) schrijft niets en meet alleen."""
    from nooch_village.projects import ProjectLedger
    from nooch_village.radar_store import RadarStore

    v = plan(data_dir)
    verslag = {**v, "toegepast": bool(apply), "radar_gewijzigd": 0, "projecten_gewijzigd": 0,
               "mislukt": [], "onverwacht": []}
    if not apply:
        return verslag

    voor = _radar_items(data_dir)
    radar = RadarStore(os.path.join(data_dir, "radar.json"))
    for iid in v["radar_ids"]:
        if radar.set_status(iid, NAAR):
            verslag["radar_gewijzigd"] += 1
        else:
            verslag["mislukt"].append(f"radar {iid}")
    ledger = ProjectLedger(os.path.join(data_dir, "projects.json"))
    for pid in v["project_ids"]:
        if ledger.archive(pid):
            verslag["projecten_gewijzigd"] += 1
        else:
            verslag["mislukt"].append(f"project {pid}")

    # DE VERIFICATIE HOORT BIJ DE ACTIE, niet bij de goede bedoelingen van de aanroeper.
    verwacht = {f"{iid}.status: {VAN!r} → {NAAR!r}" for iid in v["radar_ids"]}
    verslag["onverwacht"] = [r for r in verschil(voor, _radar_items(data_dir))
                             if r not in verwacht]
    verslag["sha_radar_na"] = sha256(os.path.join(data_dir, "radar.json"))
    return verslag


def rapport(data_dir: str, *, apply: bool = False) -> dict:
    v = voer_uit(data_dir, apply=apply)
    print(f"radar.json  sha256 {v['sha_radar'][:16]}…")
    print(f"projects.json sha256 {v['sha_projects'][:16]}…")
    print("\nradar-items per status (vóór):")
    for st, n in sorted(v["radar_per_status"].items(), key=lambda t: -t[1]):
        print(f"  {n:5d}  {st}")
    print(f"\n{'gearchiveerd' if apply else 'zou archiveren'}: "
          f"{len(v['radar_ids'])} radar-item(s) · {len(v['project_ids'])} claims-project(en)")
    if apply:
        print(f"  daadwerkelijk gewijzigd: {v['radar_gewijzigd']} radar, "
              f"{v['projecten_gewijzigd']} projecten")
        print(f"  radar.json sha256 ná: {v.get('sha_radar_na','')[:16]}…")
        if v["mislukt"]:
            print(f"  MISLUKT: {v['mislukt'][:5]}")
        print(f"  onverwachte veldwijzigingen: {len(v['onverwacht'])}"
              + ("" if not v["onverwacht"] else f" → {v['onverwacht'][:5]}"))
    else:
        print("\nDROGE RUN — er is niets geschreven. Draai met --apply.")
    return v
