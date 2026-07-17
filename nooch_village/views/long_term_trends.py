"""Long-term trends — de lange-boog-lens van de Scientist (harry_hemp / Sid).

Leest de append-only observatiereeks van de trend-herindexering (`data/trend_signals.jsonl`,
output van `reindex_metrics`). Toont per term het signaal-type — emergence / trend (échte
signalen) versus peak (een blip) en flat (niets) — met de recente trajectorie. Sid's vraag is:
'wat komt structureel op?', niet 'wat piekte even?'. Fase 2 (read-only, minimaal instrument);
in fase 3 wordt dit de Scientist-lens op één gedeelde keyword-datalaag.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav

# Volgorde + duiding per signaal-type. Échte signalen bovenaan, blip/vlak eronder.
_TYPE_ORDER = {"emergence": 0, "trend": 1, "peak": 2, "flat": 3}
_TYPE_CHIP = {"emergence": "chip green", "trend": "chip green",
              "peak": "chip amber", "flat": "chip muted"}
_TYPE_LABEL = {"emergence": "opkomst", "trend": "stijgend",
               "peak": "blip", "flat": "vlak"}


def _num(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:g}"
    return "—"


def _latest_per_term(path: str) -> list[dict]:
    """Append-only reeks → laatste observatie per term (de recentste telt)."""
    latest: dict[str, dict] = {}
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obs = json.loads(line)
            except Exception:
                continue
            term = obs.get("term")
            if term:
                latest[term] = obs        # latere regel overschrijft eerdere
    return list(latest.values())


def _window(obs: dict) -> str:
    months = obs.get("recent_months") or []
    if not months:
        return "—"
    return f"{months[0]} – {months[-1]}" if len(months) > 1 else months[0]


def _rows(items: list[dict]) -> str:
    out = []
    for obs in items:
        st = obs.get("signal_type") or "flat"
        chip = _TYPE_CHIP.get(st, "chip muted")
        label = _TYPE_LABEL.get(st, st)
        sig = "✓" if obs.get("is_signal") else "—"
        out.append(
            f"<tr><td>{_e(obs.get('term') or '—')}</td>"
            f"<td><span class='{chip}'>{_e(label)}</span></td>"
            f"<td class='num'>{_num(obs.get('recent_sustained'))}</td>"
            f"<td class='num'>{_num(obs.get('peak'))}</td>"
            f"<td>{_e(_window(obs))}</td>"
            f"<td class='num'>{sig}</td></tr>")
    return "".join(out)


def render_long_term_trends(data_dir: str) -> str:
    path = os.path.join(data_dir, "trend_signals.jsonl")
    obs = _latest_per_term(path)
    obs.sort(key=lambda o: (_TYPE_ORDER.get(o.get("signal_type") or "flat", 9),
                            -(o.get("recent_sustained") or 0)))
    signalen = [o for o in obs if o.get("is_signal")]

    if obs:
        tabel = (f"<table class='mtab'><tr><th>Term</th><th>Signaal</th>"
                 f"<th class='num'>Recent</th><th class='num'>Piek</th><th>Venster</th>"
                 f"<th class='num'>Signaal?</th></tr>{_rows(obs)}</table>")
    else:
        tabel = ("<p class='muted'>Nog geen trend-observaties. De dagelijkse trend-herindexering "
                 "(Sid) vult <code>trend_signals.jsonl</code> zodra de bron beschikbaar is.</p>")

    tel = (f"<p class='muted'><b>{len(signalen)}</b> van {len(obs)} termen zijn een écht signaal "
           f"(opkomst of stijgend, geen blip).</p>" if obs else "")

    main = (f"<div class='c2-main'><h1>Long-term trends <span class='chip'>scientist</span></h1>"
            f"<p class='muted'>De lange-boog-lens: welke termen komen structureel op of stijgen door — "
            f"onderscheiden van een korte piek (blip). Emergence en trend zijn echte signalen; "
            f"peak is een blip, flat is ruis.</p>{tel}{tabel}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Long-term trends", inner)
