"""Woordenschat / kansen — de verrijkte keywords van de Library, gerangschikt op kansrijkheid.

De Library haalt zelf geen data op: rollen (Trends & Competition, Website Watcher, harry_hemp) voeden
de woorden met verrijking (KE-volume/concurrentie, GSC-positie, Trends-interesse), Library checkt en
hangt het aan het woord. Dit scherm maakt de woorden paarsgewijs vergelijkbaar met één transparante
score, zodat het meest kansrijkste woord bovenaan staat.

Beheer (mét csrf-token) is bewust minimaal: per woord alléén ✗ verbied (→ forbidden, komt nooit meer
terug in discovery), goedkeuren/verbieden bij geëscaleerde woorden, en heractiveren op de
forbidden-lijst als undo. De functie (doelwit/volg) bepaalt de fit in de score en welke woorden een
GSC-reeks krijgen, maar wordt automatisch door de heuristiek bepaald (library.classify_function) —
geen knop. De Trend-kolom toont de GSC-impressies-reeks (scope 2) als sparkline: zo zie je de
ontwikkeling van een kans zonder te hoeven pauzeren. Alle schrijfacties lopen via POST /action
(inbox_actions → Library.curate), nooit rechtstreeks in de json.
"""
from __future__ import annotations

import json
import os

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _nav
from nooch_village.observations import ObservationStore
from nooch_village.views.metrics import _spark_svg

# fit: een doelwit is een rank-doel (hier maak je content voor); een seed voedt alleen de radar.
_FIT = {"doelwit": 1.0, "volg": 0.3}

_SPARK_DAGEN = 30      # venster van de Trend-sparkline (laatste N dagpunten)


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


def _gsc_sparks(data_dir: str) -> dict:
    """Per Library-keyword (lower) de GSC-impressies-dagreeks als (datum, waarde)-punten.
    Fail-soft: geen observations-bestand of geen reeksen → leeg dict (sparkline toont —)."""
    try:
        obs = ObservationStore(os.path.join(data_dir, "observations.jsonl"))
        groups = obs.dimensioned_series("gsc_impressions_day", bron="gsc")
    except Exception:
        return {}
    out = {}
    for label, rows in groups.items():
        pts = [(r.get("datum") or "", r.get("value")) for r in rows
               if isinstance(r.get("value"), (int, float))]
        if pts:
            out[str(label).lower()] = pts[-_SPARK_DAGEN:]
    return out


def _spark_cell(word: str, sparks: dict) -> str:
    pts = sparks.get(word.lower())
    if not pts or len(pts) < 2:
        return "<span class='muted' title='nog geen GSC-reeks'>—</span>"
    titel = f"GSC-impressies {pts[0][0]} → {pts[-1][0]}"
    return f"<span title='{_e(titel)}'>{_spark_svg(pts)}</span>"


def _rows(words: list, sparks: dict, csrf: str) -> str:
    out = []
    for w, e, score in words:
        ev = e.get("evidence") or {}
        verbied = (f"<td><span class='kc-actions'>"
                   f"{_mini_form(csrf, 'ws_forbid', w, '✗ verbied')}</span></td>") if csrf else ""
        out.append(
            f"<tr><td>{_e(w)}</td>"
            f"<td>{_spark_cell(w, sparks)}</td>"
            f"<td class='num'>{_num(ev.get('volume'))}</td>"
            f"<td class='num'>{_num(ev.get('competition'))}</td>"
            f"<td class='num'>{_num(ev.get('position'))}</td>"
            f"<td class='num'><b>{_num(score)}</b></td>{verbied}</tr>")
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
        sparks = _gsc_sparks(data_dir)
        acties_kop = "<th>Acties</th>" if csrf_token else ""
        tabel = (f"<table class='mtab'><tr><th>Woord</th><th>Trend</th><th class='num'>Volume</th>"
                 f"<th class='num'>Concurrentie</th><th class='num'>GSC-positie</th>"
                 f"<th class='num'>Kansrijkheid</th>{acties_kop}</tr>{_rows(scored, sparks, csrf_token)}</table>")
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
            f"het meest kansrijke woord bovenaan staat. Rollen leveren de verrijking aan; Library cureert. "
            f"De Trend-kolom is de GSC-impressies-reeks van de laatste {_SPARK_DAGEN} dagen.</p>"
            f"<p class='muted'>Formule: <b>kansrijkheid = volume × fit ÷ concurrentie</b> "
            f"(fit: rank-doel 1,0 · brede seed 0,3, automatisch bepaald; concurrentie 0-1 uit "
            f"Keywords Everywhere).</p>"
            f"{tabel}{beheer}</div>")
    inner = (f"{_DS_LINK}{_nav()}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Woordenschat", inner)
