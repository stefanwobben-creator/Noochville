"""Backlog Builder — het eigen scherm van de Website Developer-rol (`/backlog`).

Stond tot nu toe ÓP de Notes-tab van die rol: `render_node` verving daar de notes door dit scherm.
Dat had twee gevolgen die pas nu opvielen. De backlog builder is een gereedschap en hoort dus onder
Tools (waar de andere rol-tools ook wonen), en de Website Developer was de enige rol zonder
notes — en daarmee sinds de wiki-laag ook de enige rol zonder pagina's. Dit scherm staat daarom los,
en de Tools-tab van de rol wijst ernaar (`_ROLE_TOOLS` in views/overview.py).

Twee kanten, één bron:
- inbrenger (iedereen-ingelogd): item indienen + je eigen ingediende items
- beheerder (rolvervuller Website Developer): overzicht per staat + staat/prioriteit beheren

De vorm van dit scherm is nog de prototype-vorm; de leidende mockup
(`docs/backlog_builder_screen.html`) en het bijbehorende superset-schema komen in de volgende brok.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import (WEBSITE_DEVELOPER_ROLE, md_editor, _md,
                                         _DS_LINK, _nav, _name)
from nooch_village.backlog import TYPES, DOMEINEN, STATEN, IMPACTS, EFFORTS

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

# Waar de forms na een POST naartoe terugkeren: het scherm zelf, niet meer de Notes-tab.
TERUG = "/backlog"

# Display-mapping: de sleutels blijven de opgeslagen waarden, alleen het label is Engels.
_STAAT_LABEL = {"ruw": "Raw", "geformuleerd": "Formulated", "verkleind": "Reduced",
                "geprioriteerd": "Prioritised", "uitgevoerd": "Done"}
_VALUE_LABEL = {"bug": "bug", "wens": "wish", "idee": "idea",
                "website": "website", "village": "village",
                "hoog": "high", "medium": "medium", "laag": "low",
                "1u": "1h", "1d": "1d", "2d": "2d", "1w": "1w"}


def _vl(value: str) -> str:
    """Engels label bij een opgeslagen keuze-waarde (type/domein/impact/effort)."""
    return _VALUE_LABEL.get(value, value)


def _is_beheerder(st: "_Stores", username: str | None) -> bool:
    """Beheerder = rolvervuller van de Website Developer-rol. guest (auth uit) → volledige toegang,
    consistent met de dispatch-gate."""
    if username == "guest":
        return True
    if not username:
        return False
    actor = st.people.by_email(username)
    return bool(actor and any(f.type == "person" and f.id == actor.id
                              for f in st.assign.fillers_of(WEBSITE_DEVELOPER_ROLE)))


def _me(st: "_Stores", username: str | None):
    return st.people.by_email(username) if username and username != "guest" else None


def _chips(it) -> str:
    imp = f"<span class='chip'>impact: {_e(_vl(it.impact))}</span>" if it.impact else ""
    eff = f"<span class='chip'>effort: {_e(_vl(it.effort))}</span>" if it.effort else ""
    return (f"<span class='chip'>{_e(_vl(it.type))}</span>"
            f"<span class='chip'>{_e(_vl(it.domein))}</span>{imp}{eff}")


def _opts(values, sel) -> str:
    out = ["<option value=''>—</option>"]
    for v in values:
        s = " selected" if v == sel else ""
        out.append(f"<option value='{_e(v)}'{s}>{_e(_vl(v))}</option>")
    return "".join(out)


def _inbrenger_view(st: "_Stores", csrf: str, username: str | None) -> str:
    if not csrf:
        return ""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='next' value='{TERUG}'>")
    type_opts = "".join(f"<option value='{t}'>{_e(_vl(t))}</option>" for t in TYPES)
    dom_opts = "".join(f"<option value='{d}'>{_e(_vl(d))}</option>" for d in DOMEINEN)
    form = (f"<div class='c2-sec'><h3>Submit item</h3>"
            f"<form method='post' action='/action' class='qadd-form'>{hid}"
            f"<input name='titel' placeholder='Title…' autocomplete='off' required>"
            f"{md_editor('beschrijving', rows=4, placeholder='Description (free text)…')}"
            f"<label class='att-lbl' for='bl-type'>Type</label>"
            f"<select id='bl-type' name='type'>{type_opts}</select>"
            f"<label class='att-lbl' for='bl-domein'>Domain</label>"
            f"<select id='bl-domein' name='domein'>{dom_opts}</select>"
            f"<div class='qadd-row'><button class='btn ok' type='submit' name='action' "
            f"value='backlog_add'>Submit</button></div></form></div>")
    me = _me(st, username)
    mine = [it for it in st.backlog.all() if me and it.inbrenger_id == me.id]
    mine.sort(key=lambda it: it.aangemaakt_at, reverse=True)
    if mine:
        rows = "".join(f"<li><b>{_e(it.titel)}</b> {_chips(it)} "
                       f"<span class='muted'>· {_e(_STAAT_LABEL.get(it.staat, it.staat))}</span></li>"
                       for it in mine)
        own = f"<div class='c2-sec'><h3>My submitted items ({len(mine)})</h3><ul class='clean'>{rows}</ul></div>"
    else:
        own = "<div class='c2-sec'><p class='muted'>You haven’t submitted anything yet.</p></div>"
    return form + own


def _item_beheer(it, csrf: str) -> str:
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='next' value='{TERUG}'>"
           f"<input type='hidden' name='bid' value='{_e(it.id)}'>")
    staat_opts = "".join(f"<option value='{s}'{' selected' if s == it.staat else ''}>"
                         f"{_e(_STAAT_LABEL[s])}</option>" for s in STATEN)
    sid = f"bl-staat-{_e(it.id)}"
    staat_form = (f"<form method='post' action='/action'>{hid}"
                  f"<label class='att-lbl' for='{sid}'>State</label>"
                  f"<select id='{sid}' name='staat' onchange='this.form.requestSubmit()'>{staat_opts}</select>"
                  f"<button class='btn sm' type='submit' name='action' value='backlog_update_staat'>state</button></form>")
    iid, eid = f"bl-imp-{_e(it.id)}", f"bl-eff-{_e(it.id)}"
    prio_form = (f"<form method='post' action='/action'>{hid}"
                 f"<label class='att-lbl' for='{iid}'>Impact</label>"
                 f"<select id='{iid}' name='impact'>{_opts(IMPACTS, it.impact)}</select>"
                 f"<label class='att-lbl' for='{eid}'>Effort</label>"
                 f"<select id='{eid}' name='effort'>{_opts(EFFORTS, it.effort)}</select>"
                 f"<button class='btn sm' type='submit' name='action' value='backlog_update_prioriteit'>priority</button></form>")
    desc = f"<div class='muted'>{_md(it.beschrijving)}</div>" if it.beschrijving else ""
    return (f"<div class='card'><div class='ptitle'>{_e(it.titel)} {_chips(it)}</div>"
            f"{desc}<div class='qadd-row'>{staat_form}{prio_form}</div></div>")


def _beheerder_view(st: "_Stores", csrf: str) -> str:
    if not csrf:
        return ""
    items = st.backlog.all()
    by_staat: dict[str, list] = {s: [] for s in STATEN}
    for it in items:
        by_staat.setdefault(it.staat, []).append(it)
    blocks = ""
    for s in STATEN:
        lst = sorted(by_staat.get(s, []), key=lambda it: it.aangemaakt_at, reverse=True)
        rows = ("".join(_item_beheer(it, csrf) for it in lst) if lst
                else "<p class='muted'>—</p>")
        blocks += f"<div class='c2-sec'><h3>{_e(_STAAT_LABEL[s])} ({len(lst)})</h3>{rows}</div>"
    return f"<div class='c2-sec'><h3>Manage — all items by state</h3></div>{blocks}"


def render_backlog(st: "_Stores", csrf: str = "", username: str | None = None,
                   msg: str = "") -> str:
    """Het volledige scherm. Iedereen-ingelogd brengt in; alleen de rolvervuller beheert."""
    from nooch_village.web_base import _banner

    rec = st.records.get(WEBSITE_DEVELOPER_ROLE)
    terug = (f"<div class='c2-bar'><a href='/node?id={_e(WEBSITE_DEVELOPER_ROLE)}&tab=tools'>"
             f"← {_e(_name(rec)) if rec is not None else 'role'}</a></div>")
    kop = (f"{terug}<h1>📋 Backlog Builder</h1>"
           f"<p class='muted'>Bugs, wishes and ideas → a structured, prioritised backlog. "
           f"Prototype — the guided intake and prioritising come next.</p>")
    inhoud = ""
    if _is_beheerder(st, username):
        inhoud += _beheerder_view(st, csrf)
    inhoud += _inbrenger_view(st, csrf, username)
    main = f"<div class='c2-main'>{kop}{_banner(msg)}{inhoud}</div>"
    return _page("Backlog Builder", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
