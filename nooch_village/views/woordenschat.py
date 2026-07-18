"""Woordenschat / kansen — de verrijkte keywords van de Library, gerangschikt op kansrijkheid.

De Library haalt zelf geen data op: rollen (Trends & Competition, Website Watcher, harry_hemp) voeden
de woorden met verrijking (KE-volume/concurrentie, GSC-positie, Trends-interesse), Library checkt en
hangt het aan het woord. Dit scherm maakt de woorden paarsgewijs vergelijkbaar met één transparante
score, zodat het meest kansrijke woord bovenaan staat. Stap 2 (beheer): met een csrf-token wordt het
scherm read-write — functie-toggle (volg/doelwit), pauzeren (avoid), verbieden (forbidden) en
heractiveren (approved), plus de secties geëscaleerd/gepauzeerd/verboden. Alle schrijfacties lopen
via POST /action (inbox_actions → Library.curate/set_function), nooit rechtstreeks in de json.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _nav

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


def _mini_form(csrf: str, action: str, word: str, label: str, cls: str = "btn sm",
               extra: str = "") -> str:
    """Eén knop = één klein POST-formulier naar /action (zelfde patroon als linkbuilding)."""
    return (f"<form method='post' action='/action' class='emo-f'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='word' value='{_e(word)}'>"
            f"<input type='hidden' name='next' value='/woordenschat'>{extra}"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


def _acties(word: str, fn: str, csrf: str) -> str:
    """Beheer-knoppen per goedgekeurd woord: functie-toggle, pauzeer, verbied (default-reden)."""
    ander = "volg" if fn == "doelwit" else "doelwit"
    toggle = _mini_form(csrf, "ws_func", word, f"⇄ {ander}",
                        extra=f"<input type='hidden' name='function' value='{_e(ander)}'>")
    pauze = _mini_form(csrf, "ws_pause", word, "⏸ pauzeer")
    verbied = _mini_form(csrf, "ws_forbid", word, "✗ verbied")
    return f"<span class='kc-actions'>{toggle}{pauze}{verbied}</span>"


def _rows(words: list, csrf: str) -> str:
    out = []
    for w, e, score in words:
        ev = e.get("evidence") or {}
        fn = e.get("function") or "volg"
        chip = "chip amber" if fn == "doelwit" else "chip outline"
        acties = f"<td>{_acties(w, fn, csrf)}</td>" if csrf else ""
        out.append(
            f"<tr><td>{_e(w)}</td>"
            f"<td><span class='{chip}'>{_e(fn)}</span></td>"
            f"<td class='num'>{_num(ev.get('volume'))}</td>"
            f"<td class='num'>{_num(ev.get('competition'))}</td>"
            f"<td class='num'>{_num(ev.get('position'))}</td>"
            f"<td class='num'><b>{_num(score)}</b></td>{acties}</tr>")
    return "".join(out)


def _status_row(word: str, e: dict, knoppen: str) -> str:
    """Rij voor een niet-approved woord: woord + rationale + datum + beheer-knoppen."""
    meta = " · ".join(x for x in (e.get("rationale") or "", e.get("date") or "") if x)
    return (f"<div class='rdr-row'><div class='rdr-body'>"
            f"<div class='rdr-sig'>{_e(word)}</div>"
            f"<div class='rdr-meta'><span class='muted'>{_e(meta) or '—'}</span></div>"
            f"<div class='ffoot-l'>{knoppen}</div></div></div>")


def _sectie(titel: str, rows: list) -> str:
    if not rows:
        return ""
    return f"<h2>{_e(titel)} ({len(rows)})</h2><div class='rdr-tool'>{''.join(rows)}</div>"


def _esc_knoppen(n: int, word: str, csrf: str) -> str:
    """Geëscaleerd: goedkeuren of verbieden mét klein reden-veld (unieke fid per rij)."""
    reden = _field("Reden", "reason", fid=f"ws-reden-{n}", placeholder="reden (anders default)")
    return (_mini_form(csrf, "ws_approve", word, "✓ keur goed", "btn ok sm")
            + _mini_form(csrf, "ws_forbid", word, "✗ verbied", "btn sm", extra=reden))


def render_woordenschat(data_dir: str, csrf_token: str = "", msg: str = "") -> str:
    path = os.path.join(data_dir, "library.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    entries = [(w, e) for w, e in data.items() if isinstance(e, dict)]
    approved = [(w, e) for w, e in entries if e.get("status") == "approved"]
    scored = sorted(((w, e, kansrijkheid(e)) for w, e in approved), key=lambda r: -r[2])
    if scored:
        acties_kop = "<th>Acties</th>" if csrf_token else ""
        tabel = (f"<table class='mtab'><tr><th>Woord</th><th>Functie</th><th class='num'>Volume</th>"
                 f"<th class='num'>Concurrentie</th><th class='num'>GSC-positie</th>"
                 f"<th class='num'>Kansrijkheid</th>{acties_kop}</tr>{_rows(scored, csrf_token)}</table>")
    else:
        tabel = ("<p class='muted'>Nog geen goedgekeurde woorden met verrijking. Rollen voeden de Library; "
                 "zet de bronnen aan (Keywords Everywhere, GSC) zodat volume en positie binnenkomen.</p>")
    beheer = ""
    if csrf_token:
        # Beheer-secties alleen op het ingelogde (schrijf-)oppervlak: zonder csrf-token blijft
        # het scherm de read-only kansrijkheid-lijst (zelfde regel als "geen schrijfknoppen").
        esc = [_status_row(w, e, _esc_knoppen(n, w, csrf_token))
               for n, (w, e) in enumerate(x for x in entries if x[1].get("status") == "escalated")]
        heractiveer = lambda w: _mini_form(csrf_token, "ws_approve", w, "✓ heractiveer", "btn ok sm")
        avoid = [_status_row(w, e, heractiveer(w))
                 for w, e in entries if e.get("status") == "avoid"]
        forb = [_status_row(w, e, heractiveer(w))
                for w, e in entries if e.get("status") == "forbidden"]
        beheer = (_sectie("Geëscaleerd (wacht op jouw oordeel)", esc)
                  + _sectie("Gepauzeerd (avoid)", avoid)
                  + _sectie("Verboden", forb))
    main = (f"<div class='c2-main'><h1>Woordenschat &amp; kansen</h1>{_banner(msg)}"
            f"<p class='muted'>De goedgekeurde woorden van de Library, gerangschikt op kansrijkheid zodat "
            f"het meest kansrijke woord bovenaan staat. Rollen leveren de verrijking aan; Library cureert.</p>"
            f"<p class='muted'>Formule: <b>kansrijkheid = volume × fit ÷ concurrentie</b> "
            f"(fit: doelwit 1,0 · seed 0,3; concurrentie 0-1 uit Keywords Everywhere).</p>"
            f"{tabel}{beheer}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Woordenschat", inner)
