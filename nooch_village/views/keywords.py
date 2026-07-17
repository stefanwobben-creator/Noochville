"""Keywords — de analyse-lens van Trends & Competition (concurrent_scout / Billy Buzz).

Leest de bibliotheek-beslissingen (`data/library.json`) en toont ze als ANALYSE + SUGGESTIES:
geëvalueerde keywords gerangschikt op kansrijkheid (opportunity), met status, volume, concurrentie
en bron. Dit is de scout-kant — kansen zien en voorstellen — los van Lara's woordenschat-curatie.
Fase 2 (read-only, minimaal instrument); in fase 3 wordt dit een lens op één keyword-datalaag.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _nav

_STATUS_CHIP = {"approved": "chip green", "escalated": "chip amber",
                "forbidden": "chip coral", "": "chip muted"}


def _num(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", ".") if v >= 1000 else f"{v:g}"
    return "—"


def _opportunity(entry: dict) -> float:
    """De kans-score uit de verrijking; fail-safe naar 0 als er niets is."""
    ev = entry.get("evidence") or {}
    v = ev.get("opportunity")
    if isinstance(v, (int, float)):
        return float(v)
    # fallback: volume ÷ concurrentie als opportunity ontbreekt
    vol = ev.get("volume"); vol = float(vol) if isinstance(vol, (int, float)) else 0.0
    comp = ev.get("competition"); comp = float(comp) if isinstance(comp, (int, float)) and comp > 0 else 1.0
    return round(vol / max(comp, 0.1), 1)


def _rows(items: list) -> str:
    out = []
    for term, e, opp in items:
        ev = e.get("evidence") or {}
        status = e.get("status") or ""
        chip = _STATUS_CHIP.get(status, "chip muted")
        out.append(
            f"<tr><td>{_e(term)}</td>"
            f"<td><span class='{chip}'>{_e(status or '—')}</span></td>"
            f"<td class='num'>{_num(ev.get('volume'))}</td>"
            f"<td class='num'>{_num(ev.get('competition'))}</td>"
            f"<td class='num'><b>{_num(opp)}</b></td>"
            f"<td>{_e(ev.get('source') or '—')}</td></tr>")
    return "".join(out)


def render_keywords(data_dir: str) -> str:
    path = os.path.join(data_dir, "library.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    evaluated = [(w, e, _opportunity(e)) for w, e in data.items() if isinstance(e, dict)]
    evaluated.sort(key=lambda r: -r[2])

    if evaluated:
        tabel = (f"<table class='mtab'><tr><th>Keyword</th><th>Status</th><th class='num'>Volume</th>"
                 f"<th class='num'>Concurrentie</th><th class='num'>Kansrijkheid</th><th>Bron</th></tr>"
                 f"{_rows(evaluated)}</table>")
    else:
        tabel = ("<p class='muted'>Nog geen geëvalueerde keywords. De bronnen (Trends, GSC, Keywords "
                 "Everywhere) voeden de bibliotheek; zodra rollen keywords voorstellen verschijnen ze hier.</p>")

    # Suggesties = de approved-kandidaten, de kansrijkste eerst — waar de scout op kan sturen.
    sugg = [r for r in evaluated if (r[1].get("status") == "approved")][:8]
    if sugg:
        chips = "".join(f"<span class='chip green'>{_e(t)} <span class='muted'>· {_num(o)}</span></span> "
                        for t, _e2, o in sugg)
        sugg_block = (f"<div class='c2-sec'><h2>Suggesties</h2>"
                      f"<p class='muted'>Goedgekeurde, kansrijke keywords om op te sturen (content of "
                      f"linkbuilding). Kansrijkheid staat achter het woord.</p>{chips}</div>")
    else:
        sugg_block = ""

    main = (f"<div class='c2-main'><h1>Keywords <span class='chip'>trends &amp; competition</span></h1>"
            f"<p class='muted'>De analyse-lens van de scout: geëvalueerde keywords gerangschikt op "
            f"kansrijkheid, met status en concurrentie. Curatie van de woordenschat doet de Library.</p>"
            f"{tabel}{sugg_block}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Keywords", inner)
