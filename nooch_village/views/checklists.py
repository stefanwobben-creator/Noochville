"""Checklist-views — brok 5 van de cockpit2-split."""
from __future__ import annotations

from nooch_village.projects import PREP_CHECKLIST_TITLE

import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import _name, _IC_CHECK
from nooch_village import org
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores


# DEFAULT-TITELS ZIJN GEEN NAMEN. Op productie heet 234 van de ~265 checklists "Uitvoerplan" —
# de naam die de wizard en de puls zetten, niet iets wat iemand bedacht. Die op elke kaart tonen is
# ruis met de vorm van informatie: je leest een kop die op 90% van de kaarten hetzelfde zegt.
#
# `Uitvoerplan` BLIJFT de identifier: hij gate't de Done-uitkomst, het aanbod-mechanisme, de wizard
# en de puls (`projects.PREP_CHECKLIST_TITLE`). Alleen de WEERGAVE vervalt — identifier is
# mechaniek, label is content, dezelfde scheiding als bij de verslag-voorzet.
_DEFAULT_TITELS = {PREP_CHECKLIST_TITLE.casefold(), "tasks", "checklist"}


def toon_titel(titel: str) -> str:
    """De titel zoals hij op het scherm hoort, of "" als het een default is.

    Alleen een titel die iemand ECHT zelf gaf verdient ruimte. Leeg → "", want een lege naam is
    ook geen naam."""
    t = (titel or "").strip()
    return "" if t.casefold() in _DEFAULT_TITELS else t


def _cl_target_label(st: _Stores, item: dict) -> str:
    if item.get("target_type") == "role" and item.get("target_id"):
        r = st.records.get(item["target_id"])
        return _name(r) if r else item["target_id"]
    return "All members"


