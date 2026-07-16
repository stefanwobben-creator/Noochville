"""Woordenschat / kansen — de verrijkte keywords van de Library, gerangschikt op kansrijkheid.

De Library haalt zelf geen data op: rollen (Trends & Competition, Website Watcher, harry_hemp) voeden
de woorden met verrijking (KE-volume/concurrentie, GSC-positie, Trends-interesse), Library checkt en
hangt het aan het woord. Dit scherm maakt de woorden paarsgewijs vergelijkbaar met één transparante
score, zodat het meest kansrijke woord bovenaan staat. Stap 1 (read-only): de lijst zien werken. Het
pull-gedrag (rol matcht woord op accountability → future-project) volgt als stap 2.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _BUILD

# fit: een doelwit is een rank-doel (hier maak je content voor); een seed voedt alleen de radar.
_FIT = {"doelwit": 1.0, "volg": 0.3}


def kansrijkheid(entry: dict) -> float:
    """Transparante score: volume × fit ÷ concurrentie. Zichtbaar in het scherm zodat je 'm kunt bijstellen.
    Ontbrekende velden fail-safe naar neutraal (volume 0 → score 0; concurrentie leeg → 1)."""
    ev = entry.get("evidence") or {}
    volume = ev.get("volume")
    volume = float(volume) if isinstance(volume, (int, float)) else 0.0
    comp = ev.get("competition")
    comp = float(comp) if isinstance(comp, (int, float)) and comp > 0 else 1.0
    fit = _FIT.get(entry.get("function"), 0.3)
    return round(volume * fit / max(comp, 0.1), 1)


def _num(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", ".") if v >= 1000 else f"{v:g}"
    return "—"


def _rows(words: list) -> str:
    out = []
    for w, e, score in words:
        ev = e.get("evidence") or {}
        fn = e.get("function") or "volg"
        chip = "chip amber" if fn == "doelwit" else "chip outline"
        out.append(
            f"<tr><td>{_e(w)}</td>"
            f"<td><span class='{chip}'>{_e(fn)}</span></td>"
            f"<td class='num'>{_num(ev.get('volume'))}</td>"
            f"<td class='num'>{_num(ev.get('competition'))}</td>"
            f"<td class='num'>{_num(ev.get('position'))}</td>"
            f"<td class='num'><b>{_num(score)}</b></td></tr>")
    return "".join(out)


def render_woordenschat(data_dir: str) -> str:
    path = os.path.join(data_dir, "library.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    approved = [(w, e) for w, e in data.items() if isinstance(e, dict) and e.get("status") == "approved"]
    scored = sorted(((w, e, kansrijkheid(e)) for w, e in approved), key=lambda r: -r[2])
    if scored:
        tabel = (f"<table class='mtab'><tr><th>Woord</th><th>Functie</th><th class='num'>Volume</th>"
                 f"<th class='num'>Concurrentie</th><th class='num'>GSC-positie</th>"
                 f"<th class='num'>Kansrijkheid</th></tr>{_rows(scored)}</table>")
    else:
        tabel = ("<p class='muted'>Nog geen goedgekeurde woorden met verrijking. Rollen voeden de Library; "
                 "zet de bronnen aan (Keywords Everywhere, GSC) zodat volume en positie binnenkomen.</p>")
    main = (f"<div class='c2-main'><h1>Woordenschat &amp; kansen</h1>"
            f"<p class='muted'>De goedgekeurde woorden van de Library, gerangschikt op kansrijkheid zodat "
            f"het meest kansrijke woord bovenaan staat. Rollen leveren de verrijking aan; Library cureert.</p>"
            f"<p class='muted'>Formule: <b>kansrijkheid = volume × fit ÷ concurrentie</b> "
            f"(fit: doelwit 1,0 · seed 0,3; concurrentie 0-1 uit Keywords Everywhere).</p>"
            f"{tabel}</div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/bronnen'>bronnen</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Woordenschat", inner)
