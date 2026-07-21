"""Project-views — brok 9 van de cockpit2-split."""
from __future__ import annotations

import json
import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page, _banner
from nooch_village.cockpit2_util import (
    _DS_LINK,
    _name, _initials, _age, _fmt_due, _created_full, md_editor, _md, _md_doc, _WRAPSEL_DEF,
    _link_host, _psec, _person_name, _stamp,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK,
    _IC_DESC, _IC_CLOCK, _IC_FILE, _IC_TARGET, _nav,)
from nooch_village.views.feed import _mentionables, _feed_entry_html, _wall_outcome_opts
from nooch_village.views.checklists import _checklists_html
from nooch_village import org

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

_PROJ_CHIP = {   # status -> (label, chip-kleur-modifier)
    "running": ("Actief", "green"),
    "queued": ("Wachtrij", "muted"),
    "future": ("Toekomst", "muted"),
    "blocked": ("Wacht", "coral"),
    "draft": ("Concept", "muted"),
    "done": ("Done", "green"),
}


def _proj_chip(status: str) -> str:
    lbl, mod = _PROJ_CHIP.get(status, (status, "muted"))
    return f"<span class='chip {mod}'>{_e(lbl)}</span>"


def _trekker_html(st: _Stores, p: dict) -> str:
    if p.get("agent"):
        pa = st.personas.get(p["agent"])
        return (f"<span class='person'><span class='av ai'>AI</span>"
                f"{_e((pa.name if pa else p['agent']))} <span class='muted'>(AI)</span></span>")
    if p.get("person"):
        return (f"<span class='person'><span class='av'>{_e(_initials(_person_name(st, p['person'])))}"
                f"</span>{_e(_person_name(st, p['person']))}</span>")
    return "<span class='muted'>geen trekker</span>"


# Holacracy-kernrollen (governance): doen geen uitvoerend werk → geen owner van een operationeel
# project, en dus niet in de owner-dropdown. Er is GEEN machine-vlag op het record; de seeds genereren
# ze per cirkel als '<cirkel>__<suffix>', plus de historische wortel-facilitator 'facilitator'. We
# herkennen ze aan hun DETERMINISTISCHE id-suffix (niet aan de vrije weergavenaam), expliciet en leesbaar.
_CORE_ROLE_IDS = frozenset({"facilitator"})           # wortel-facilitator draagt geen cirkel-prefix
_CORE_ROLE_SUFFIXES = ("__facilitator", "__secretary", "__circle_lead", "__circle_rep", "__shareholder")


def _is_core_role(rid: str) -> bool:
    """True voor een Holacracy-governance-kernrol (facilitator/secretary/lead-link/rep-link/shareholder)."""
    return rid in _CORE_ROLE_IDS or rid.endswith(_CORE_ROLE_SUFFIXES)


def _trekker_candidates(st: _Stores, owner: str) -> list:
    """De kandidaat-fillers (mens + persona) voor de trekker:
    - gewone rol → UITSLUITEND de fillers van die owner-ROL;
    - Individueel Initiatief ('ii:<circle>') → de members van die cirkel = de fillers van alle rollen
      die in de cirkel hangen (er is geen owner-rol om fillers op te zoeken; resolve_circle_id levert
      de cirkel uit de sentinel)."""
    if not owner:
        return []
    if owner.startswith(_II_PREFIX):
        from nooch_village.cockpit2 import resolve_circle_id
        circle = resolve_circle_id(owner, st.records)
        fillers = []
        for r in st.records.all():
            if getattr(r, "parent", None) == circle:
                fillers.extend(st.assign.fillers_of(r.id, record=r))
        return fillers
    orec = st.records.get(owner)
    return list(st.assign.fillers_of(orec.id, record=orec)) if orec is not None else []


def _trekker_options(st: _Stores, owner: str, sel_person="", sel_agent="") -> str:
    """Trekker-keuze = de mens/AI die de eigenaar 'bezetten': fillers van de owner-ROL, of — bij een
    Individueel Initiatief — de members van de cirkel (zie _trekker_candidates). Geen kandidaten →
    alleen 'geen trekker'. Zo kan een trekker nooit iemand zijn die er niet bij hoort."""
    out = ["<option value=''>— geen trekker —</option>"]
    seen = set()
    for f in _trekker_candidates(st, owner):
        if (f.type, f.id) in seen:                    # dedup: een lid kan meerdere rollen vervullen (II)
            continue
        seen.add((f.type, f.id))
        if f.type == "person":
            s = " selected" if f.id == sel_person else ""
            out.append(f"<option value='person:{_e(f.id)}'{s}>{_e(_person_name(st, f.id))}</option>")
        else:
            pa = st.personas.get(f.id)
            s = " selected" if f.id == sel_agent else ""
            out.append(f"<option value='persona:{_e(f.id)}'{s}>🤖 {_e(pa.name if pa else f.id)} (AI)</option>")
    return "".join(out)


def _owner_options(st: _Stores, sel_owner="", circle: str | None = None) -> str:
    """Rollen om een project naar te verplaatsen, GESCOPED op de cirkel waar het project hangt
    (circle = de ouder-cirkel van de owner-rol). None = dorp-breed (bv. dangling of nog ongekoppeld).
    Cirkels én Holacracy-kernrollen vallen weg (geen uitvoerend werk). De huidige owner blijft altijd
    zichtbaar-en-geselecteerd, ook als hij buiten de scope of dangling is."""
    if circle is not None:
        pool = org.roles_of(st.records.all(), circle)          # directe rollen in de cirkel (geen subcirkels)
    else:
        pool = [r for r in st.records.all() if not org.is_circle(r)]
    roles = [r for r in pool if not org.is_circle(r) and not _is_core_role(r.id)]
    roles.sort(key=lambda r: _name(r).lower())
    out, role_ids = [], {r.id for r in roles}
    if sel_owner and sel_owner not in role_ids:
        cur = st.records.get(sel_owner)
        if cur is None:                                        # dangling: bestaat niet meer
            out.append(f"<option value='{_e(sel_owner)}' selected>⚠ {_e(sel_owner)} (bestaat niet meer)</option>")
        else:                                                  # geldige owner buiten de scope/kernrol → toch tonen
            out.append(f"<option value='{_e(sel_owner)}' selected>{_e(_name(cur))}</option>")
    for r in roles:
        s = " selected" if r.id == sel_owner else ""
        out.append(f"<option value='{_e(r.id)}'{s}>{_e(_name(r))}</option>")
    return "".join(out)


_PROJ_COLS = [("Actief", "actief", ("running", "queued")), ("Wacht", "wacht", ("blocked",)),
              ("Done", "done", ("done",)), ("Toekomst", "toekomst", ("future",))]


_LABELS = {"groen": "#1F9D55", "geel": "#FFCE2E", "koraal": "#FF6B5B",
           "blauw": "#2B5BB5", "paars": "#7A5BD1", "": ""}

# Impact-pills (scope 2): klik = zetten, klik op de actieve pill = leegmaken (terug naar ongelabeld).
# Kleur-code per waarde (design-systeem, klassen .imp-pill in cockpit2_util.py): g=groen, n=grijs,
# r=rood, l=lichtgrijs. Nog gebruikt door _missie_dot (kaart-stip); de detail-view toont ze nu als
# <select> (zelfde datawaarden, alleen de weergave werd een dropdown i.p.v. pills).
_MISSIE_OPTS   = [("versterkt", "g"), ("neutraal", "n"), ("verzwakt", "r")]
_BUSINESS_OPTS = [("hoog", "g"), ("medium", "n"), ("laag", "l")]

# Effort-model: uren als canonieke opslag ({"hours": N}). Legacy enum-strings (1u/1d/2d/1w) worden LUI
# geconverteerd bij lezen — geen migratie-script. 1u=1, 1d=8, 2d=16, 1w=40 (8-urige werkdag).
_EFFORT_ENUM_HOURS = {"1u": 1, "1d": 8, "2d": 16, "1w": 40}


def _effort_hours(eff) -> int | None:
    """Effort → uren (int) of None. Nieuw: {"hours": N}. Legacy enum-string → via _EFFORT_ENUM_HOURS.
    Leeg/ontbrekend/onbekend → None (nette default, geen crash)."""
    if isinstance(eff, dict):
        h = eff.get("hours")
        return int(h) if isinstance(h, (int, float)) and h > 0 else None
    if isinstance(eff, str):
        return _EFFORT_ENUM_HOURS.get(eff)
    return None


