"""Wees-bestand-rapportage (READ-ONLY): bestanden in data/attachments/<pid>/ die GEEN bijbehorende
'file'-attachment-entry in projects.json hebben. Zulke wezen ontstonden door de lost-update-race op
projects.json (bestand weggeschreven, wall-entry overschreven) — nu gefixt, maar bestaande wezen blijven.

Dit script HERSTELT NIETS: het toont de lijst zodat een mens per geval beslist (re-linken via de UI,
laten staan, of verwijderen). Server-data-protocol geldt bij het uitvoeren tegen productie.

    python -m nooch_village.orphan_report [data_dir]
"""
from __future__ import annotations

import os
import sys
import time

from nooch_village.util import read_json


def find_orphans(data_dir: str):
    """→ (orphans, aantal_geregistreerde_files). Een orphan = een bestand op schijf onder attachments/
    waarvan het pad niet als 'file'-attachment 'stored' in enig project voorkomt."""
    projects = read_json(os.path.join(data_dir, "projects.json"), {})
    registered = set()
    for p in projects.values():
        for a in (p.get("attachments") or []):
            if a.get("kind") == "file" and a.get("stored"):
                registered.add(os.path.normpath(a["stored"]))
    orphans = []
    att_root = os.path.join(data_dir, "attachments")
    for dirpath, _dirs, files in os.walk(att_root):
        for fn in files:
            full = os.path.join(dirpath, fn)
            rel = os.path.normpath(os.path.relpath(full, data_dir))     # attachments/<pid>/<file>
            if rel not in registered:
                stt = os.stat(full)
                orphans.append({"pid": os.path.basename(dirpath), "rel": rel, "name": fn,
                                "size": stt.st_size, "mtime": stt.st_mtime})
    orphans.sort(key=lambda o: o["mtime"])
    return orphans, len(registered)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    data_dir = argv[0] if argv else os.path.join(os.getcwd(), "data")
    if not os.path.isdir(os.path.join(data_dir, "attachments")):
        print(f"Geen attachments-map in {data_dir!r} — niets te rapporteren.")
        return 0
    orphans, n_reg = find_orphans(data_dir)
    print(f"Wees-bestand-rapport voor {data_dir}")
    print(f"  {n_reg} geregistreerde file-bijlagen in projects.json | {len(orphans)} wees-bestanden op schijf\n")
    if not orphans:
        print("  Geen wezen — elk bestand op schijf heeft een wall-entry. ✓")
        return 0
    for o in orphans:
        dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(o["mtime"]))
        print(f"  {dt}  {o['size']:>9} B  pid={o['pid']}  {o['name']}")
    print("\n  READ-ONLY: niets is gewijzigd. Beslis per geval (re-linken via de UI / laten staan / verwijderen).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
