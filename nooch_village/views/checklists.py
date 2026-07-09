"""Checklist-views — brok 5 van de cockpit2-split."""
from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import _name, _IC_CHECK
from nooch_village import org
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


def _cl_target_label(st: _Stores, item: dict) -> str:
    if item.get("target_type") == "role" and item.get("target_id"):
        r = st.records.get(item["target_id"])
        return _name(r) if r else item["target_id"]
    return "Alle leden"


def _cl_spark(item: dict) -> str:
    h = ChecklistStore.history(item, 6)
    if not h:
        return "<span class='cl-spark muted' title='nog geen historie'>—</span>"
    dots = "".join(f"<i class='{'ok' if b else 'no'}'>{'✓' if b else '✗'}</i>" for b in h)
    return f"<span class='cl-spark' title='laatste {len(h)} keer'>{dots}</span>"


def _cl_row(st: _Stores, item: dict, csrf: str) -> str:
    cid = item["id"]
    status = ChecklistStore.current_status(item)
    tgt = f"<span class='chip muted'>{_e(_cl_target_label(st, item))}</span>"
    # rapporteer ✓/✗ voor de huidige periode (U5: numerieke waarde niet meer in de UI)
    if csrf:
        rep = (f"<form method='post' action='/action' class='cl-rep'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='cid' value='{_e(cid)}'>"
               f"<input type='hidden' name='action' value='cl_report'>"
               f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
               f"<button class='cl-check ok{(' on' if status is True else '')}' type='submit' name='ok' value='1' title='check'>✓</button>"
               f"<button class='cl-check no{(' on' if status is False else '')}' type='submit' name='ok' value='0' title='geen check'>✗</button></form>")
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='cid' value='{_e(cid)}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
              f"<button class='dellink' type='submit' name='action' value='cl_remove' title='verwijderen'>✕</button></form>")
    else:
        rep = "" if status is None else (f"<span class='cl-check {'ok' if status else 'no'} on'>"
                                         f"{'✓' if status else '✗'}</span>")
        rm = ""
    danger = f"<span class='row-danger'>{rm}</span>" if rm else ""
    # Kleurcodering op rij-niveau, wederzijds uitsluitend: gemist=coral, te-doen=geel, gedaan=neutraal.
    # status is False (gemist) impliceert een rapport deze periode -> nooit tegelijk is_due (te-doen).
    if status is False:
        rowcls = " cl-attn"
    elif ChecklistStore.is_due(item):
        rowcls = " cl-todo"
    else:
        rowcls = ""
    return (f"<div class='cl-row{rowcls}'><div class='cl-main'><span class='cl-desc'>{_e(item['description'])}</span> {tgt}</div>"
            f"<div class='cl-act'>{_cl_spark(item)}<span class='cl-checks'>{rep}</span>{danger}</div></div>")