# Auto-opslaan: onchange/onblur submit het form (zelfde patroon als de zichtbaarheid-checkbox). In de
# modal vangt wire() de submit → fetch → reopen (fragment-re-render) + toast; op de volle pagina reload.
# requestSubmit() vuurt een submit-event (zodat wire 'm ziet); .submit() is de no-requestSubmit-fallback.
_AUTOSAVE = "this.form.requestSubmit?this.form.requestSubmit():this.form.submit()"


def _impact_select(p, field: str, kind: str, opts, rw: bool, hid) -> str:
    """Impact-dropdown: zelfde select-patroon als ROL/TREKKER (.fieldform → proj_setimpact), maar
    auto-opslaan bij selectie (geen knop). Zelfde datawaarden; leeg (—) = ongelabeld. Read-only → tekst."""
    cur = p.get(field, "")
    if not rw:
        return _e(cur) if cur else "<span class='muted'>—</span>"
    options = "<option value=''>—</option>" + "".join(
        f"<option value='{_e(val)}'{' selected' if val == cur else ''}>{_e(val)}</option>" for val, _ in opts)
    return (f"<form method='post' action='/action' class='fieldform'>{hid()}"
            f"<input type='hidden' name='action' value='proj_setimpact'>"
            f"<input type='hidden' name='kind' value='{_e(kind)}'>"
            f"<select name='value' onchange='{_AUTOSAVE}'>{options}</select></form>")


def _effort_control(p, rw: bool, hid) -> str:
    """Effort als numeriek veld + uren/dagen-toggle (zelfde rij-patroon → proj_seteffort). Auto-opslaan:
    de toggle bij selectie (onchange), het getal bij blur (onblur) — geen knop. Een veelvoud van 8 uur
    toont standaard in dagen. Leeg/ontbrekend → geen getal, default uren. Read-only → tekst."""
    hours = _effort_hours(p.get("effort"))
    if not rw:
        if not hours:
            return "<span class='muted'>—</span>"
        return _e(f"{hours // 8} dagen" if hours % 8 == 0 else f"{hours} uren")
    if hours and hours % 8 == 0:
        num, unit = hours // 8, "dagen"
    elif hours:
        num, unit = hours, "uren"
    else:
        num, unit = "", "uren"
    units = "".join(f"<option value='{u}'{' selected' if u == unit else ''}>{u}</option>" for u in ("uren", "dagen"))
    return (f"<form method='post' action='/action' class='fieldform eff'>{hid()}"
            f"<input type='hidden' name='action' value='proj_seteffort'>"
            f"<input type='number' name='number' value='{num}' min='0' step='1' placeholder='0' onblur='{_AUTOSAVE}'>"
            f"<select name='unit' onchange='{_AUTOSAVE}'>{units}</select></form>")


def _missie_dot(p) -> str:
    """Kleine missie-impact-kleurstip voor de bordkaart (geen tekst/pills): groen (versterkt) / grijs
    (neutraal) / rood (verzwakt). Ongelabeld = geen stip. Business-impact staat bewust NIET op de kaart."""
    col = dict(_MISSIE_OPTS).get(p.get("missie_impact", ""))
    if not col:
        return ""
    return f"<span class='mdot {col}' title='Missie-impact: {_e(p['missie_impact'])}'></span>"


def _verzwakt_block(p, hid, rw: bool) -> str:
    """Signaal-infoblok bij missie_impact=verzwakt (géén blokkade — statuswissels blijven mogelijk). Toont
    de boodschap + een knop om het als spanning te agenderen in het werkoverleg van de cirkel (bewerkbaar)."""
    btn = ""
    if rw:
        btn = (f"<form method='post' action='/action' class='vz-form'>{hid()}"
               f"<button class='btn ok sm' type='submit' name='action' value='proj_agendeer_verzwakt'>"
               f"Agendeer in werkoverleg</button></form>")
    return (f"<div class='vzblock'>"
            f"<div class='vz-h'>Missie verzwakt. Jij besluit als rolvervuller.</div>"
            f"<div class='vz-t'>Wil je dit als spanning agenderen in het werkoverleg?</div>{btn}</div>")


def _proj_progress(p: dict):
    items = [it for cl in (p.get("checklists") or []) for it in cl.get("items", [])]
    if not items:
        return None
    done = sum(1 for it in items if it.get("done"))
    return done, len(items), round(100 * done / len(items))


def _due_overdue(due: str) -> bool:
    """Is de deadline (ISO 'YYYY-MM-DD') verstreken (vóór vandaag)?"""
    if not due:
        return False
    import datetime
    try:
        return datetime.date.fromisoformat(due) < datetime.date.today()
    except Exception:
        return False


def _progress_badge(p: dict) -> str:
    pr = _proj_progress(p)
    if not pr:
        return ""
    done, total, pct = pr
    return (f"<div class='pbadge' title='{done}/{total}'>"
            f"<div class='pbar'><div style='width:{pct}%'></div></div>"
            f"<span>{pct}%</span></div>")


def _scope_text(p) -> str:
    scope = p.get("scope")
    if isinstance(scope, dict):
        return " · ".join(f"{k}: {v}" for k, v in scope.items())
    return str(scope or "—")


def _proj_card(st: _Stores, p: dict, csrf_token: str, back: str) -> str:
    pid = p["id"]
    href = f"/project?pid={_e(pid)}&back={urllib.parse.quote(back, safe='')}"
    verz = " verzwakt" if p.get("missie_impact") == "verzwakt" else ""   # rode rand = signaal, geen blokkade
    bar = ""
    if p.get("label") in _LABELS and _LABELS.get(p.get("label")):
        bar = f"<div class='clabel' style='background:{_LABELS[p['label']]}'></div>"
    meta = (f"<div class='muted' style='font-size:.72rem;margin-top:.25rem'>"
            f"{_trekker_html(st, p)} · {_e(_age(p.get('created_at')))}</div>")
    inner = f"{bar}<div class='ptitle'>{_missie_dot(p)}{_e(_scope_text(p))}</div>{meta}{_progress_badge(p)}"
    if not csrf_token:
        # Publiek/alleen-lezen: er is geen modal-JS, dus de kaart moet zelf navigeren.
        # /project redirect server-side naar /login als de bezoeker niet is ingelogd —
        # het detail blijft dus achter login, maar de kaart is niet langer een dode div.
        return (f"<a class='card pcard{verz}' href='{_e(href)}' "
                f"style='display:block;text-decoration:none;color:inherit'>{inner}</a>")
    return (f"<div class='card pcard{verz}' data-pid='{_e(pid)}' data-href='{href}' draggable=\"true\">"
            f"{inner}</div>")


def _quickadd(owner: str, col: str, csrf_token: str, back: str, trekker: str = "") -> str:
    """Trello-stijl '+ kaart toevoegen': klap open → vol-breed invoerveld bovenaan, knop eronder.
    `trekker` (person:<id>/persona:<id>) wordt voorgevuld bij groeperen per persoon."""
    if not csrf_token or col == "done":
        return ""
    trek = f"<input type='hidden' name='trekker' value='{_e(trekker)}'>" if trekker else ""
    return (
        f"<details class='qadd'><summary>+ project toevoegen</summary>"
        f"<form method='post' action='/action' class='qadd-form'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='owner' value='{_e(owner)}'>"
        f"<input type='hidden' name='col' value='{_e(col)}'>"
        f"<input type='hidden' name='next' value='{_e(back)}'>{trek}"
        f"<textarea name='scope' rows='2' placeholder='Titel van het project…' aria-label='nieuw project'></textarea>"
        f"<textarea name='done_when' rows='2' required "
        f"placeholder='Waar herken je aan dat dit klaar is?' aria-label='done-when'></textarea>"
        f"<div class='qadd-row'>"
        f"<button class='btn ok' type='submit' name='action' value='proj_add'>Project toevoegen</button>"
        f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
        f"aria-label='annuleren'>✕</button></div>"
        f"</form></details>")


