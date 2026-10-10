#!/usr/bin/env python3
"""Herstel-toets: is deze back-up van `data/` terug te zetten? (10 oktober 2026)

Een back-up waarvan niemand weet of hij werkt, is geen back-up. Deze toets doet wat een restore
zou doen, op een KOPIE — de snapshot zelf blijft onaangeroerd:

1. elk `.json`-bestand moet te lezen zijn (een half geschreven bestand valt hier op);
2. elke regel van elk `.jsonl`-bestand moet te lezen zijn, behalve hoogstens de laatste (een
   append die net liep toen rsync las — dat is geen beschadiging, dat is een moment);
3. de cockpit moet de stores uit de kopie kunnen openen (`_Stores`), en de kern mag niet leeg zijn:
   governance-records en mensen.

Gebruik:  python scripts/backup_herstel_toets.py <pad naar een snapshot/data>
Exit 0 = te herstellen; anders 1, met wat er mis is.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


def _finance_bijlagen(data: str) -> list[str]:
    """Elke bijlage in het kostenregister (Finance) moet er zijn, met de sha256 uit het register.
    Een back-up met een kapotte of ontbrekende factuur is voor de borging geen back-up. Leest alleen
    `finance/costs.jsonl` en de bestanden; geen finance-code nodig. Zonder register: niets te doen."""
    import hashlib
    pad = os.path.join(data, "finance", "costs.jsonl")
    if not os.path.exists(pad):
        return []
    fouten, n = [], 0
    with open(pad, encoding="utf-8") as f:
        for regel in f:
            try:
                r = json.loads(regel)
            except ValueError:
                continue
            b = r.get("attachment") or {}
            if not b.get("path"):
                continue
            n += 1
            vol = os.path.join(data, b["path"])
            if not os.path.isfile(vol):
                fouten.append(f"finance-bijlage ontbreekt: {b['path']}")
                continue
            with open(vol, "rb") as h:
                if hashlib.sha256(h.read()).hexdigest() != b.get("sha256"):
                    fouten.append(f"finance-bijlage klopt niet met zijn sha256: {b['path']}")
    print(f"{n} finance-bijlage(n) nagelopen")
    return fouten


def toets(data: str) -> list[str]:
    """De fouten in deze data-map; leeg = te herstellen."""
    fouten: list[str] = []
    if not os.path.isdir(data):
        return [f"geen map: {data}"]
    n_json = n_jsonl = 0
    for root, _dirs, files in os.walk(data):
        for f in files:
            pad = os.path.join(root, f)
            rel = os.path.relpath(pad, data)
            if f.endswith(".json"):
                n_json += 1
                try:
                    with open(pad, encoding="utf-8") as h:
                        json.load(h)
                except (ValueError, UnicodeDecodeError) as e:
                    fouten.append(f"{rel}: geen geldige JSON ({e})")
            elif f.endswith(".jsonl"):
                n_jsonl += 1
                with open(pad, encoding="utf-8", errors="replace") as h:
                    regels = [r for r in h.read().split("\n") if r.strip()]
                for i, r in enumerate(regels):
                    try:
                        json.loads(r)
                    except ValueError:
                        if i < len(regels) - 1:                    # alleen de laatste mag half zijn
                            fouten.append(f"{rel}: regel {i + 1} is geen JSON")
                            break
    print(f"{n_json} json- en {n_jsonl} jsonl-bestanden gelezen")
    fouten += _finance_bijlagen(data)
    # Herstel op een kopie: de stores openen zoals de cockpit dat doet.
    with tempfile.TemporaryDirectory() as tmp:
        kopie = os.path.join(tmp, "data")
        shutil.copytree(data, kopie, symlinks=True)
        try:
            from nooch_village.cockpit2 import _Stores
            st = _Stores(kopie)
            n_rec, n_mens = len(st.records.all()), len(st.people.all())
            print(f"stores geopend: {n_rec} records, {n_mens} mensen")
            if not n_rec:
                fouten.append("governance-records zijn leeg")
            if not n_mens:
                fouten.append("people is leeg")
        except Exception as e:                                   # elke fout bij openen is een fout
            fouten.append(f"stores openen faalde: {type(e).__name__}: {e}")
    return fouten


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    fouten = toets(sys.argv[1])
    for f in fouten:
        print("FOUT:", f)
    print("te herstellen" if not fouten else f"{len(fouten)} fout(en)")
    return 0 if not fouten else 1


if __name__ == "__main__":
    sys.exit(main())
