"""Staging-view (/kennisbank/staging?batch=…) — "even nakijken" vóór de bibliotheek.

Toont de voorgestelde atomen uit één bron, bewerkbaar, met samenvoegen en weggooien.
Pas op "Voeg set toe aan bibliotheek" landen ze append-only in notes.json. Herkend brontype
staat bovenaan (verklaarbaar). Hergebruikt de kn-/kern-klassen; geen nieuwe machinerie zichtbaar.
"""
from __future__ import annotations

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.cockpit2_util import _DS_LINK, _BUILD
from nooch_village.kennisbank_intake import SUBJECTS

_PROV = ("peer_reviewed", "certificate", "internal_data", "survey", "expert_opinion",
         "media", "advocacy", "internal_judgment", "unknown")


def _hid(csrf: str, action: str, nxt: str, extra: dict | None = None) -> str:
    h = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
         f"<input type='hidden' name='action' value='{_e(action)}'>"
         f"<input type='hidden' name='next' value='{_e(nxt)}'>")
    for k, v in (extra or {}).items():
        h += f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
    return h


def _atoom_kaartje(b: dict, a: dict, csrf: str, nxt: str) -> str:
    """Eén voorgesteld atoom: bewerkbaar (content/onderwerp/provenance) + aanvinken + weggooien."""
    sid = a["sid"]
    subj_opts = "<option value=''>— geen onderwerp —</option>" + "".join(
        f"<option value='{_e(s)}'{' selected' if a.get('subject') == s else ''}>{_e(s)}</option>"
        for s in SUBJECTS)
    prov_opts = "".join(
        f"<option value='{_e(p)}'{' selected' if a.get('provenance') == p else ''}>{_e(p)}</option>"
        for p in _PROV)
    body = (f"<details class='kn-nctrl'><summary>samengestelde inhoud</summary>"
            f"<div class='kn-ann'>{_e(a['body']).replace(chr(10), '<br>')}</div></details>"
            if (a.get("body") or "").strip() else "")
    bron = "bron: " + _e(a['source']) + (f" · {_e(a['reference'])}" if a.get("reference") else "")
    # Verticale stapel-kaart op volle breedte (fix-brief bug 1): een grid met een
    # middenkolom minmax(0,1fr) zodat lange onbreekbare strings (URL-slugs) de kaart nooit
    # naar ~0 breedte kunnen persen. Checkbox links, inhoud+controls midden, × rechts.
    return (
        f"<div class='kn-stage'>"
        f"<input type='checkbox' name='sid' value='{_e(sid)}' form='mergeform' aria-label='selecteer'>"
        f"<form method='post' action='/action' class='kn-stage-edit'>"
        f"{_hid(csrf, 'kb_stage_edit', nxt, {'bid': b['id'], 'sid': sid})}"
        f"<textarea name='content' rows='2'>{_e(a['content'])}</textarea>{body}"
        f"<span class='kn-stage-src'>{bron}</span>"
        f"<div class='kn-stage-ctrls'><select name='subject'>{subj_opts}</select>"
        f"<select name='provenance'>{prov_opts}</select>"
        f"<button class='btn'>Bewaar</button></div></form>"
        f"<form method='post' action='/action' class='kn-stage-del'>"
        f"{_hid(csrf, 'kb_stage_delete', nxt, {'bid': b['id'], 'sid': sid})}"
        f"<button class='btn' title='weggooien'>×</button></form></div>")


def render_kennisbank_staging(st, bid: str, csrf_token: str = "", msg: str = "") -> str:
    b = st.staging.get(bid)
    if b is None:
        inner = (f"{_DS_LINK}<div class='c2-wrap'><div class='c2-main'>"
                 f"<p class='muted'>Deze staging-set is er niet (meer). "
                 f"<a href='/kennisbank'>← terug</a></p></div></div>")
        return _page("Even nakijken", inner)
    nxt = f"/kennisbank/staging?batch={bid}"
    atomen = b.get("atoms") or []
    kaartjes = "".join(_atoom_kaartje(b, a, csrf_token, nxt) for a in atomen) or (
        "<p class='muted'>Geen atomen meer in deze set.</p>")
    tab = " <span class='chip muted'>tabeldata</span>" if b.get("tabular") else ""

    merge = (f"<form method='post' action='/action' id='mergeform' class='kn-lrow'>"
             f"{_hid(csrf_token, 'kb_stage_merge', nxt, {'bid': bid})}"
             f"{_field('kop voor een samengestelde kaart (vink eerst ≥2 aan)', 'kop', fid='f-stg-kop')}"
             f"<button class='btn'>Voeg samen</button></form>")
    commit = (f"<form method='post' action='/action'>"
              f"{_hid(csrf_token, 'kb_stage_commit', '/kennisbank', {'bid': bid})}"
              f"<button class='btn ok'>Voeg set toe aan bibliotheek ({len(atomen)})</button></form>"
              f"<form method='post' action='/action'>"
              f"{_hid(csrf_token, 'kb_stage_discard', '/kennisbank', {'bid': bid})}"
              f"<button class='btn'>Gooi de hele set weg</button></form>")

    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/kennisbank'>← wat Nooch weet</a></div>"
            f"<h1>Even nakijken</h1>"
            f"<p class='muted'>Herkend als <b>{_e(b.get('kind'))}</b>{tab} · bron "
            f"<b>{_e(b.get('source_label'))}</b>. Bewerk, voeg samen of gooi weg. Pas op "
            f"“Voeg set toe” landen ze in de bibliotheek.</p>{_banner(msg)}"
            f"{merge}{kaartjes}<div class='kn-sec'>{commit}</div></div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             f"<a href='/'>home</a> · <a href='/kennisbank'>kennisbank</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Even nakijken", inner)
