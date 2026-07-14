"""LLM-usage-log — de grondslag onder de CO2-KPI van het dorp.

Elke GESLAAGDE LLM-call (via reason()) landt hier als één append-regel: welke call-site, welke trede
(vendor:model), hoeveel tokens, en of dat een schatting is. De dagelijkse CO2-aggregatie leest dit terug.

Tokens: zolang we de vendor-usage niet uitlezen, schatten we uit tekenlengte (prompt + antwoord) / 4,
gemarkeerd als `estimated=True`. Zo blijft de meting eerlijk over wat geschat is. Real usage per vendor
is een latere verfijning die `estimated` op False zet voor de tredes die het echt teruggeven.

Fail-soft: een schrijffout mag een LLM-call NOOIT breken — dit is boekhouding, geen kritiek pad.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import time

from nooch_village.util import file_lock

log = logging.getLogger("village.llm.usage")

_PATH: str | None = None            # module-singleton; de village zet 'm op zijn data_dir, anders default


def set_path(path: str) -> None:
    """De village zet dit bij opstart op `<data_dir>/llm_usage.jsonl`."""
    global _PATH
    _PATH = path


def _path() -> str:
    return _PATH or os.path.join("data", "llm_usage.jsonl")


def _day(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat()


def estimate_split(prompt: str, output: str) -> tuple:
    """(input_tokens, output_tokens) geschat uit tekenlengte (~4 tekens per token). APART, omdat
    input- en output-tokens verschillende emissiefactoren hebben (input ≈ output/5). Bron van waarheid
    wordt later de vendor-usage waar die beschikbaar is."""
    return len(prompt or "") // 4, len(output or "") // 4


def record(call_site: str, tier: str, in_tokens: int, out_tokens: int, *, estimated: bool = True,
           ts: float | None = None, path: str | None = None) -> None:
    """Append één usage-regel (input- en output-tokens apart). Fail-soft (nooit de LLM-call breken)."""
    t = time.time() if ts is None else ts
    it, ot = int(in_tokens or 0), int(out_tokens or 0)
    row = {"ts": t, "day": _day(t), "call_site": call_site or "onbekend", "tier": tier or "onbekend",
           "in_tokens": it, "out_tokens": ot, "tokens": it + ot, "estimated": bool(estimated)}
    p = path or _path()
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        line = json.dumps(row, ensure_ascii=False) + "\n"
        with file_lock(p):
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:                       # boekhouding mag de puls nooit breken
        log.debug("usage-log overslaan (%s): %s", call_site, e)


def read_day(day: str, path: str | None = None) -> list:
    """Alle usage-rijen van één dag (YYYY-MM-DD). Ontbrekend bestand → []."""
    p = path or _path()
    rows = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("day") == day:
                    rows.append(r)
    except FileNotFoundError:
        pass
    return rows
