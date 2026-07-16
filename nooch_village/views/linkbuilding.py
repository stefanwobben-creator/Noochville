"""Linkbuilding — de doelwit-lijst geborgd in cockpit 2.

De radar (ConcurrentScout, skill linkbuilding_targets) stelt gidsen/lijstjes voor waar Nooch in
vermeld wil worden; jij beslist per doelwit of het pitchen waard is. Tot nu toe leefde dit alleen in
cockpit 1; dit scherm brengt het naar cockpit 2, read-write, zodat linkbuilding blijft werken als de
rest van de autonome processen wordt stopgezet. Leest de `LinkTargets`-store (linkbuilding_targets.json).
"""
from __future__ import annotations

import os

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _DS_LINK, _BUILD

_PRIO_CHIP = {"hoog": "chip amber", "midden": "chip", "laag": "chip outline", "onbekend": "chip outline"}


def _decide(action: str, link: str, label: str, cls: str, csrf: str) -> str:
    return (f"<form method='post' action='/action' class='emo-f'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
            f"<input type='hidden' name='link' value='{_e(link)}'>"
            f"<input type='hidden' name='next' value='/linkbuilding'>"
            f"<button class='{cls}' name='action' value='{action}'>{_e(label)}</button></form>")


def _cand_card(c: dict, csrf: str) -> str:
    link = c.get("link", "")
    title = c.get("title") or link or "(zonder titel)"
    src = c.get("source") or ""
    prio = c.get("priority") or "onbekend"
    seen = c.get("first_seen") or ""
    disp = (f"<a href='{_e(link)}' target='_blank' rel='noopener'>{_e(str(title))}</a>"
            if isinstance(link, str) and link.startswith("http") else _e(str(title)))
    chip = f"<span class='{_PRIO_CHIP.get(prio, 'chip outline')}'>{_e(prio)}</span>"
    meta = f"{_e(src)}{(' · sinds ' + _e(seen)) if seen else ''}"
    acties = ""
    if csrf:
        acties = (_decide("link_pursue", link, "Ga pitchen", "btn ok sm", csrf)
                  + _decide("link_ignore", link, "Negeer", "btn sm", csrf))
    return (f"<div class='card'><div class='cl-head'><div class='rdr-sig'>{disp}</div>"
            f"<span class='kc-actions'>{chip}</span></div>"
            f"<div class='rdr-meta'><span class='muted'>{meta}</span></div>"
            f"<div class='ffoot-l'>{acties}</div></div>")


def _link_title(p: dict) -> str:
    link = str(p.get("link", "") or "")
    title = str(p.get("title") or link or "")
    if link.startswith("http"):
        return f"<a href='{_e(link)}' target='_blank' rel='noopener'>{_e(title)}</a>"
    return _e(title)


def _pursued_row(p: dict) -> str:
    return (f"<div class='rdr-row'><div class='rdr-body'><div class='rdr-sig'>{_link_title(p)}</div>"
            f"<div class='rdr-meta'><span class='muted'>{_e(p.get('source', ''))}</span></div></div></div>")


def render_linkbuilding(data_dir: str, csrf_token: str = "") -> str:
    from nooch_village.link_targets import LinkTargets
    store = LinkTargets(os.path.join(data_dir, "linkbuilding_targets.json"))
    cands = store.candidates()
    purs = store.pursued()
    cand_html = "".join(_cand_card(c, csrf_token) for c in cands) or (
        "<p class='muted'>Nog geen doelwitten om te beoordelen. De radar vult deze lijst elke puls.</p>")
    pursued_block = ""
    if purs:
        prows = "".join(_pursued_row(p) for p in purs)
        pursued_block = f"<h2>Wordt gepitcht ({len(purs)})</h2><div class='rdr-tool'>{prows}</div>"
    main = (f"<div class='c2-main'><h1>Linkbuilding</h1>"
            f"<p class='muted'>Gidsen en lijstjes waar Nooch in vermeld wil worden. Beslis per doelwit: "
            f"ga je pitchen of negeer je het. {len(cands)} te beoordelen.</p>"
            f"<h2>Te beoordelen</h2>{cand_html}{pursued_block}</div>")
    inner = (f"{_DS_LINK}<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/bronnen'>bronnen</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Linkbuilding", inner)