def _inline_add_project(st: _Stores, rec, csrf_token: str, back: str, username: str | None = None) -> str:
    """Universele inline '+ project' (één patroon, geen aparte modal). Op een cirkel kies je de rol;
    op een rol staat de eigenaar vast. Dekt ook lege rollen/cirkels die per-kolom-quickadd mist."""
    if not csrf_token:
        return ""
    # standaard-trekker = de ingelogde gebruiker (guest/onbekend → geen voorselectie)
    me = st.people.by_email(username) if username and username != "guest" else None
    if org.is_circle(rec):
        roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
        ro = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
        # Individueel Initiatief: een project oppakken zónder rol, direct onder de cirkel.
        ii_opt = f"<option value='{_II_PREFIX}{_e(rec.id)}'>Individueel Initiatief (geen rol)</option>"
        owner_field = (f"<label class='att-lbl'>Rol</label>"
                       f"<select name='owner'>{ro}{ii_opt}</select>")
    else:
        owner_field = f"<input type='hidden' name='owner' value='{_e(rec.id)}'>"
    return (
        f"<details class='qadd qadd-top'><summary>+ project</summary>"
        f"<form method='post' action='/action' class='qadd-form'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='next' value='{_e(back)}'>"
        f"<textarea name='scope' rows='2' placeholder='Te bereiken uitkomst…' aria-label='nieuw project'></textarea>"
        f"<textarea name='done_when' rows='2' required "
        f"placeholder='Waar herken je aan dat dit klaar is?' aria-label='done-when'></textarea>"
        f"{owner_field}"
        f"<label class='att-lbl'>Status</label><select name='col'>"
        f"<option value='actief'>Actief</option><option value='wacht'>Wacht</option>"
        f"<option value='toekomst'>Toekomst</option></select>"
        f"<label class='att-lbl'>Trekker (persoon of AI)</label><select name='trekker'>"
        f"{_trekker_options(st, '' if org.is_circle(rec) else rec.id)}</select>"
        f"<div class='qadd-row'><button class='btn ok' type='submit' name='action' value='proj_add'>"
        f"Project toevoegen</button></div></form></details>")


def _wizard_addlink(rec, csrf_token: str) -> str:
    """De enige 'project toevoegen'-ingang: opent de geleide wizard in de modal-overlay (js-modal),
    net als de projectkaarten. Op een rol wordt die rol voorgeselecteerd; op een cirkel kiest de
    wizard zelf de rol. Zonder JS valt de link terug op de volledige wizard-pagina."""
    if not csrf_token:
        return ""
    href = "/project/nieuw"
    if not org.is_circle(rec):
        href += f"?role={_e(rec.id)}"
    return (f"<a class='addlink js-modal' href='{href}' data-href='{href}'>"
            f"＋ project toevoegen</a>")


def _columns_html(st: _Stores, items: list, add_owner: str, add_trekker: str,
                  csrf_token: str, back: str, quickadd: bool) -> str:
    cols = ""
    for label, key, statuses in _PROJ_COLS:
        its = [p for p in items if p.get("status") in statuses]
        its.sort(key=lambda p: -(p.get("created_at") or 0))
        body = "".join(_proj_card(st, p, csrf_token, back) for p in its)
        qa = _quickadd(add_owner, key, csrf_token, back, trekker=add_trekker) if quickadd else ""
        cols += (f"<div class='pcol' data-to='{key}'>"
                 f"<div class='pcol-h'>{_e(label)} ({len(its)})</div>"
                 f"<div class='pcol-scroll'>{body}</div>{qa}</div>")
    return f"<div class='pboard'>{cols}</div>"


def _drag_script(csrf_token: str, back: str) -> str:
    if not csrf_token:
        return ""
    return (
        "<script>(function(){"
        f"var csrf={json.dumps(csrf_token)},next={json.dumps(back)},pid=null;"
        # Drag-drop = volledige page-reload → scrollpositie herstellen op load (verticaal via het
        # window, horizontaal per .pboard-swimlane). Eenmalig: lezen-en-wissen uit sessionStorage.
        "try{var _ss=JSON.parse(sessionStorage.getItem('__nvscroll')||'null');if(_ss){"
        "sessionStorage.removeItem('__nvscroll');requestAnimationFrame(function(){"
        "window.scrollTo(_ss.x||0,_ss.y||0);var _bs=document.querySelectorAll('.pboard');"
        "(_ss.b||[]).forEach(function(sl,i){if(_bs[i])_bs[i].scrollLeft=sl;});});}}catch(e){}"
        "document.querySelectorAll('.pcard').forEach(function(c){"
        "c.addEventListener('dragstart',function(e){pid=c.getAttribute('data-pid');window.__pdrag=true;"
        "e.dataTransfer.effectAllowed='move';c.style.opacity='.5';});"
        "c.addEventListener('dragend',function(){c.style.opacity='';setTimeout(function(){window.__pdrag=false;},60);});});"
        "document.querySelectorAll('.pcol[data-to]').forEach(function(col){"
        "col.addEventListener('dragover',function(e){e.preventDefault();col.classList.add('over');});"
        "col.addEventListener('dragleave',function(){col.classList.remove('over');});"
        "col.addEventListener('drop',function(e){e.preventDefault();col.classList.remove('over');"
        "if(!pid)return;var to=col.getAttribute('data-to');"
        "var f=document.createElement('form');f.method='post';f.action='/action';"
        "function a(n,v){var i=document.createElement('input');i.type='hidden';i.name=n;i.value=v;f.appendChild(i);}"
        "a('csrf',csrf);a('pid',pid);a('next',next);"
        "if(to==='done'){a('action','proj_done');}else{a('action','proj_status');a('to',to);}"
        # Verticale (window) + horizontale (elke .pboard) scrollpositie bewaren vóór de reload.
        "try{var _bs=document.querySelectorAll('.pboard');"
        "sessionStorage.setItem('__nvscroll',JSON.stringify({x:window.scrollX,y:window.scrollY,"
        "b:[].map.call(_bs,function(b){return b.scrollLeft;})}));}catch(e){}"
        "document.body.appendChild(f);f.submit();});});})();</script>")


_II_PREFIX = "ii:"   # Individual Initiative-pseudo-eigenaar per cirkel: 'ii:<circle_id>'


