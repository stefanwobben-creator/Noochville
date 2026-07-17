"""De gedeelde keyword-datalaag (IA-fase 3).

Eén per-term-waarheid, AFGELEID bij lezen — geen nieuwe opgeslagen store, geen gedupliceerde
cijfers ("Reference, don't copy"). De laag joint twee bestaande bronnen op de term (kleine letter):

- `data/library.json`   — de Librarian-beslissing (status/functie) + verrijking (volume,
                          concurrentie, opportunity, GSC-positie). Bron: library_enrich.
- `data/trend_signals.jsonl` — de trend-herindexering van Sid (signal_type, trajectorie,
                          is_signal), append-only; de laatste observatie per term telt.

Elke rol kijkt via een LENS naar deze ene laag (marketing/scientist/trends/library); ze delen
dus dezelfde cijfers i.p.v. elk een eigen bron te tellen.
"""
from __future__ import annotations

import json
import os

# signal_type → richting in mensentaal (dezelfde duiding als de Scientist-lens).
_DIRECTION = {"emergence": "stijgend", "trend": "stijgend", "peak": "blip", "flat": "vlak"}


def _read_library(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _latest_trends_per_term(path: str) -> dict:
    """Append-only reeks → laatste observatie per term (kleine letter als sleutel)."""
    latest: dict[str, dict] = {}
    if not os.path.exists(path):
        return latest
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obs = json.loads(line)
            except Exception:
                continue
            term = (obs.get("term") or "").strip()
            if term:
                latest[term.lower()] = obs
    return latest


def _num(v):
    return float(v) if isinstance(v, (int, float)) else None


def _direction(entry: dict | None, trend: dict | None) -> str:
    """Richting: primair uit het trend-signaal; anders uit de library-verrijking (breakout/signal)."""
    if trend:
        return _DIRECTION.get(trend.get("signal_type") or "", "—")
    ev = (entry or {}).get("evidence") or {}
    if ev.get("breakout") or ev.get("signal") == "positive":
        return "stijgend"
    return "—"


def build_keyword_layer(data_dir: str) -> list[dict]:
    """Union-per-term van library-verrijking + trend-signaal. Eén record per keyword; velden die
    een bron niet levert blijven None (geen verzonnen nul). Ongesorteerd — de lens sorteert."""
    lib = _read_library(os.path.join(data_dir, "library.json"))
    trends = _latest_trends_per_term(os.path.join(data_dir, "trend_signals.jsonl"))

    # originele schrijfwijze behouden waar mogelijk; join op kleine letter
    lib_lower = {k.lower(): (k, v) for k, v in lib.items() if isinstance(v, dict)}
    terms = set(lib_lower) | set(trends)

    rows = []
    for key in terms:
        orig, entry = lib_lower.get(key, (None, None))
        trend = trends.get(key)
        term = orig or (trend.get("term") if trend else key)
        ev = (entry or {}).get("evidence") or {}
        rows.append({
            "term": term,
            "in_library": entry is not None,
            "in_trends": trend is not None,
            "status": (entry or {}).get("status"),
            "function": (entry or {}).get("function"),
            "volume": _num(ev.get("volume")),
            "competition": _num(ev.get("competition")),
            "opportunity": _num(ev.get("opportunity")),
            "position": _num(ev.get("position")),
            "source": ev.get("source"),
            "signal_type": (trend or {}).get("signal_type"),
            "recent_sustained": _num((trend or {}).get("recent_sustained")),
            "peak": _num((trend or {}).get("peak")),
            "recent_months": (trend or {}).get("recent_months"),
            "is_signal": bool((trend or {}).get("is_signal")),
            "direction": _direction(entry, trend),
        })
    return rows


def converges(row: dict) -> bool:
    """Lara's convergentie-toets: waar meerdere facetten samenkomen en curatie loont —
    een écht trend-signaal dat óók meetbaar volume/bibliotheek-context heeft, of een open
    (escalated) status met een signaal eronder."""
    signal = row.get("is_signal")
    has_volume = (row.get("volume") or 0) > 0
    open_status = row.get("status") in ("escalated", None) and row.get("in_trends")
    return bool((signal and (has_volume or row.get("in_library"))) or (open_status and signal))
