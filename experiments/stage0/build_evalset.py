#!/usr/bin/env python3
"""Bouw de Stage-0 eval-set uit de LIVE radar: de menselijke grondwaarheid.

`goedgekeurd` = keep (1), `afgewezen` = dismiss (0). Alleen die twee statussen tellen: `wacht` is
nog niet beoordeeld en `samengevoegd` is een curatie-actie, geen oordeel over bewaren-of-weggooien.

Draai dit OP de server (daar staat de radar), of geef een pad mee:
    RADAR_JSON=/opt/noochville/data/radar.json python3 experiments/stage0/build_evalset.py

De uitvoer (`evalset.jsonl`) is PRODUCTIEDATA — signaalteksten en rationales van echte curatie.
Hij staat daarom in .gitignore en hoort nooit in de repo. De eval-set is reproduceerbaar: dit
script draait 'm zo weer opnieuw uit de radar van dat moment.
"""
from __future__ import annotations

import glob
import json
import os

LABEL = {"goedgekeurd": 1, "afgewezen": 0}


def vind_radar() -> str:
    """Het radar-bestand: expliciet meegegeven, of gevonden naast de andere stores."""
    kandidaten = [os.environ.get("RADAR_JSON", "")]
    kandidaten += sorted(glob.glob("/opt/noochville/**/live_radar.json", recursive=True))
    kandidaten += sorted(glob.glob("/opt/noochville/**/radar*.json", recursive=True))
    kandidaten += ["data/radar.json"]
    pad = next((c for c in kandidaten if c and os.path.exists(c)), None)
    if not pad:
        raise SystemExit("radar-json niet gevonden; zet RADAR_JSON=/pad/naar/radar.json")
    return pad


def bouw(pad: str) -> list[dict]:
    d = json.load(open(pad, encoding="utf-8"))
    items = d.get("items", d)
    items = list(items.values()) if isinstance(items, dict) else items
    return [{"id": it.get("id"), "feed": it.get("feed", ""), "role": it.get("role", ""),
             "content": (it.get("content") or "").strip(),
             "rationale": (it.get("rationale") or "").strip(),
             "source": it.get("source", ""), "label": LABEL[it["status"]]}
            for it in items
            if it.get("status") in LABEL and (it.get("content") or "").strip()]


def main() -> None:
    pad = vind_radar()
    rows = bouw(pad)
    keep = sum(r["label"] for r in rows)
    uit = os.environ.get("EVALSET", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "evalset.jsonl"))
    print(f"radar: {pad}")
    print(f"bruikbaar: {len(rows)}  keep={keep}  dismiss={len(rows) - keep}"
          f"  ({keep / len(rows) * 100:.1f}% keep)" if rows else "bruikbaar: 0")
    with open(uit, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(f"geschreven: {uit}")


if __name__ == "__main__":
    main()