def _modal_html(mentions_json: str = "[]") -> str:
    """Herbruikbare detail-overlay (modal): klik op een kaart → haalt het fragment op en toont het;
    formulieren erin posten via fetch en verversen alleen de overlay. Val-terug: zonder JS navigeert
    de kaart-link naar de volledige /project-pagina. Bedoeld als standaard-patroon (ook kenniskaartjes)."""
    return (
        "<div id='ovl' class='ovl' style='display:none'><div class='ovl-box'>"
        "<button type='button' class='ovl-x' aria-label='sluiten'>✕</button>"
        "<div id='ovl-body'></div></div></div>"
        "<script>(function(){"
        "var ov=document.getElementById('ovl'),bd=document.getElementById('ovl-body'),last=null,dirty=false;"
        # De wizard-flow draait op eigen fetch (buiten wire()); zo kan hij het bord tóch laten verversen
        # bij het sluiten van de modal nadat er een project is aangemaakt.
        "window.__ovlDirty=function(){dirty=true;};"
        f"window.__mentions={mentions_json};"
        # wrapSel MOET hier (guarded) staan: de modal voegt fragmenten in via innerHTML, en een <script>
        # in een fragment (zoals de meegedragen editor-JS) draait dan niet — zónder deze definitie doen
        # de WYSIWYG-knoppen in de modal niets. Guarded → geen dubbele definitie op de volle pagina.
        f"{_WRAPSEL_DEF}"
        "function mentionWire(t){var box=null;function close(){if(box){box.remove();box=null;}}"
        "t.addEventListener('input',function(){var v=t.value.slice(0,t.selectionStart);"
        "var m=v.match(/@([^@\\n]*)$/);close();if(!m)return;var q=m[1].toLowerCase();"
        "var hits=(window.__mentions||[]).filter(function(x){return x.l.toLowerCase().indexOf(q)===0;}).slice(0,6);"
        "if(!hits.length)return;box=document.createElement('div');box.className='mention-pop';"
        "hits.forEach(function(h){var b=document.createElement('button');b.type='button';b.className='mention-it';"
        "b.textContent='@'+h.l;b.addEventListener('mousedown',function(ev){ev.preventDefault();"
        "var s=t.value,c=t.selectionStart;var pre=s.slice(0,c).replace(/@([^@\\n]*)$/,'@'+h.l+' ');"
        "t.value=pre+s.slice(c);t.focus();t.selectionStart=t.selectionEnd=pre.length;close();});box.appendChild(b);});"
        "t.parentNode.style.position='relative';t.parentNode.appendChild(box);});"
        "t.addEventListener('blur',function(){setTimeout(close,200);});}"
        "window.emoFilter=function(inp){var q=inp.value.toLowerCase();"
        "inp.parentNode.querySelectorAll('.emo-f').forEach(function(f){"
        "var k=f.getAttribute('data-k')||'';f.style.display=(!q||k.indexOf(q)>-1)?'':'none';});};"
        "function frag(u){return u+(u.indexOf('?')>-1?'&':'?')+'fragment=1';}"
        "function openCard(u,push){var wasClosed=(ov.style.display==='none'||!ov.style.display);last=u;"
        "fetch(frag(u)).then(function(r){return r.text();}).then(function(h){bd.innerHTML=h;ov.style.display='flex';"
        # Fragmenten die een eigen flow meedragen (de project-wizard) markeren hun <script> met
        # data-modal-run; innerHTML voert scripts niet uit, dus vervangen we ze door verse elementen.
        "bd.querySelectorAll('script[data-modal-run]').forEach(function(o){var s=document.createElement('script');"
        "for(var i=0;i<o.attributes.length;i++){s.setAttribute(o.attributes[i].name,o.attributes[i].value);}"
        "s.textContent=o.textContent;o.parentNode.replaceChild(s,o);});"
        "window.__noclose=!!bd.querySelector('[data-noclose]');"
        "var xb=document.querySelector('.ovl-x');if(xb)xb.style.display=window.__noclose?'none':'';wire();"
        # URL-sync: alleen voor project-kaarten. Bij de eerste opening zet de vorige (bord-)entry op
        # de back=<cirkel-url> die de kaart meegeeft (zonder oude msg=), dan pushState /project?pid=.
        "try{var pm=u.match(/[?&]pid=([^&]+)/);"
        "if(push!==false&&pm&&u.indexOf('/project')===0){var cu='/project?pid='+pm[1];"
        "if(wasClosed){var bk=(u.match(/[?&]back=([^&]+)/)||[])[1];"
        "if(bk){history.replaceState(history.state,'',decodeURIComponent(bk));}"
        "history.pushState({card:pm[1]},'',cu);}else{history.replaceState({card:pm[1]},'',cu);}}}catch(e){}"
        "});}"
        "function reopen(){if(last)openCard(last,false);}"  # verversen na actie: geen nieuwe history-entry
        "function shut(){if(history.state&&history.state.card){history.back();return;}"  # pushed kaart → pop naar bord-URL
        "ov.style.display='none';bd.innerHTML='';if(dirty){dirty=false;location.reload();}}"
        # back-knop / gepopte kaart-entry: sluit de modal, herstel de bord-URL (browser deed dat al).
        "window.addEventListener('popstate',function(){if(ov.style.display!=='none'){"
        "ov.style.display='none';bd.innerHTML='';if(dirty){dirty=false;location.reload();}}});"
        "function confetti(){var c=['#2e7d32','#ef6c5a','#f6c244','#7bb661'];for(var i=0;i<70;i++){"
        "var d=document.createElement('div');d.className='cfetti';d.style.left=(Math.random()*100)+'vw';"
        "d.style.background=c[i%4];d.style.animationDelay=(Math.random()*0.4)+'s';document.body.appendChild(d);"
        "(function(x){setTimeout(function(){x.remove();},2400);})(d);}}"
        "function toast(t){var d=document.createElement('div');d.className='c2-toast';d.textContent=t;"
        "document.body.appendChild(d);setTimeout(function(){d.classList.add('show');},10);"
        "setTimeout(function(){d.classList.remove('show');},1600);setTimeout(function(){d.remove();},2000);}"
        "function wire(){bd.querySelectorAll('form').forEach(function(f){f.addEventListener('submit',function(e){"
        "e.preventDefault();dirty=true;var act=(e.submitter&&e.submitter.value)||'';var opts;"
        "if(f.classList.contains('filepost')){opts={method:'POST',body:new FormData(f)};}"
        "else{var data=new URLSearchParams(new FormData(f));"
        "if(e.submitter&&e.submitter.name){data.set(e.submitter.name,e.submitter.value);}opts={method:'POST',body:data};}"
        "fetch('/action',opts).then(function(resp){"
        # response.ok-poort (generiek voor ELKE modal-actie, incl. de auto-opslaan-controls): een 413
        # (bestand te groot) of elke andere niet-2xx toont de server-melding en NOOIT '✓ opgeslagen'.
        "if(!resp.ok){resp.text().then(function(t){reopen();toast('\\u26a0 '+(((t||'').trim()||'niet opgeslagen').slice(0,90)));});return;}"
        "if(act==='wo_close'||act==='rov2_end'){confetti();setTimeout(shut,700);}"
        "else if(act==='proj_delete'||act==='proj_archive'||act==='proj_add'){shut();}"
        "else{var dr=f.getAttribute('data-reopen');if(dr){last=dr;}reopen();toast('\\u2713 opgeslagen');}})"
        # netwerk-foutpad (geen response): melding + best-effort revert door het fragment te herladen.
        ".catch(function(){reopen();toast('\\u26a0 niet opgeslagen');});});});"
        "bd.querySelectorAll('textarea').forEach(mentionWire);"
        # wall scrollt naar het laatste bericht: bij openen én na elke actie (reopen()→wire()), scoped op bd
        "var ws=bd.querySelector('.wall-scroll');if(ws){requestAnimationFrame(function(){ws.scrollTop=0;});}"
        "bd.querySelectorAll('a.js-modal[data-href]').forEach(function(a){"
        "a.addEventListener('click',function(e){e.preventDefault();openCard(a.getAttribute('data-href'));});});"
        "var mems=bd.querySelector('.wo-mems');if(mems){var rows=[].slice.call(mems.querySelectorAll('.wo-mem')),sel=0;"
        "function paint(){rows.forEach(function(r,i){r.classList.toggle('sel',i===sel);});}if(rows.length)paint();"
        "mems.addEventListener('keydown',function(e){if(e.key==='ArrowDown'){sel=Math.min(rows.length-1,sel+1);paint();e.preventDefault();}"
        "else if(e.key==='ArrowUp'){sel=Math.max(0,sel-1);paint();e.preventDefault();}"
        "else if(e.key==='v'||e.key==='Enter'){var b=rows[sel]&&rows[sel].querySelector('.cl-check.ok');if(b)b.click();}"
        "else if(e.key==='x'){var b=rows[sel]&&rows[sel].querySelector('.cl-check.no');if(b)b.click();}});mems.focus();}"
        # Projectenbord IN de modal: kaartjes slepen (fetch + reopen) en klik -> projectdetails.
        "var dcsrf=(bd.querySelector(\"input[name=csrf]\")||{}).value||'';"
        "bd.querySelectorAll('.pcard[data-pid]').forEach(function(c){"
        "c.setAttribute('draggable','true');"
        "c.addEventListener('dragstart',function(e){window.__pdrag=true;e.dataTransfer.setData('text',c.getAttribute('data-pid'));"
        "e.dataTransfer.effectAllowed='move';c.style.opacity='.5';});"
        "c.addEventListener('dragend',function(){c.style.opacity='';setTimeout(function(){window.__pdrag=false;},60);});});"
        "bd.querySelectorAll('.pcol[data-to]').forEach(function(col){"
        "col.addEventListener('dragover',function(e){e.preventDefault();col.classList.add('over');});"
        "col.addEventListener('dragleave',function(){col.classList.remove('over');});"
        "col.addEventListener('drop',function(e){e.preventDefault();col.classList.remove('over');"
        "var pid=e.dataTransfer.getData('text');if(!pid)return;var to=col.getAttribute('data-to');"
        "var d=new URLSearchParams();d.set('csrf',dcsrf);d.set('pid',pid);d.set('next','/');"
        "if(to==='done'){d.set('action','proj_done');}else{d.set('action','proj_status');d.set('to',to);}"
        # response.ok-poort (zoals wire()): een niet-2xx toont de server-melding, nooit '✓ verplaatst'.
        "fetch('/action',{method:'POST',body:d}).then(function(resp){"
        "if(!resp.ok){resp.text().then(function(t){reopen();toast('\\u26a0 '+(((t||'').trim()||'niet verplaatst').slice(0,90)));});return;}"
        "reopen();toast('\\u2713 verplaatst');})"
        ".catch(function(){reopen();toast('\\u26a0 niet verplaatst');});});});"
        "bd.querySelectorAll('.pcard[data-href]').forEach(function(c){"
        "c.addEventListener('click',function(e){if(window.__pdrag)return;e.preventDefault();"
        "var href=c.getAttribute('data-href');"
        "if(last&&last.indexOf('/werkoverleg')>-1){"
        "href=href.replace(/[?&]back=[^&]*/,'');"
        "href+=(href.indexOf('?')>-1?'&':'?')+'back='+encodeURIComponent(last);}"
        "openCard(href);});});"
        "}"
        "document.querySelectorAll('.pcard[data-href],a.js-modal[data-href]').forEach(function(c){"
        "c.addEventListener('click',function(e){if(window.__pdrag)return;e.preventDefault();"
        "openCard(c.getAttribute('data-href'));});});"
        "ov.addEventListener('click',function(e){if(e.target===ov&&!window.__noclose)shut();});"
        "document.querySelector('.ovl-x').addEventListener('click',function(){if(!window.__noclose)shut();});"
        "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&ov.style.display!=='none'&&!window.__noclose)shut();});"
        "})();</script>")