def _cl_spark(item: dict) -> str:
    h = ChecklistStore.history(item, 6)
    if not h:
        return "<span class='cl-spark muted' title='no history yet'>—</span>"
    dots = "".join(f"<i class='{'ok' if b else 'no'}'>{'✓' if b else '✗'}</i>" for b in h)
    return f"<span class='cl-spark' title='last {len(h)} times'>{dots}</span>"


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
               f"<button class='cl-check no{(' on' if status is False else '')}' type='submit' name='ok' value='0' title='no check'>✗</button></form>")
        rm = (f"<form method='post' action='/action' style='display:inline'>"
              f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
              f"<input type='hidden' name='cid' value='{_e(cid)}'>"
              f"<input type='hidden' name='next' value='/node?id={_e(item['node'])}&tab=checklists'>"
              f"<button class='dellink' type='submit' name='action' value='cl_remove' title='remove'>✕</button></form>")
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
        groups = "<p class='muted'>No checklist items yet.</p>"

    # toevoegen (governance-poort: alleen een al bestaande terugkerende actie)
    add = ""
    if csrf:
        if is_c:
            roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
            opts = "<option value='all'>All circle members</option>" + "".join(
                f"<option value='role:{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
            doel = (f"<label class='att-lbl'>Target</label><select name='doel'>{opts}</select>")
        else:
            doel = "<input type='hidden' name='doel' value='all'>"
        cadopts = "".join(f"<option value='{c}'>{_e(CADENCE_LABEL[c])}</option>" for c in CADENCES)
        add = (f"<details class='cl-add'><summary class='btn ok sm'>+ Checklist item</summary>"
               f"<form method='post' action='/action' class='cl-addform'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
               f"<input type='hidden' name='node' value='{_e(rec.id)}'>"
               f"<input type='hidden' name='next' value='{base}'>"
               f"<label class='att-lbl'>Description</label>"
               f"<input name='description' placeholder='E.g. Invoices sent' autocomplete='off'>"
               f"<label class='att-lbl'>Cadence</label><select name='cadence'>{cadopts}</select>"
               f"{doel}"
               f"<label class='cl-gate'><input type='checkbox' name='bestaand' value='1'> "
               f"This is an <b>existing</b> recurring action (not a new expectation).</label>"
               f"<button class='btn ok sm' type='submit' name='action' value='cl_add'>Add</button>"
               f"</form></details>")

    head = (f"<div class='cl-head'><h3>Checklists</h3>{add}</div>"
            f"<p class='muted' style='font-size:.8rem'>Transparency about recurring work (pre-flight): "
            f"✓ or ✗ per period. New expectations go through the governance meeting.</p>")
    return f"<div class='c2-sec'>{head}</div>{groups}"


def _cl_item_state(it: dict, done, skill) -> tuple[str, str]:
    """Bepaal de weergave-state van een checklist-item + de extra box-klasse.

    Vier onderscheidbare states (scope 1):
      done     ✓  afgevinkt
      exec     ·  uitvoerbaar (skill + payload in orde, nog niet gedraaid)
      warn     ⚠  payload onvolledig (payload_ok=False) — de checklist deugt niet
      noskill  ○  geen skill (skill=None) — er is (nog) geen software voor
      human    🙋 expliciete mens-taak (planner zag vooraf: fysiek/offline) — telt niet mee
      skipped  ⤳  bewust overgeslagen door de mens — telt niet mee

    Fail-soft (afgesproken): een ONTBREKEND payload_ok = 'niet gevalideerd' = gewoon uitvoerbaar (·),
    NIET ongeldig. Alleen expliciet payload_ok is False → ⚠. Zo staat een oud item (geprepareerd vóór
    PR #136, zonder het veld) niet ten onrechte als onvolledig gemarkeerd — consistent met hoe het
    primitief fail-soft is op skills zonder required_payload."""
    if it.get("skipped"):                        # bewust overgeslagen: telt niet meer mee (n.v.t./elders)
        return "skipped", " b-skip"
    if done:
        return "done", ""
    if it.get("human_task"):                     # planner zag vooraf: alleen een mens/externe partij
        return "human", " b-human"
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
    if state == "skipped":
        why = (it.get("skip_reason") or "").strip()
        return (f"<span class='ck-meta'><span class='ck-skip'>⤳ skipped — does not count"
                f"{' · ' + _e(why) if why else ''}</span></span>")
    if state == "human":
        why = (it.get("reason") or "").strip()
        return (f"<span class='ck-meta'><span class='ck-human'>🙋 human task — does not count towards "
                f"done{' · ' + _e(why) if why else ''}</span></span>")
    reason = (it.get("reason") or "").strip()
    parts = []
    if skill:
        parts.append(f"<span class='ck-skill'>{_e(str(skill))}</span>")
        pl = _cl_fmt_payload(it)
        if pl:
            parts.append(f"<span class='ck-payload'>{_e(pl)}</span>")
    if state == "warn":
        parts.append(f"<span class='ck-warn'>⚠ payload incomplete{': ' + _e(reason) if reason else ''}</span>")
    elif state == "noskill":
        parts.append(f"<span class='ck-noskill'>○ no skill{' · ' + _e(reason) if reason else ' · needs a human'}</span>")
    return f"<span class='ck-meta'>{' '.join(parts)}</span>" if parts else ""


def _cl_resolve_row(it: dict, hid: str, clitem: str, role_opts: str) -> str:
    """De drie mens-uitkomsten op een item dat alleen een mens kan oplossen (geen skill, of een
    onvolledige payload). Zonder deze knoppen sluit de mens wel de spanning maar blijft het item open
    en het project geparkeerd — de herhaal-lus. 'Gedaan' zit al op het ✓-vakje ernaast (dat loopt via
    dezelfde resolutie-route), hier staan 'overslaan' en 'overdragen'."""
    # 'skip (n/a)' IS WEG. Hij stond naast het ✓-vakje en deed vrijwel hetzelfde: een item dat
    # niet meer hoeft, vink je af of haal je weg. Twee knoppen voor één gedachte maakt de keuze
    # zwaarder dan de handeling. De `skipped`-STAAT blijft bestaan (oude items dragen hem nog en
    # `checklist_progress` telt hem correct niet mee); alleen de knop om hem te zetten is weg.
    hand = (f"<details class='fedit'><summary class='flink'>📤 hand off</summary>"
            f"<form method='post' action='/action'>{hid}{clitem}"
            f"<select name='naar_rol'>{role_opts}</select>"
            f"<input name='reason' placeholder='done when…'>"
            f"<button class='btn sm' type='submit' name='action' value='check_handoff'>"
            f"hand off</button></form></details>") if role_opts else ""
    return f"<span class='ck-resolve'>{hand}</span>"


#: De lege checklist. "no items yet" CONSTATEERT; dit NODIGT UIT — en zegt erbij waar een eerste
#: item vandaan komt, want dat is de vraag waar iemand op vastloopt. Eigen klasse binnen de bestaande
#: .cl--familie: de andere lege staten in het systeem zijn losse <span class='muted'>-zinnen, en die
#: dragen geen ruimte of toon.
_CL_LEEG = ("<li class='cl-empty'>No actions yet. Put the first step from the meeting "
            "here — or split the end document into what still needs doing.</li>")


def _checklists_html(p: dict, csrf: str, pid: str, back: str, rw: bool, st: _Stores = None) -> str:
    """Named checklists (Trello-stijl): titel + voortgangsbalk + items + verwijderen."""
    def hid():
        nxt = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        return (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(nxt)}'>")

    from nooch_village.projects import checklist_progress
    # Rol-opties voor de overdracht: dezelfde bron als het wall-outcome-formulier (reference, don't copy).
    role_opts = ""
    if rw and st is not None:
        try:
            from nooch_village.views.feed import _wall_outcome_opts
            role_opts = _wall_outcome_opts(st)[0]
        except Exception:
            role_opts = ""
    out = ""
    for cl in (p.get("checklists") or []):
        items = cl.get("items", [])
        done, tot = checklist_progress(cl)          # overgeslagen items tellen niet mee in de noemer
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
                          f"title='skill: {_e(str((offer or {}).get('skill','')))}'>🤖 can pick this up</button>"
                          f"</form>") if (rw and offer) else ""
            # Een item dat geen enkele skill kan draaien blijft anders eeuwig open en houdt het project
            # geparkeerd. Geef de mens hier de twee uitkomsten die dat doorbreken (✓ = de derde).
            resolve = (_cl_resolve_row(it, hid(), clitem, role_opts)
                       if (rw and state in ("noskill", "warn", "human")) else "")
            unskip = (f"<form method='post' action='/action' class='emo-f'>{hid()}{clitem}"
                      f"<button class='flink' type='submit' name='action' value='check_unskip'>"
                      f"undo skip</button></form>") if (rw and state == "skipped") else ""
            rows += f"<li class='ck-item'>{chk}{txt}{offer_html}{resolve}{unskip}{rm}</li>"
        add = (f"<form method='post' action='/action' class='ckadd'>{hid()}"
               f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
               # EEN PLACEHOLDER IS EEN UITNODIGING OF EEN GRIJS VLAK. "add item…" beschrijft het
               # veld; een voorbeeld laat zien wat er in hoort en hoe fijn een item mag zijn.
               f"<input name='text' placeholder='E.g. Ask three suppliers for a sample'>"
               f"<button class='btn ok' type='submit' name='action' value='check_add'>+ item</button></form>") if rw else ""
        delc = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
                f"<input type='hidden' name='clid' value='{_e(cl['id'])}'>"
                f"<button class='dellink cl-del' type='submit' name='action' value='checklist_remove' "
                f"onclick=\"return confirm('Remove checklist?')\">remove</button></form>") if rw else ""
        _titel = toon_titel(cl.get("title", ""))
        out += (f"<div class='checklist'><div class='cl-head'>{_IC_CHECK}"
                + (f"<span class='cl-title'>{_e(_titel)}</span>" if _titel else "")
                + f"{delc}</div>"
                f"{bar}<ul class='clean ck-list'>{rows or _CL_LEEG}</ul>{add}</div>")
    return out
