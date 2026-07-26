"""Backlog Builder-views — de Notes-vervanger op de Website Developer-rol.

Prototype: datastructuur + UI, GEEN Noochie/LLM. Twee views:
- inbrenger (iedereen-ingelogd): item indienen + eigen ingediende items
- beheerder (rolvervuller Website Developer): overzicht per staat + staat/prioriteit beheren
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import WEBSITE_DEVELOPER_ROLE, md_editor, _md
from nooch_village.backlog import TYPES, DOMEINEN, STATEN, IMPACTS, EFFORTS

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

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


def _inbrenger_view(st: "_Stores", rec, csrf: str, username: str | None) -> str:
    if not csrf:
        return ""
    back = f"/node?id={rec.id}&tab=notes"
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='next' value='{_e(back)}'>")
    type_opts = "".join(f"<option value='{t}'>{_e(_vl(t))}</option>" for t in TYPES)
    dom_opts = "".join(f"<option value='{d}'>{_e(_vl(d))}</option>" for d in DOMEINEN)
    form = (f"<div class='c2-sec'><h3>Submit item</h3>"
            f"<form method='post' action='/action' class='qadd-form'>{hid}"
            f"<input name='titel' placeholder='Title…' autocomplete='off' required>"
            f"{md_editor('beschrijving', rows=4, placeholder='Description (free text)…')}"
            f"<label class='att-lbl'>Type</label><select name='type'>{type_opts}</select>"
            f"<label class='att-lbl'>Domain</label><select name='domein'>{dom_opts}</select>"
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


def _item_beheer(rec, it, csrf: str) -> str:
    back = f"/node?id={rec.id}&tab=notes"
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='next' value='{_e(back)}'>"
           f"<input type='hidden' name='bid' value='{_e(it.id)}'>")
    staat_opts = "".join(f"<option value='{s}'{' selected' if s == it.staat else ''}>"
                         f"{_e(_STAAT_LABEL[s])}</option>" for s in STATEN)
    staat_form = (f"<form method='post' action='/action' style='display:inline-block;margin-right:.6rem'>{hid}"
                  f"<select name='staat' onchange='this.form.requestSubmit()'>{staat_opts}</select>"
                  f"<button class='btn sm' type='submit' name='action' value='backlog_update_staat'>state</button></form>")
    prio_form = (f"<form method='post' action='/action' style='display:inline-block'>{hid}"
                 f"<select name='impact'>{_opts(IMPACTS, it.impact)}</select>"
                 f"<select name='effort'>{_opts(EFFORTS, it.effort)}</select>"
                 f"<button class='btn sm' type='submit' name='action' value='backlog_update_prioriteit'>priority</button></form>")
    desc = f"<div class='muted' style='font-size:.85rem'>{_md(it.beschrijving)}</div>" if it.beschrijving else ""
    return (f"<div class='accrow' style='display:block'><div><b>{_e(it.titel)}</b> {_chips(it)}</div>"
            f"{desc}<div style='margin-top:.35rem'>{staat_form}{prio_form}</div></div>")


def _beheerder_view(st: "_Stores", rec, csrf: str) -> str:
    if not csrf:
        return ""
    items = st.backlog.all()
    by_staat: dict[str, list] = {s: [] for s in STATEN}
    for it in items:
        by_staat.setdefault(it.staat, []).append(it)
    blocks = ""
    for s in STATEN:
        lst = sorted(by_staat.get(s, []), key=lambda it: it.aangemaakt_at, reverse=True)
        rows = ("".join(_item_beheer(rec, it, csrf) for it in lst) if lst
                else "<p class='muted' style='font-size:.85rem'>—</p>")
        blocks += f"<div class='c2-sec'><h3>{_e(_STAAT_LABEL[s])} ({len(lst)})</h3>{rows}</div>"
    return f"<div class='c2-sec'><h3>Manage — all items by state</h3></div>{blocks}"


def render_backlog_tab(st: "_Stores", rec, csrf: str = "", username: str | None = None) -> str:
    out = ("<div class='c2-sec'><h3>📋 Backlog Builder</h3>"
           "<p class='muted' style='font-size:.85rem'>Bugs, wishes and ideas → a structured, "
           "prioritised backlog. Prototype — Noochie help with wording and prioritising comes later.</p></div>")
    if _is_beheerder(st, username):
        out += _beheerder_view(st, rec, csrf)
    out += _inbrenger_view(st, rec, csrf, username)
    return out