def _group_meta(st: _Stores, p: dict, mode: str, node_owner: str):
    """(gid, sorteersleutel, label, add_owner, add_trekker) voor groeperen per persoon/rol."""
    owner = p.get("owner") or ""
    if mode == "rol":
        if owner.startswith(_II_PREFIX):
            return (("ii", owner), "zzz", "Individueel Initiatief", owner, "")
        orec = st.records.get(owner)
        if orec is None and owner:
            # dangling: de eigenaar-rol bestaat niet meer — maak dat zichtbaar i.p.v. stil "—"
            return (("rol", owner), "zzz_" + owner.lower(),
                    f"⚠ {owner} (rol bestaat niet meer)", owner, "")
        nm = _name(orec) if orec else (owner or "—")
        return (("rol", owner), nm.lower(), nm, owner, "")
    if p.get("agent"):
        pa = st.personas.get(p["agent"])
        return (("persona", p["agent"]), "1", f"🤖 {(pa.name if pa else p['agent'])} (AI)",
                node_owner, f"persona:{p['agent']}")
    if p.get("person"):
        nm = _person_name(st, p["person"])
        return (("person", p["person"]), "0_" + nm.lower(), nm, node_owner, f"person:{p['person']}")
    return (("none",), "2", "Geen trekker", node_owner, "")


def _projects_board(st: _Stores, projs: list, owner: str, csrf_token: str, back: str,
                    group: str = "persoon", quickadd: bool = True) -> str:
    """Swimlanes per groep — alleen NIET-lege lanes (lege boards zijn ruis). Lege return → ''."""
    mode = group if group in ("persoon", "rol") else "persoon"
    groups: dict = {}
    for p in projs:
        gid, sk, label, ao, at = _group_meta(st, p, mode, owner)
        g = groups.setdefault(gid, {"sk": sk, "label": label, "items": [], "ao": ao, "at": at})
        g["items"].append(p)
    if not groups:
        return ""
    board = ""
    for gid, g in sorted(groups.items(), key=lambda kv: kv[1]["sk"]):
        board += (f"<div class='swim'><div class='swim-h'>{_e(g['label'])} ({len(g['items'])})</div>"
                  f"{_columns_html(st, g['items'], g['ao'], g['at'], csrf_token, back, quickadd=quickadd)}"
                  f"</div>")
    return board + _drag_script(csrf_token, back)


def _archived_html(st: _Stores, archived: list, csrf_token: str, back: str) -> str:
    if not archived:
        return ""
    rows = ""
    for p in archived:
        scope = p.get("scope")
        if isinstance(scope, dict):
            scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
        ctrl = ""
        if csrf_token:
            ctrl = (
                f" <form method='post' action='/action' style='display:inline'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(p['id'])}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='btn' type='submit' name='action' value='proj_unarchive'>herstellen</button>"
                f"<button type='submit' name='action' value='proj_delete' class='dellink' "
                f"onclick=\"return confirm('Definitief verwijderen?')\">verwijderen</button></form>")
        rows += f"<li class='muted'>{_e(str(scope or '—'))}{ctrl}</li>"
    return (f"<details class='box-details' style='margin-top:.6rem'><summary>🗄 Gearchiveerd ({len(archived)})</summary>"
            f"<ul class='clean'>{rows}</ul></details>")




def _drafts_html(st: _Stores, drafts: list, csrf_token: str, back: str) -> str:
    """Concept-projecten (status draft) die op akkoord wachten: goedkeuren → op het bord,
    verwerpen → weg. Onzichtbaar als er geen drafts zijn."""
    if not drafts:
        return ""
    rows = ""
    for p in drafts:
        scope = p.get("scope")
        if isinstance(scope, dict):
            scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
        trekker = _trekker_html(st, p)
        ctrl = ""
        if csrf_token:
            base = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='pid' value='{_e(p['id'])}'>"
                    f"<input type='hidden' name='next' value='{_e(back)}'>")
            ctrl = (
                f" <form method='post' action='/action' style='display:inline'>{base}"
                f"<button class='btn ok sm' type='submit' name='action' value='proj_approve'>goedkeuren</button>"
                f"</form> <form method='post' action='/action' style='display:inline'>{base}"
                f"<button class='dellink' type='submit' name='action' value='proj_discard' "
                f"onclick=\"return confirm('Concept verwerpen?')\">verwerpen</button></form>")
        rows += (f"<li>{_e(str(scope or '—'))} <span class='muted'>· {trekker}</span>{ctrl}</li>")
    return (f"<details class='box-details' open style='margin:.6rem 0'><summary>📝 Concepten — wachten op akkoord "
            f"({len(drafts)})</summary><ul class='clean'>{rows}</ul></details>")


def _orphans_html(st: _Stores, orphans: list, csrf_token: str, back: str) -> str:
    """Wees-projecten: hun eigenaar-rol bestaat niet meer, dus ze vallen door alle bordfilters
    en zijn anders onzichtbaar. Hier kun je ze opnieuw aan een rol koppelen, archiveren of wissen."""
    if not orphans:
        return ""
    rows = ""
    for p in orphans:
        scope = p.get("scope")
        if isinstance(scope, dict):
            scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
        ghost = _e(p.get("owner") or "?")
        ctrl = ""
        if csrf_token:
            base = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                    f"<input type='hidden' name='pid' value='{_e(p['id'])}'>"
                    f"<input type='hidden' name='next' value='{_e(back)}'>")
            ctrl = (
                f" <form method='post' action='/action' style='display:inline'>{base}"
                f"<select name='owner'>{_owner_options(st)}</select>"
                f"<button class='btn sm' type='submit' name='action' value='proj_setowner'>koppel aan rol</button>"
                f"</form> <form method='post' action='/action' style='display:inline'>{base}"
                f"<button class='btn sm' type='submit' name='action' value='proj_archive'>archiveer</button>"
                f"<button class='dellink' type='submit' name='action' value='proj_delete' "
                f"onclick=\"return confirm('Definitief verwijderen?')\">verwijder</button></form>")
        rows += (f"<li><span class='chip coral-solid'>wees</span> {_e(str(scope or '—'))} "
                 f"<span class='muted'>· verloren eigenaar: {ghost}</span>{ctrl}</li>")
    return (f"<div class='c2-sec'><h3>⚠ Wees-projecten ({len(orphans)})</h3>"
            f"<p class='muted' style='font-size:.8rem'>Deze projecten verwijzen naar een rol die "
            f"niet meer bestaat. Koppel ze aan een bestaande rol of ruim ze op.</p>"
            f"<ul class='clean'>{rows}</ul></div>")