def _checklists_tab_html(st: _Stores, rec, csrf: str = "", flt: str = "due", nav: str = "") -> str:
    # flt blijft in de signatuur voor caller-compat (render_node + werkoverleg geven 'm nog door),
    # maar filtert niet meer: sinds U4 tonen we altijd de hele checklist en highlighten we de
    # te-doen items met .cl-todo. (clf-threading opruimen kan later, apart.)
    is_c = org.is_circle(rec)
    items = st.checklists.for_node(rec.id)
    base = f"/node?id={_e(rec.id)}&tab=checklists"

    shown = items   # geen filter meer: altijd de hele checklist; kleurcodering per rij (cl-todo/cl-attn)

    # groepering per cadans
    groups = ""
    for cad in CADENCES:
        sub = [i for i in shown if i.get("cadence") == cad]
        if not sub:
            continue
        groups += (f"<div class='cl-group'><h4>{_e(CADENCE_LABEL[cad])}</h4>"
                   + "".join(_cl_row(st, i, csrf) for i in sub) + "</div>")
    if not groups:
        groups = "<p class='muted'>Nog geen checklist-items.</p>"

    # toevoegen (governance-poort: alleen een al bestaande terugkerende actie)
    add = ""
    if csrf:
        if is_c:
            roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
            opts = "<option value='all'>Alle cirkelleden</option>" + "".join(
                f"<option value='role:{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
            doel = (f"<label class='att-lbl'>Doel</label><select name='doel'>{opts}</select>")
        else:
            doel = "<input type='hidden' name='doel' value='all'>"
        cadopts = "".join(f"<option value='{c}'>{_e(CADENCE_LABEL[c])}</option>" for c in CADENCES)
        add = (f"<details class='cl-add'><summary class='btn ok sm'>+ Checklist-item</summary>"
               f"<form method='post' action='/action' class='cl-addform'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='node' value='{_e(rec.id)}'>"
               f"<input type='hidden' name='next' value='{base}'>"
               f"<label class='att-lbl'>Beschrijving</label>"
               f"<input name='description' placeholder='Bijv. Facturen verstuurd' autocomplete='off'>"
               f"<label class='att-lbl'>Cadans</label><select name='cadence'>{cadopts}</select>"
               f"{doel}"
               f"<label class='cl-gate'><input type='checkbox' name='bestaand' value='1'> "
               f"Dit is een al <b>bestaande</b> terugkerende actie (geen nieuwe verwachting).</label>"
               f"<button class='btn ok sm' type='submit' name='action' value='cl_add'>Toevoegen</button>"
               f"</form></details>")

    head = (f"<div class='cl-head'><h3>Checklists</h3>{add}</div>"
            f"<p class='muted' style='font-size:.8rem'>Transparantie over terugkerend werk (pre-flight): "
            f"✓ of ✗ per periode. Nieuwe verwachtingen lopen via het roloverleg.</p>")
    return f"<div class='c2-sec'>{head}</div>{groups}"


def _cl_item_state(it: dict, done, skill) -> tuple[str, str]:
    """Bepaal de weergave-state van een checklist-item + de extra box-klasse.

    Vier onderscheidbare states (scope 1):
      done     ✓  afgevinkt
      exec     ·  uitvoerbaar (skill + payload in orde, nog niet gedraaid)
      warn     ⚠  payload onvolledig (payload_ok=False) — de checklist deugt niet
      noskill  ○  geen skill (skill=None) — een mens moet dit doen

    Fail-soft (afgesproken): een ONTBREKEND payload_ok = 'niet gevalideerd' = gewoon uitvoerbaar (·),
    NIET ongeldig. Alleen expliciet payload_ok is False → ⚠. Zo staat een oud item (geprepareerd vóór
    PR #136, zonder het veld) niet ten onrechte als onvolledig gemarkeerd — consistent met hoe het
    primitief fail-soft is op skills zonder required_payload."""
    if done:
        return "done", ""
    if not skill:
        return "noskill", " b-noskill"
    if it.get("payload_ok") is False:            # expliciet False; None/afwezig telt NIET als ongeldig
        return "warn", " b-warn"
    return "exec", ""


def _cl_fmt_payload(it: dict) -> str:
    """Compacte payload-weergave (zoals in het prototype: {sleutel: waarde}). Valt terug op query."""
    payload = it.get("payload")
    if isinstance(payload, dict) and payload:
        inner = ", ".join(f"{k}: {v}" for k, v in list(payload.items())[:4])
        return "{" + inner[:80] + "}"
    q = (it.get("query") or "").strip()
    return "{" + q[:60] + "}" if q else ""


def _cl_item_meta(state: str, skill, it: dict) -> str:
    """De meta-regel onder een checklist-item: skill-naam + payload, en per state het ⚠/○-signaal.
    ⚠ (coral) en ○ (grijs) verschillen bewust visueel — ze vragen om verschillende actie."""
    if state == "done":
        return ""                                # afgerond → geen ruis; het resultaat staat in de wall
    reason = (it.get("reason") or "").strip()
    parts = []
    if skill:
        parts.append(f"<span class='ck-skill'>{_e(str(skill))}</span>")
        pl = _cl_fmt_payload(it)
        if pl:
            parts.append(f"<span class='ck-payload'>{_e(pl)}</span>")
    if state == "warn":
        parts.append(f"<span class='ck-warn'>⚠ payload onvolledig{': ' + _e(reason) if reason else ''}</span>")
    elif state == "noskill":
        parts.append(f"<span class='ck-noskill'>○ geen skill{' · ' + _e(reason) if reason else ' · vereist mens'}</span>")
    return f"<span class='ck-meta'>{' '.join(parts)}</span>" if parts else ""


def _checklists_html(p: dict, csrf: str, pid: str, back: str, rw: bool) -> str:
    """Named checklists (Trello-stijl): titel + voortgangsbalk + items + verwijderen."""
    def hid():
        nxt = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>")

    out = ""
    for cl in (p.get("checklists") or []):
        items = cl.get("items", [])
        done = sum(1 for it in items if it.get("done"))
        tot = len(items)
        pct = round(100 * done / tot) if tot else 0
        bar = (f"<div class='ck-prog'><div class='pbar' style='flex:1'><div style='width:{pct}%'></div></div>"
               f"<span class='muted'>{pct}% ({done}/{tot})</span></div>") if tot else ""
        rows = ""
        for it in items:
            d = it.get("done")
            skill = it.get("skill")
            state, box_extra = _cl_item_state(it, d, skill)
            clitem = (f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                      f"<input type='hidden' name='item' value='{_e(it['id'])}'>")
            chk = (f"<form method='post' action='/action'>{hid()}{clitem}"
                   f"<button class='ck-box{' on' if d else ''}{box_extra}' type='submit' name='action' "
                   f"value='check_toggle'>{'✓' if d else ''}</button></form>") if rw else ("☑" if d else "☐")
            rm = (f"<form method='post' action='/action'>{hid()}{clitem}"
                  f"<button class='dellink' type='submit' name='action' value='check_remove'>✕</button></form>") if rw else ""
            txt = (f"<span class='ck-txt'><span class='{'ck-done' if d else ''}'>{_e(it['text'])}</span>"
                   f"{_cl_item_meta(state, skill, it)}</span>")
            # Stil skill-aanbod (cockpit-match): alleen als het item nog geen skill heeft. Klik = accepteren
            # (skill+payload aan het item, uitvoering door de daemon); negeren = afwijzen.
            offer = it.get("offer") if not skill else None
            offer_html = (f"<form method='post' action='/action'>{hid()}{clitem}"
                          f"<button class='btn ghost sm' type='submit' name='action' value='check_accept' "
                          f"title='skill: {_e(str((offer or {}).get('skill','')))}'>🤖 kan dit oppakken</button>"
                          f"</form>") if (rw and offer) else ""
            rows += f"<li class='ck-item'>{chk}{txt}{offer_html}{rm}</li>"
        add = (f"<form method='post' action='/action' class='ckadd'>{hid()}"
               f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
               f"<input name='text' placeholder='item toevoegen…'>"
               f"<button class='btn ok' type='submit' name='action' value='check_add'>+ item</button></form>") if rw else ""
        delc = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
                f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                f"<button class='dellink cl-del' type='submit' name='action' value='checklist_remove' "
                f"onclick=\"return confirm('Checklist verwijderen?')\">verwijderen</button></form>") if rw else ""
        out += (f"<div class='checklist'><div class='cl-head'>{_IC_CHECK}"
                f"<span class='cl-title'>{_e(cl.get('title', 'Checklist'))}</span>{delc}</div>"
                f"{bar}<ul class='clean ck-list'>{rows or '<li class=muted>nog geen items</li>'}</ul>{add}</div>")
    return out