def _projects_tab_html(st: _Stores, rec, csrf_token: str, group: str = "", add: bool = True,
                       username: str | None = None) -> str:
    allp = st.projects.all()
    back_base = f"/node?id={rec.id}&tab=projects"

    addlink = _wizard_addlink(rec, csrf_token) if add else ""

    if not org.is_circle(rec):
        # ROL: eigen projecten, gegroepeerd per persoon (de doener). Lege lanes tonen we niet.
        mine = [p for p in allp if p.get("owner") == rec.id and not p.get("archived")]
        projs = [p for p in mine if p.get("status") != "draft"]
        drafts = [p for p in mine if p.get("status") == "draft"]
        archived = [p for p in allp if p.get("owner") == rec.id and p.get("archived")]
        board = _projects_board(st, projs, rec.id, csrf_token, back_base, "persoon", quickadd=add)
        if not board:
            board = ("<p class='muted'>Nog geen projecten. Voeg er een toe met ＋ project toevoegen.</p>" if add
                     else "<p class='muted'>Nog geen projecten.</p>")
        head = (f"<div style='margin-bottom:1rem'>"
                f"<h3 style='margin:0;display:inline'>Projecten ({len(projs)})</h3> &nbsp; {addlink}</div>")
        return (f"<div class='c2-sec'>{head}{_drafts_html(st, drafts, csrf_token, back_base)}"
                f"{board}{_archived_html(st, archived, csrf_token, back_base)}</div>")

    # CIRKEL: doet zelf geen uitvoerend werk. Toont projecten van haar DIRECTE rollen +
    # Individual Initiative. Lege lanes tonen we niet; subcirkels = eigen bord (niet aggregeren).
    g = group if group in ("persoon", "rol") else "rol"
    direct = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    rids = {r.id for r in direct}
    ii = f"{_II_PREFIX}{rec.id}"
    mine = [p for p in allp if (p.get("owner") in rids or p.get("owner") == ii) and not p.get("archived")]
    projs = [p for p in mine if p.get("status") != "draft"]
    drafts = [p for p in mine if p.get("status") == "draft"]
    back = f"{back_base}&group={g}"
    board = _projects_board(st, projs, rec.id, csrf_token, back, g, quickadd=add)
    if not board:
        board = ("<p class='muted'>Nog geen projecten. Voeg er een toe met ＋ project toevoegen.</p>" if add
                 else "<p class='muted'>Nog geen projecten.</p>")
    subs = sorted(org.subcircles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    sub_html = ""
    if subs:
        lis = "".join(f"<li><a href='/node?id={_e(s.id)}&tab=projects'>{_e(_name(s))}</a> "
                      f"<span class='muted'>→ eigen projectenbord</span></li>" for s in subs)
        sub_html = (f"<div class='c2-sec'><h3>Subcirkels</h3>"
                    f"<p class='muted' style='font-size:.8rem'>Een subcirkel heeft een eigen "
                    f"projectenbord.</p><ul class='clean'>{lis}</ul></div>")
    on = lambda v: " on" if g == v else ""
    switch = (f"<div class='vswitch'>Groeperen: "
              f"<a class='vbtn{on('rol')}' href='{back_base}&group=rol'>per rol</a>"
              f"<a class='vbtn{on('persoon')}' href='{back_base}&group=persoon'>per persoon</a></div>")
    head = (f"<div style='display:flex;align-items:center;justify-content:space-between;"
            f"flex-wrap:wrap;gap:.6rem;margin-bottom:1rem'>"
            f"<div><h3 style='margin:0;display:inline'>Projecten ({len(projs)})</h3> &nbsp; {addlink}</div>"
            f"{switch}</div>")
    # Wees-projecten (verloren eigenaar) tonen we op de wortelcirkel: van daaruit altijd bereikbaar.
    orphans_html = ""
    roots = {r.id for r in org.roots(st.records.all())}
    if rec.id in roots:
        orphans = [p for p in allp if not p.get("archived")
                   and (o := p.get("owner")) and not o.startswith(_II_PREFIX)
                   and st.records.get(o) is None]
        orphans_html = _orphans_html(st, orphans, csrf_token, back_base)
    return (f"<div class='c2-sec'>{head}{_drafts_html(st, drafts, csrf_token, back)}"
            f"{board}{sub_html}</div>{orphans_html}")


def _person_projects_tab_html(st: _Stores, filler_type: str, pid: str, csrf_token: str = "") -> str:
    """Aggregatie-lens voor de persoon-view: DEZELFDE kanban-component als op cirkel/rol-niveau
    (_projects_board), gefilterd op de projecten waarvan de owner een rol is die deze filler vervult.
    BRON VAN WAARHEID = owner ∈ roles_of(filler_type, pid) — één component op één bron, geen tweede
    render (reference, not copy). group='rol' → elke swimlane is een van mijn rollen; quickadd=False
    → de lens voegt niet toe (dat blijft op rol-niveau)."""
    role_ids = set(st.assign.roles_of(filler_type, pid))
    mine = [p for p in st.projects.all()
            if p.get("owner") in role_ids and not p.get("archived") and p.get("status") != "draft"]
    back = f"/person?id={pid}&tab=projecten"
    board = _projects_board(st, mine, "", csrf_token, back, "rol", quickadd=False)
    if not board:
        board = "<p class='muted'>Geen projecten op de rollen van deze persoon.</p>"
    return f"<div class='c2-sec'><h3>Projecten ({len(mine)})</h3>{board}</div>"


def _opdracht_post(p: dict) -> str:
    """De opdracht (p['description']) als eerste, oudste wall-post — ALLEEN read-only weergave, ALLEEN
    aangeroepen wanneer er een opdracht IS. De UI-ingang om een opdracht te zetten/bewerken is bewust
    verwijderd (scope: opdracht-veld uit de UI); het veld blijft via prep (description → prompt-sectie)
    én via de API (proj_describe-dispatch) bereikbaar. Bestaande descriptions blijven dus zichtbaar."""
    desc = p.get("description", "")
    return (f"<div class='fentry fentry-opdracht'>"
            f"<div class='fhead'><span class='av you'>🙋</span>"
            f"<span class='fwho'><b class='fname'>Opdracht</b></span>"
            f"<span class='fstamp'>{_e(_stamp(p.get('created_at')))}</span></div>"
            f"<div class='fbubble'><span class='fkicker'>Opdracht</span>{_md(desc)}</div></div>")


def _attach_post(a: dict, pid: str, hid, rw: bool) -> str:
    """Een bijlage/link als inhoud-post in de wall. Tijd (at) is bekend; 'wie' wordt (nog) niet
    vastgelegd op het attachment-record → generieke auteur. Het vastleggen van 'wie' is een
    datawijziging → scope 2 (audit-trail), niet deze pure-weergave-scope."""
    if a.get("kind", "link") == "file":
        nm = a.get("title") or a.get("name", "bestand")
        href = f"/file?pid={_e(pid)}&aid={_e(a.get('id', ''))}"
        card = (f"<div class='attcard'><span class='att-ic'>{_IC_FILE}</span>"
                f"<a class='att-name' href='{href}' target='_blank' rel='noopener'>{_e(nm)}</a></div>")
    else:
        nm = a.get("title") or _link_host(a.get("url", ""))
        card = (f"<div class='attcard'><span class='att-ic'>{_IC_LINK}</span>"
                f"<a class='att-name' href='{_e(a.get('url', ''))}' target='_blank' rel='noopener'>{_e(nm)}</a></div>")
    rm = ("" if not rw else
          f"<form method='post' action='/action' class='pf'>{hid()}"
          f"<input type='hidden' name='aid' value='{_e(a.get('id', ''))}'>"
          f"<button class='flink' type='submit' name='action' value='attach_remove'>✕ verwijderen</button></form>")
    return (f"<div class='fentry fentry-attach'>"
            f"<div class='fhead'><span class='av'>📎</span>"
            f"<span class='fwho'><b class='fname'>Bijlage toegevoegd</b></span>"
            f"<span class='fstamp'>{_e(_stamp(a.get('at')))}</span></div>"
            f"<div class='fbubble'>{card}<div class='ffoot'><div class='ffoot-l'>{rm}</div></div></div></div>")


def _einddocument_html(st: _Stores, pid: str, rw: bool, hid) -> str:
    """Het levende einddocument: in-/uitklapbare, leesbaar-gerenderde weergave (📄, via `_md_doc`) +
    edit-form (mens redigeert bij review). De weergave zit in een <details open> met een eigen
    hoogte-cap (.einddoc-body) zodat een lang rapport de composer eronder niet uit beeld duwt; inklappen
    maakt de composer direct bereikbaar. De AI werkt het document bij; mens-edits zijn input voor de
    volgende synthese-pass (geen merge)."""
    store = getattr(st, "project_docs", None)
    doc = store.read(pid) if store is not None else ""
    if doc.strip():
        body = f"<div class='fentry'><div class='fbubble einddoc-body'>{_md_doc(doc)}</div></div>"
    else:
        body = ("<div class='fentry'><div class='fbubble'><span class='muted'>Nog geen einddocument — "
                "de toegewezen inwoner schrijft dit bij elke geslaagde puls.</span></div></div>")
    view = (f"<details class='einddoc-d' open><summary class='wall-head einddoc-sum'>"
            f"<h2>📄 Einddocument</h2><span class='einddoc-toggle'>in-/uitklappen</span></summary>"
            f"{body}</details>")
    if not rw:
        return view
    editor = (f"<details class='cardmenu'><summary class='flink'>✏️ document bewerken</summary>"
              f"<form method='post' action='/action' class='pf'>{hid()}"
              f"<input type='hidden' name='pid' value='{_e(pid)}'>"
              f"<label class='att-lbl'>De AI werkt dit document bij; blijvende aanwijzingen geef je via "
              f"een #task-comment op de wall.</label>"
              f"{md_editor('doc', value=doc, rows=10, help=True)}"
              f"<button class='btn ok sm' type='submit' name='action' value='proj_doc_edit'>Document opslaan</button>"
              f"</form></details>")
    regen = (f"<form method='post' action='/action' class='pf einddoc-regen'>{hid()}"
             f"<button class='flink' type='submit' name='action' value='proj_regen_doc' "
             f"onclick=\"return confirm('Rapport opnieuw genereren uit de laatste deliverables? "
             f"Dit overschrijft de huidige tekst.')\">🔄 rapport opnieuw genereren</button></form>")
    return f"{view}{editor}{regen}"


def render_project(st: _Stores, pid: str, csrf_token: str = "", msg: str = "", back: str = "/",
                   fragment: bool = False) -> str:
    p = st.projects.get(pid)
    if p is None:
        if fragment:
            return "<p class='muted'>Project bestaat niet meer.</p>"
        return _page("Niet gevonden", "<p>Project niet gevonden.</p><p><a href='/'>← home</a></p>")
    if not back.startswith("/"):
        back = "/"
    orec = st.records.get(p.get("owner"))
    owner_link = (f"<a href='/node?id={_e(p['owner'])}'>{_e(_name(orec))}</a>" if orec
                  else _e(p.get("owner") or ""))
    rw = bool(csrf_token)

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(f'/project?pid={pid}&back=' + urllib.parse.quote(back, safe=''))}'>")

    status = p.get("status", "")

    role_name = _name(orec) if orec else ""
    mention_names = [m["l"] for m in _mentionables(st)[0]]   # voor highlight in de bubble

    # ---- Status-menu (huidige status gemarkeerd) — in de header ----
    menu = ""
    if rw:
        st_items = ""
        for label, key, statuses in _PROJ_COLS:
            act = "proj_done" if key == "done" else "proj_status"
            to = "" if key == "done" else f"<input type='hidden' name='to' value='{key}'>"
            on = " on" if status in statuses else ""
            st_items += (f"<form method='post' action='/action'>{hid()}{to}"
                         f"<button class='menuitem{on}' type='submit' name='action' value='{act}'>{_e(label)}</button></form>")
        menu = (f"<details class='cardmenu'><summary class='statustrigger' aria-label='status wijzigen'>"
                f"{_proj_chip(status)}<span class='caret'>▾</span></summary><div class='cardmenu-b'>"
                f"<div class='menu-h'>Status</div>{st_items}<div class='menu-sep'></div>"
                f"<form method='post' action='/action'>{hid()}<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='menuitem' type='submit' name='action' value='proj_archive'>Archiveren</button></form>"
                f"<form method='post' action='/action'>{hid()}<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='menuitem danger' type='submit' name='action' value='proj_delete' "
                f"onclick=\"return confirm('Definitief verwijderen? Archiveren bewaart het project.')\">Verwijderen</button>"
                f"</form></div></details>")

    # ---- Titel (inline bewerkbaar) ----
    if rw:
        title = (f"<form method='post' action='/action' class='titleform'>{hid()}"
                 f"<input class='title-edit' name='scope' value='{_e(_scope_text(p))}' aria-label='projecttitel'>"
                 f"<button class='btn ok sm title-save' type='submit' name='action' value='proj_rename'>opslaan</button></form>")
    else:
        title = f"<h2 class='ptitle-ro'>{_e(_scope_text(p))}</h2>"

    # ---- Deadline-chip + overdue-badge; klikbaar → date-popover (proj_setdue) ----
    over = _due_overdue(p["due"]) if p.get("due") else False
    due_lbl = _fmt_due(p.get("due") or "") or "deadline"
    due_badge = "<span class='chip coral-solid'>Overdue</span>" if over else ""
    if rw:
        due = p.get("due") or ""
        due_rm = ("" if not due else
                  f"<form method='post' action='/action' class='pf'>{hid()}"
                  f"<input type='hidden' name='action' value='proj_setdue'><input type='hidden' name='due' value=''>"
                  f"<button class='dellink' type='submit'>datum wissen</button></form>")
        due_head = (f"<details class='acard-d'><summary class='chip {'coral' if over else 'outline'}'>"
                    f"{_IC_CLOCK}{_e(due_lbl)}</summary><div class='datepop'>"
                    f"<form method='post' action='/action'>{hid()}"
                    f"<input type='hidden' name='action' value='proj_setdue'>"
                    f"<input type='date' name='due' value='{_e(due)}' "
                    f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
                    f"</form>{due_rm}</div></details>{due_badge}")
    else:
        due_head = (f"<span class='chip {'coral' if over else 'outline'}'>{_IC_CLOCK}{_e(due_lbl)}</span>{due_badge}"
                    if p.get("due") else "")
    head = (f"<div class='pcard-head'>{title}"
            f"<div class='pcard-head-r'>{due_head}{menu or _proj_chip(status)}</div></div>")

    # ═══ RECHTS: STRUCTUUR (sticky kantlijn) ═══════════════════════════════════════════
    # 1) Projectdetails (rol+dangling, trekker, aangemaakt, zichtbaar, impacts, effort-buckets)
    owner = p.get("owner", "")
    is_ii = owner.startswith(_II_PREFIX)
    dangling = bool(owner) and not is_ii and orec is None
    rol_naam = "Individueel Initiatief" if is_ii else (_name(orec) if orec else (owner or "—"))
    if rw and not is_ii:
        warn = ("<div class='dangling-warn'><span class='chip coral-solid'>"
                "⚠ rol bestaat niet meer — kies een nieuwe</span></div>") if dangling else ""
        # scope de owner-dropdown op de cirkel waar dit project hangt (= ouder-cirkel van de owner-rol)
        owner_circle = orec.parent if orec else None
        rol_v = (f"{warn}<form method='post' action='/action' class='fieldform'>{hid()}"
                 f"<input type='hidden' name='action' value='proj_setowner'>"
                 f"<select name='owner' onchange='{_AUTOSAVE}'>{_owner_options(st, owner, circle=owner_circle)}</select></form>")
    else:
        rol_v = (f"<a href='/node?id={_e(owner)}'>{_e(rol_naam)}</a>" if orec else _e(rol_naam))
    if rw:
        pers_v = (f"<form method='post' action='/action' class='fieldform'>{hid()}"
                  f"<input type='hidden' name='action' value='proj_settrekker'>"
                  f"<select name='trekker' onchange='{_AUTOSAVE}'>"
                  f"{_trekker_options(st, owner, p.get('person') or '', p.get('agent') or '')}</select></form>")
    elif p.get("agent"):
        pa = st.personas.get(p["agent"])
        pers_v = f"{_e(pa.name if pa else p['agent'])} (AI)"
    elif p.get("person"):
        pers_v = f"<a href='/person?id={_e(p['person'])}'>{_e(_person_name(st, p['person']))}</a>"
    else:
        pers_v = "<span class='muted'>—</span>"
    if rw:
        vis_v = (f"<form method='post' action='/action' class='visform'>{hid()}"
                 f"<input type='hidden' name='action' value='proj_setprivate'>"
                 f"<label><input type='checkbox' name='private' value='1'"
                 f"{' checked' if p.get('private') else ''} "
                 f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
                 f" alleen voor deze cirkel</label></form>")
    else:
        vis_v = "Alleen voor deze cirkel" if p.get("private") else "Hele cirkel-boom"
    verzwakt_block = _verzwakt_block(p, hid, rw) if p.get("missie_impact") == "verzwakt" else ""
    w = " wide" if rw else ""                    # bewerkbaar → label boven + dropdown op volle breedte
    details_dcol = (
        f"<div class='dcol'>"
        f"<span class='dk{w}'>Rol</span><span class='dv{w}'>{rol_v}</span>"
        f"<span class='dk{w}'>Trekker</span><span class='dv{w}'>{pers_v}</span>"
        f"<span class='dk'>Aangemaakt</span><span class='dv'>{_e(_created_full(p.get('created_at')))}</span>"
        f"<span class='dk'>Zichtbaar</span><span class='dv'>{vis_v}</span>"
        f"<span class='dk{w}'>Missie-impact</span><span class='dv{w}'>{_impact_select(p, 'missie_impact', 'missie', _MISSIE_OPTS, rw, hid)}</span>"
        f"<span class='dk{w}'>Business-impact</span><span class='dv{w}'>{_impact_select(p, 'business_impact', 'business', _BUSINESS_OPTS, rw, hid)}</span>"
        f"<span class='dk{w}'>Effort</span><span class='dv{w}'>{_effort_control(p, rw, hid)}</span>"
        f"</div>")
    details_panel = _psec(_IC_INFO, "Projectdetails", details_dcol + verzwakt_block)

    # 1b) DoD-contract (founder, 19 jul — de projectpoort): done_when bij de start,
    # dod_outcome (het antwoord op de projectvraag) verplicht vóór Done. Zelfde
    # fieldform-patroon als de rest van de kantlijn; action proj_dod.
    def _dod_veld(veld: str, label: str, waarde: str, hint: str) -> str:
        if rw:
            return (f"<span class='dk wide'>{_e(label)}</span><span class='dv wide'>"
                    f"<form method='post' action='/action' class='fieldform'>{hid()}"
                    f"<input type='hidden' name='action' value='proj_dod'>"
                    f"<input type='hidden' name='veld' value='{_e(veld)}'>"
                    f"<textarea name='tekst' rows='2' placeholder='{_e(hint)}'>{_e(waarde)}</textarea>"
                    f"<button class='btn ok sm' type='submit'>opslaan</button></form></span>")
        toon = _e(waarde) or "<span class='muted'>—</span>"
        return f"<span class='dk'>{_e(label)}</span><span class='dv'>{toon}</span>"
    dod_leeg = status != "done" and not (p.get("dod_outcome") or "").strip()
    dod_flag = ("<p class='muted'>⛔ zonder antwoord geen Done — dit is de projectpoort</p>"
                if dod_leeg and rw else "")
    dod_panel = _psec(_IC_CHECK, "DoD-contract", (
        "<div class='dcol'>"
        + _dod_veld("done_when", "Klaar wanneer", p.get("done_when") or "",
                    "Waar herken je aan dat dit klaar is?")
        + _dod_veld("dod_outcome", "Antwoord op de projectvraag", p.get("dod_outcome") or "",
                    "Wat weten we nu — of waarom is dit onbeantwoordbaar?")
        + "</div>" + dod_flag))

    # 2) Checklist — vier onderscheidbare states + skill/payload (zie _checklists_html)
    checklists_html = _checklists_html(p, csrf_token, pid, back, rw)
    cl_new = ""
    if rw:
        cl_new = (f"<details class='acard-d cl-newlist'><summary class='flink'>+ nieuwe checklist</summary>"
                  f"<div class='datepop'><form method='post' action='/action'>{hid()}"
                  f"<input name='title' placeholder='Naam checklist'>"
                  f"<button class='btn ok sm' type='submit' name='action' value='checklist_add'>Voeg toe</button>"
                  f"</form></div></details>")
    cl_inner = (checklists_html or "<p class='muted'>Nog geen checklist.</p>") + cl_new
    checklist_panel = _psec(_IC_CHECK, "Checklist", cl_inner)

    # 3) Doel & relaties — placeholder (functie later)
    goals_panel = _psec(_IC_TARGET, "Doel & relaties",
                        "<p class='muted'>Nog niet gekoppeld aan een doel.</p>"
                        f"<button type='button' class='acard acard-off' disabled>{_IC_TARGET}"
                        "<span>Koppel aan doel · binnenkort</span></button>")
    structure = details_panel + dod_panel + checklist_panel + goals_panel

    # ═══ LINKS: WALL — inhoud & gesprek in tijdsvolgorde ═══════════════════════════════
    composer = ""
    if rw:
        nxt_full = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        bijlage = (f"<details class='acard-d comp-attach'><summary class='flink'>📎 bijlage</summary>"
                   f"<div class='datepop att-pop'>"
                   f"<form method='post' action='/action' enctype='multipart/form-data' class='filepost'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                   f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                   f"<input type='hidden' name='action' value='attach_file'>"
                   f"<input type='hidden' name='next' value='{_e(nxt_full)}'>"
                   f"<label class='att-lbl'>Bestand van je computer</label>"
                   f"<input type='file' name='file'>"
                   f"<button class='btn ok sm' type='submit'>Upload</button></form>"
                   f"<div class='att-sep'></div>"
                   f"<form method='post' action='/action'>{hid()}"
                   f"<label class='att-lbl'>Of een link plakken</label>"
                   f"<input name='url' placeholder='https://…'>"
                   f"<input name='title' placeholder='Naam (optioneel)'>"
                   f"<button class='btn ok sm' type='submit' name='action' value='attach_add'>Toevoegen</button></form>"
                   f"</div></details>")
        # De toolbar-rij (bijlage + Plaatsen) staat BUITEN de composer-form. Anders zit het upload-form
        # (class='filepost', multipart) genest ín comp-form — ongeldige HTML → de browser dropt de inner
        # form → de File wordt niet als multipart verstuurd (form-encoded, bestand valt weg). Plaatsen
        # submit de composer via het form=-attribuut; de bijlage is nu een eigen sibling-form.
        _cfid = f"cf-{_e(pid)}"
        composer = (f"<form id='{_cfid}' method='post' action='/action' class='pf comp-form'>{hid()}"
                    f"<input type='hidden' name='author' value='human:'>"
                    f"<label class='att-lbl'>Gesprek — @naam vraagt een inwoner om mee te denken. Sturen doe je via de checklist.</label>"
                    f"{md_editor('text', rows=2, placeholder='Schrijf een reactie…', help=True)}"
                    f"</form>"
                    f"<div class='comp-row'>"
                    f"{bijlage}"                                    # bijlage links op de toolbar-rij (eigen form)…
                    f"<button class='btn ok sm' type='submit' form='{_cfid}' name='action' value='proj_feed'>Plaatsen</button>"
                    f"</div>")                                      # …Plaatsen rechts (via .comp-attach margin-right:auto)
    # Wall-volgorde: de opdracht (de brief) blijft als context bovenaan gepind; daaronder het gesprek en
    # de deliverables/bijlagen met de NIEUWSTE bovenaan. Zo staat je net-geplaatste reactie meteen in beeld
    # (onder de composer) i.p.v. onderaan een lange rapport-wall waar je aan voorbij scrollt.
    heeft_opdracht = bool(p.get("description", "").strip())
    _oo = _wall_outcome_opts(st)   # rol-/project-opties voor '→ uitkomst' — één keer per wall
    entries = []                    # log + bijlagen; los van de gepinde opdracht, want die staat altijd bovenaan
    for m in (p.get("log") or []):
        entries.append((m.get("at") or 0,
                        _feed_entry_html(st, m, role_name=role_name, pid=pid,
                                         csrf_token=csrf_token, mention_names=mention_names,
                                         outcome_opts=_oo)))
    for a in (p.get("attachments") or []):
        entries.append((a.get("at") or 0, _attach_post(a, pid, hid, rw)))
    entries.sort(key=lambda t: t[0], reverse=True)   # nieuwste eerst
    stream_html = (_opdracht_post(p) if heeft_opdracht else "") + "".join(h for _, h in entries)
    # Nieuwste bovenaan (zie stream_html): geen auto-scroll-naar-onder meer; de wall opent bovenaan zodat
    # de composer + de recentste berichten meteen in beeld staan.
    wall = (f"<div class='wall-head'><h2>Wall — inhoud &amp; gesprek</h2></div>"
            f"{composer}"
            f"<div class='wall-scroll'>{stream_html}</div>")

    # ---- Bovenrand/labels + werkoverleg-CTA (conditioneel) ----
    labelbar = ""
    if _LABELS.get(p.get("label")):
        labelbar = f"<div class='clabel' style='background:{_LABELS[p['label']]};height:8px;border-radius:4px;margin-bottom:.6rem'></div>"
    meeting = back.startswith("/werkoverleg")
    wo_cta = (f"<a class='btn ok sm js-modal' href='{_e(back)}' data-href='{_e(back)}'>"
              f"← terug naar werkoverleg</a>") if meeting else ""
    top_bar = f"<div class='wo-back-bar'>{wo_cta}</div>" if meeting else ""
    foot_bar = f"<div class='wo-back-bar wo-back-foot'>{wo_cta}</div>" if meeting else ""

    einddoc = _einddocument_html(st, pid, rw, hid)
    detail = (f"{top_bar}{labelbar}{_banner(msg)}{head}"
              f"<div class='pgrid'><div class='pmain'>{einddoc}{wall}</div>"
              f"<aside class='pside psticky'>{structure}</aside></div>{foot_bar}")
    if fragment:
        return f"<div data-noclose='1'>{detail}</div>" if meeting else detail
    main = (f"<div class='c2-main pdetail'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{detail}</div>")
    inner = (f"{_DS_LINK}"
             f"{_nav('projectdetail')}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page(_scope_text(p), inner)




