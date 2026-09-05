"""Project-views — brok 9 van de cockpit2-split."""
from __future__ import annotations

import json
import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.web_base import _e, _page, _banner, _field
from nooch_village.project_essentie import essentie_van
from nooch_village.projects import heeft_seed_vorm
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

_PROJ_CHIP = {   # opgeslagen status-sleutel -> (Engels label, chip-kleur-modifier). Sleutels = logica.
    "running": ("Active", "green"),
    "queued": ("Queue", "muted"),
    "future": ("Future", "muted"),
    "blocked": ("Waiting", "coral"),
    "draft": ("Draft", "muted"),
    "proposed": ("Proposed", "muted"),
    "done": ("Done", "green"),
}

# Statussen die NIET op het bord horen: ze wachten op een mens-oordeel in een eigen baan. Ze zitten
# ook in geen enkele kolom van _PROJ_COLS — deze constante maakt dat expliciet in plaats van
# impliciet, zodat de telling "Projects (N)" eerlijk blijft.
_OFF_BOARD = ("draft", "proposed")


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
    return "<span class='muted'>no owner</span>"


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
    out = ["<option value=''>— no owner —</option>"]
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
            out.append(f"<option value='{_e(sel_owner)}' selected>⚠ {_e(sel_owner)} (no longer exists)</option>")
        else:                                                  # geldige owner buiten de scope/kernrol → toch tonen
            out.append(f"<option value='{_e(sel_owner)}' selected>{_e(_name(cur))}</option>")
    for r in roles:
        s = " selected" if r.id == sel_owner else ""
        out.append(f"<option value='{_e(r.id)}'{s}>{_e(_name(r))}</option>")
    return "".join(out)


# Label = weergave (Engels); de tweede waarde ('actief'/'wacht'/…) is de kolom-SLEUTEL die als
# form-value 'col' naar de dispatch gaat en daar wordt vergeleken — die blijft dus Nederlands.
_PROJ_COLS = [("Active", "actief", ("running", "queued")), ("Waiting", "wacht", ("blocked",)),
              ("Done", "done", ("done",)), ("Future", "toekomst", ("future",))]


_LABELS = {"groen": "#1F9D55", "geel": "#FFCE2E", "koraal": "#FF6B5B",
           "blauw": "#2B5BB5", "paars": "#7A5BD1", "": ""}

# Impact-pills (scope 2): klik = zetten, klik op de actieve pill = leegmaken (terug naar ongelabeld).
# Kleur-code per waarde (design-systeem, klassen .imp-pill in cockpit2_util.py): g=groen, n=grijs,
# r=rood, l=lichtgrijs. Nog gebruikt door _missie_dot (kaart-stip); de detail-view toont ze nu als
# <select> (zelfde datawaarden, alleen de weergave werd een dropdown i.p.v. pills).
_MISSIE_OPTS   = [("versterkt", "g"), ("neutraal", "n"), ("verzwakt", "r")]
_BUSINESS_OPTS = [("hoog", "g"), ("medium", "n"), ("laag", "l")]

# Weergave-labels voor de opgeslagen impact- en effort-enums. De OPGESLAGEN waarde blijft Nederlands
# (logica-sleutel: proj_setimpact/proj_seteffort vergelijken 'versterkt', 'dagen', … — zie cockpit2);
# alleen het GETOONDE label is Engels. Precies de display-mapping-regel: nooit de opgeslagen waarde.
_IMPACT_LABEL = {"versterkt": "Strengthens", "neutraal": "Neutral", "verzwakt": "Weakens",
                 "hoog": "High", "medium": "Medium", "laag": "Low"}
_UNIT_LABEL = {"uren": "hours", "dagen": "days"}

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
        return _e(_IMPACT_LABEL.get(cur, cur)) if cur else "<span class='muted'>—</span>"
    options = "<option value=''>—</option>" + "".join(
        f"<option value='{_e(val)}'{' selected' if val == cur else ''}>{_e(_IMPACT_LABEL.get(val, val))}</option>"
        for val, _ in opts)
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
        return _e(f"{hours // 8} days" if hours % 8 == 0 else f"{hours} hours")
    if hours and hours % 8 == 0:
        num, unit = hours // 8, "dagen"
    elif hours:
        num, unit = hours, "uren"
    else:
        num, unit = "", "uren"
    # value blijft 'uren'/'dagen' (proj_seteffort vergelijkt 'dagen'); alleen het label is Engels.
    units = "".join(f"<option value='{u}'{' selected' if u == unit else ''}>{_UNIT_LABEL[u]}</option>"
                    for u in ("uren", "dagen"))
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
    return f"<span class='mdot {col}' title='Mission impact: {_e(_IMPACT_LABEL.get(p['missie_impact'], p['missie_impact']))}'></span>"


def _verzwakt_block(p, hid, rw: bool) -> str:
    """Signaal-infoblok bij missie_impact=verzwakt (géén blokkade — statuswissels blijven mogelijk). Toont
    de boodschap + een knop om het als spanning te agenderen in het werkoverleg van de cirkel (bewerkbaar)."""
    btn = ""
    if rw:
        btn = (f"<form method='post' action='/action' class='vz-form'>{hid()}"
               f"<button class='btn ok sm' type='submit' name='action' value='proj_agendeer_verzwakt'>"
               f"Add to tactical meeting</button></form>")
    return (f"<div class='vzblock'>"
            f"<div class='vz-h'>Mission weakened. You decide as role filler.</div>"
            f"<div class='vz-t'>Raise this as a tension in the tactical meeting?</div>{btn}</div>")


def _proj_progress(p: dict):
    """(done, telbaar, pct) over alle checklists. Telt via de gedeelde `checklist_progress`, zodat de
    kaart-badge exact hetzelfde getal toont als waar de worker zijn review-gate op baseert."""
    from nooch_village.projects import checklist_progress
    items = [it for cl in (p.get("checklists") or []) for it in cl.get("items", [])]
    if not items:
        return None
    done, telbaar = checklist_progress(items)
    if not telbaar:                                   # alles overgeslagen → geen zinnig percentage
        return None
    return done, telbaar, round(100 * done / telbaar)


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
    # 100% mag niet lezen als "alles gedaan" wanneer er iets is overgeslagen: de ⤳ en de tooltip
    # maken het besluit zichtbaar op de kaart zelf, zonder doorklikken.
    from nooch_village.projects import not_answered_note
    weg = not_answered_note(p)
    return (f"<div class='pbadge' title='{done}/{total}"
            f"{' · ' + _e(weg) if weg else ''}'>"
            f"<div class='pbar'><div style='width:{pct}%'></div></div>"
            f"<span>{pct}%{' ⤳' if weg else ''}</span></div>")


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
    """'+ add project' per kolom — een DEUR, geen formulier.

    Hier stonden tot 28-08-2026 twee tekstvelden (titel + done-when). Bij B1 werd de knop al naar
    de wizard geleid, maar de velden bleven staan "zodat je niets hoeft over te tikken". Gevolg:
    het bord toonde iets dat er precies uitzag als een tweede projectcreatie-formulier. Een lezer
    die het zag concludeerde terecht dat er nog een tweede deur was — en dat is bij een vorm die
    er zo uitziet geen misverstand maar een ontwerpfout.

    Nu is het één link naar de wizard, met de context die deze kolom al weet: de rol, en de
    trekker als er per persoon gegroepeerd wordt. Typen doe je in de wizard, in het veld dat het
    project ook echt aanmaakt.

    Zonder javascript navigeert de link gewoon; de wizard is ook een volle pagina."""
    if not csrf_token or col == "done":
        return ""
    from urllib.parse import urlencode
    vraag = {"role": owner}
    if trekker:
        vraag["trekker"] = trekker
    href = "/project/nieuw?" + urlencode(vraag)
    return (f"<a class='addlink js-modal' href='{_e(href)}' data-href='{_e(href)}'>"
            f"+ add project</a>")


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
            f"＋ add project</a>")


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
        "<button type='button' class='ovl-x' aria-label='close'>✕</button>"
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
        # Leest de server-markering uit de gevolgde redirect: `ok=0` betekent geweigerd, en
        # `msg` draagt de reden die de mens moet lezen. Geen markering → gewoon gelukt.
        "function weigering(u){try{var q=new URL(u,location.origin).searchParams;"
        "if(q.get('ok')!=='0')return '';"
        "return q.get('msg')||'\\u26a0 geweigerd';}catch(e){return '';}}"
        "function frag(u){return u+(u.indexOf('?')>-1?'&':'?')+'fragment=1';}"
        "function openCard(u,push){var wasClosed=(ov.style.display==='none'||!ov.style.display);last=u;"
        # Had geen enkele respons-controle: een 500 of een login-redirect vulde de kaart met
        # een foutpagina of stilte, zonder dat iets zich meldde.
        "fetch(frag(u)).then(function(r){"
        "if(!r.ok){toast('\\u26a0 kon deze kaart niet laden ('+r.status+')');throw new Error(r.status);}"
        "return r.text();}).then(function(h){bd.innerHTML=h;ov.style.display='flex';"
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
        # Formulieren worden per stuk bedraad en gemarkeerd, zodat een fragment dat NA het openen
        # wordt vervangen (de puntenlijst na een vangst) alsnog bedraad kan worden zonder de al
        # bedrade formulieren een tweede listener te geven — die zou elke actie dubbel posten.
        "function wireForm(f){if(f.getAttribute('data-wired'))return;f.setAttribute('data-wired','1');"
        # Formulieren van de gedeelde mechaniek (`static/nooch.js`) slaan we over: die hebben hun
        # eigen wachtrij, want drie regels achter elkaar typen mag het fragment niet onder je
        # vingers vandaan vervangen. Op het ATTRIBUUT selecteren, niet op de klasse: `.rov-add`
        # zit ook op het agenda-veld van het roloverleg, en dat heeft de generieke afhandeling
        # wél nodig — anders post het formulier gewoon en navigeert het de overlay uit.
        "if(f.getAttribute('data-qa-frag'))return;"
        "f.addEventListener('submit',function(e){"
        "e.preventDefault();dirty=true;var act=(e.submitter&&e.submitter.value)||'';var opts;"
        "if(f.classList.contains('filepost')){opts={method:'POST',body:new FormData(f)};}"
        "else{var data=new URLSearchParams(new FormData(f));"
        "if(e.submitter&&e.submitter.name){data.set(e.submitter.name,e.submitter.value);}opts={method:'POST',body:data};}"
        "fetch('/action',opts).then(function(resp){"
        # response.ok-poort (generiek voor ELKE modal-actie, incl. de auto-opslaan-controls): een 413
        # (bestand te groot) of elke andere niet-2xx toont de server-melding en NOOIT '✓ opgeslagen'.
        "if(!resp.ok){resp.text().then(function(t){reopen();toast('\\u26a0 '+(((t||'').trim()||'not saved').slice(0,90)));});return;}"
        # ZELFDE POORT ALS BIJ DE DROP. Hier liep de done-knop óók langs: de server weigerde
        # met "⛔ het einddocument is nog leeg", de redirect gaf 200, en dit toastte
        # "✓ saved". Geen confetti op een weigering.
        "var w=weigering(resp.url);"
        "if(w){reopen();toast(w.slice(0,140));return;}"
        "if(act==='wo_close'||act==='rov2_end'){confetti();setTimeout(shut,700);}"
        "else if(act==='proj_delete'||act==='proj_archive'||act==='proj_add'){shut();}"
        "else{var dr=f.getAttribute('data-reopen');if(dr){last=dr;}reopen();toast('\\u2713 saved');}})"
        # netwerk-foutpad (geen response): melding + best-effort revert door het fragment te herladen.
        ".catch(function(){reopen();toast('\\u26a0 not saved');});});}"
        "window.__ovlWireForms=function(root){(root||bd).querySelectorAll('form').forEach(wireForm);};"
        "function wire(){bd.querySelectorAll('form').forEach(wireForm);"
        # De gedeelde mechaniek kent de overlay niet; de overlay roept hem aan zodra hij een
        # fragment heeft ingevoegd. Zo krijgt élk toekomstig typ-en-Enter-veld in een modal de
        # wachtrij zonder dat de modal er iets van hoeft te weten.
        "if(window.NV)NV.wire(bd);"
        "bd.querySelectorAll('textarea').forEach(mentionWire);"
        # wall scrollt naar het laatste bericht: bij openen én na elke actie (reopen()→wire()), scoped op bd
        "var ws=bd.querySelector('.wall-scroll');if(ws){requestAnimationFrame(function(){ws.scrollTop=0;});}"
        # Per link markeren en via één hook, zodat een blok dat NA het openen wordt vervangen
        # (de puntenlijst in het stappenmenu) alsnog bedraad wordt zonder de al bedrade links een
        # tweede listener te geven — die zou de kaart twee keer openen.
        "window.__ovlWireLinks=function(root){(root||bd).querySelectorAll('a.js-modal[data-href]')"
        ".forEach(function(a){if(a.getAttribute('data-wired'))return;a.setAttribute('data-wired','1');"
        "a.addEventListener('click',function(e){e.preventDefault();openCard(a.getAttribute('data-href'));});});};"
        "window.__ovlWireLinks(bd);"
        # Publieke ingang: een knop die zijn doel-URL pas bij het klikken samenstelt (de wizard,
        # voorgevuld met wat de mens net intypte) kan geen data-href dragen. Zonder deze hook zou
        # zo'n knop de pagina uit navigeren in plaats van de overlay te openen.
        "window.__ovlOpen=function(u){openCard(u);};"
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
        # `resp.ok` IS NIET GENOEG. Een weigering reist als melding op een 303; fetch volgt die,
        # dus de status is 200 en `ok` staat op true terwijl de server NEE zei. De server
        # markeert dat nu zelf met `ok=0` in de redirect-URL — wij lezen de markering, niet de
        # emoji, en tonen de reden die er al bij zat.
        "fetch('/action',{method:'POST',body:d}).then(function(resp){"
        "if(!resp.ok){resp.text().then(function(t){reopen();toast('\\u26a0 '+(((t||'').trim()||'not moved').slice(0,90)));});return;}"
        "var w=weigering(resp.url);"
        "if(w){reopen();toast(w.slice(0,140));return;}"
        "reopen();toast('\\u2713 moved');})"
        ".catch(function(){reopen();toast('\\u26a0 not moved');});});});"
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
            return (("ii", owner), "zzz", "Individual Action", owner, "")
        orec = st.records.get(owner)
        if orec is None and owner:
            # dangling: de eigenaar-rol bestaat niet meer — maak dat zichtbaar i.p.v. stil "—"
            return (("rol", owner), "zzz_" + owner.lower(),
                    f"⚠ {owner} (role no longer exists)", owner, "")
        nm = _name(orec) if orec else (owner or "—")
        return (("rol", owner), nm.lower(), nm, owner, "")
    if p.get("agent"):
        pa = st.personas.get(p["agent"])
        return (("persona", p["agent"]), "1", f"🤖 {(pa.name if pa else p['agent'])} (AI)",
                node_owner, f"persona:{p['agent']}")
    if p.get("person"):
        nm = _person_name(st, p["person"])
        return (("person", p["person"]), "0_" + nm.lower(), nm, node_owner, f"person:{p['person']}")
    return (("none",), "2", "No owner", node_owner, "")


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
                f"<button class='btn' type='submit' name='action' value='proj_unarchive'>restore</button>"
                f"<button type='submit' name='action' value='proj_delete' class='dellink' "
                f"onclick=\"return confirm('Delete permanently?')\">delete</button></form>")
        rows += f"<li class='muted'>{_e(str(scope or '—'))}{ctrl}</li>"
    return (f"<details class='box-details' style='margin-top:.6rem'><summary>🗄 Archived ({len(archived)})</summary>"
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
                f"<button class='btn ok sm' type='submit' name='action' value='proj_approve'>approve</button>"
                f"</form> <form method='post' action='/action' style='display:inline'>{base}"
                f"<button class='dellink' type='submit' name='action' value='proj_discard' "
                f"onclick=\"return confirm('Discard draft?')\">discard</button></form>")
        rows += (f"<li>{_e(str(scope or '—'))} <span class='muted'>· {trekker}</span>{ctrl}</li>")
    return (f"<details class='box-details' open style='margin:.6rem 0'><summary>📝 Drafts — awaiting approval "
            f"({len(drafts)})</summary><ul class='clean'>{rows}</ul></details>")


# De review-baan voor voorstellen (status `proposed`) stond hier, in twee smaken: op de rol-tab en
# op de cirkel-tab. Hij is 11 aug 2026 verhuisd naar de Founder Flow (/founder). Reden: adjudicatie
# hoort op één plek. Verspreid over het projectenbord moest je per rol en per cirkel langs om te
# zien wat op je oordeel wachtte, en zag je nooit hoeveel er in totaal lag.
# De rendering leeft nu in `views/founder_flow._voorstellen_sectie`; de dispatch-takken
# (proj_proposal_accept/reject) en `project_proposals` zijn ongewijzigd.


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
                f"<button class='btn sm' type='submit' name='action' value='proj_setowner'>link to role</button>"
                f"</form> <form method='post' action='/action' style='display:inline'>{base}"
                f"<button class='btn sm' type='submit' name='action' value='proj_archive'>archive</button>"
                f"<button class='dellink' type='submit' name='action' value='proj_delete' "
                f"onclick=\"return confirm('Delete permanently?')\">delete</button></form>")
        rows += (f"<li><span class='chip coral-solid'>orphan</span> {_e(str(scope or '—'))} "
                 f"<span class='muted'>· lost owner: {ghost}</span>{ctrl}</li>")
    return (f"<div class='c2-sec'><h3>⚠ Orphan projects ({len(orphans)})</h3>"
            f"<p class='muted' style='font-size:.8rem'>These projects reference a role that no longer "
            f"exists. Link them to an existing role or clean them up.</p>"
            f"<ul class='clean'>{rows}</ul></div>")


def _projects_tab_html(st: _Stores, rec, csrf_token: str, group: str = "", add: bool = True,
                       username: str | None = None) -> str:
    allp = st.projects.all()
    back_base = f"/node?id={rec.id}&tab=projects"

    addlink = _wizard_addlink(rec, csrf_token) if add else ""

    if not org.is_circle(rec):
        # ROL: eigen projecten, gegroepeerd per persoon (de doener). Lege lanes tonen we niet.
        mine = [p for p in allp if p.get("owner") == rec.id and not p.get("archived")]
        projs = [p for p in mine if p.get("status") not in _OFF_BOARD]
        drafts = [p for p in mine if p.get("status") == "draft"]
        archived = [p for p in allp if p.get("owner") == rec.id and p.get("archived")]
        board = _projects_board(st, projs, rec.id, csrf_token, back_base, "persoon", quickadd=add)
        if not board:
            board = ("<p class='muted'>No projects yet. Add one with ＋ add project.</p>" if add
                     else "<p class='muted'>No projects yet.</p>")
        head = (f"<div style='margin-bottom:1rem'>"
                f"<h3 style='margin:0;display:inline'>Projects ({len(projs)})</h3> &nbsp; {addlink}</div>")
        return (f"<div class='c2-sec'>{head}{_drafts_html(st, drafts, csrf_token, back_base)}"
                f"{board}{_archived_html(st, archived, csrf_token, back_base)}</div>")

    # CIRKEL: doet zelf geen uitvoerend werk. Toont projecten van haar DIRECTE rollen +
    # Individual Initiative. Lege lanes tonen we niet; subcirkels = eigen bord (niet aggregeren).
    g = group if group in ("persoon", "rol") else "rol"
    direct = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    rids = {r.id for r in direct}
    ii = f"{_II_PREFIX}{rec.id}"
    mine = [p for p in allp if (p.get("owner") in rids or p.get("owner") == ii) and not p.get("archived")]
    projs = [p for p in mine if p.get("status") not in _OFF_BOARD]
    drafts = [p for p in mine if p.get("status") == "draft"]
    back = f"{back_base}&group={g}"
    board = _projects_board(st, projs, rec.id, csrf_token, back, g, quickadd=add)
    if not board:
        board = ("<p class='muted'>No projects yet. Add one with ＋ add project.</p>" if add
                 else "<p class='muted'>No projects yet.</p>")
    subs = sorted(org.subcircles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    sub_html = ""
    if subs:
        lis = "".join(f"<li><a href='/node?id={_e(s.id)}&tab=projects'>{_e(_name(s))}</a> "
                      f"<span class='muted'>→ own project board</span></li>" for s in subs)
        sub_html = (f"<div class='c2-sec'><h3>Subcircles</h3>"
                    f"<p class='muted' style='font-size:.8rem'>A subcircle has its own "
                    f"project board.</p><ul class='clean'>{lis}</ul></div>")
    on = lambda v: " on" if g == v else ""
    switch = (f"<div class='vswitch'>Group by: "
              f"<a class='vbtn{on('rol')}' href='{back_base}&group=rol'>by role</a>"
              f"<a class='vbtn{on('persoon')}' href='{back_base}&group=persoon'>by person</a></div>")
    head = (f"<div style='display:flex;align-items:center;justify-content:space-between;"
            f"flex-wrap:wrap;gap:.6rem;margin-bottom:1rem'>"
            f"<div><h3 style='margin:0;display:inline'>Projects ({len(projs)})</h3> &nbsp; {addlink}</div>"
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
            if p.get("owner") in role_ids and not p.get("archived")
            and p.get("status") not in _OFF_BOARD]
    back = f"/person?id={pid}&tab=projecten"
    board = _projects_board(st, mine, "", csrf_token, back, "rol", quickadd=False)
    if not board:
        board = "<p class='muted'>No projects on this person's roles.</p>"
    return f"<div class='c2-sec'><h3>Projects ({len(mine)})</h3>{board}</div>"


def _opdracht_post(p: dict) -> str:
    """De opdracht (p['description']) als eerste, oudste wall-post — ALLEEN read-only weergave, ALLEEN
    aangeroepen wanneer er een opdracht IS. De UI-ingang om een opdracht te zetten/bewerken is bewust
    verwijderd (scope: opdracht-veld uit de UI); het veld blijft via prep (description → prompt-sectie)
    én via de API (proj_describe-dispatch) bereikbaar. Bestaande descriptions blijven dus zichtbaar."""
    desc = p.get("description", "")
    return (f"<div class='fentry fentry-opdracht'>"
            f"<div class='fhead'><span class='av you'>🙋</span>"
            f"<span class='fwho'><b class='fname'>Assignment</b></span>"
            f"<span class='fstamp'>{_e(_stamp(p.get('created_at')))}</span></div>"
            f"<div class='fbubble'><span class='fkicker'>Assignment</span>{_md(desc)}</div></div>")


def _attach_post(a: dict, pid: str, hid, rw: bool) -> str:
    """Een bijlage/link als inhoud-post in de wall. Tijd (at) is bekend; 'wie' wordt (nog) niet
    vastgelegd op het attachment-record → generieke auteur. Het vastleggen van 'wie' is een
    datawijziging → scope 2 (audit-trail), niet deze pure-weergave-scope."""
    if a.get("kind", "link") == "file":
        nm = a.get("title") or a.get("name", "file")
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
          f"<button class='flink' type='submit' name='action' value='attach_remove'>✕ remove</button></form>")
    return (f"<div class='fentry fentry-attach'>"
            f"<div class='fhead'><span class='av'>📎</span>"
            f"<span class='fwho'><b class='fname'>Attachment added</b></span>"
            f"<span class='fstamp'>{_e(_stamp(a.get('at')))}</span></div>"
            f"<div class='fbubble'>{card}<div class='ffoot'><div class='ffoot-l'>{rm}</div></div></div></div>")


def _herkomst_chip(st: _Stores, pid: str) -> str:
    """Welk model schreef dit einddocument — en was dat het gevraagde model?

    Een persona-voorkeur is een kop met de dorpsladder als staart: valt de dure trede weg, dan komt
    er alsnog een document, maar van een goedkoper model. Zonder deze markering leest zo'n document
    als een premium exemplaar, en dat is precies de stille verwisseling die een reviewer niet kan
    zien. Geen herkomst (mens-edit, of van vóór de markering) → geen chip, geen ruis."""
    store = getattr(st, "project_docs", None)
    meta = store.meta(pid) if store is not None else {}
    tier = (meta or {}).get("tier")
    if not tier:
        return ""
    if meta.get("terugval"):
        return (f"<span class='chip amber' title='The requested model was unavailable; this document "
                f"came from the cheaper fallback rung.'>⚠ fallback: {_e(tier)}</span>")
    return f"<span class='chip outline' title='Model that wrote this document'>{_e(tier)}</span>"


def _result_formulier(st, pid: str, p: dict, concept: dict, hid, nxt: str) -> str:
    """Het menselijke sluitstuk op de kaart: doel behaald ja/nee, toelichting, optionele learnings.

    GEEN POORT. De status stond al op done vóór dit formulier bestond; dit is een vraag ná de
    handeling, geen dialoog ertussen. Overslaan kan, en dat markeert het verslag eerlijk
    ("not recorded") in plaats van het als behaald weg te zetten.

    TWEE SIGNALEN NAAST ELKAAR. Het modeloordeel is het voorstel; de checklist-staat is de
    kruischeck. Botsen ze — de checklist zei "8 van 8 af", het gesprek zei "twee gaten open" — dan
    is dat iets om naar te kijken. Ze samenvoegen tot één cijfer zou de botsing verstoppen, en
    juist die botsing is de reden dat een mens hier kijkt."""
    from nooch_village.project_verslag import (label_voor, modeloordeel, voorstel_learnings,
                                                voorstel_toelichting)
    tekst = concept.get("tekst") or ""
    model = modeloordeel(tekst)
    kruis = label_voor((concept.get("voorzet") or "").strip())
    signalen = (f"<div class='einddoc-sig'>"
                + (f"<div class='einddoc-sigr'><span class='einddoc-sigk'>Report says</span>"
                   f"<span class='einddoc-sigv'>{_e(model)}</span></div>" if model else "")
                + f"<div class='einddoc-sigr'><span class='einddoc-sigk'>Checklist says</span>"
                  f"<span class='einddoc-sigv'>{_e(kruis)}</span></div></div>")
    # Expliciete for/id, ook al zou een omwikkelend label ook werken: dan blijft de ratchet
    # (labels-zonder-for) meten wat hij bedoelt te meten in plaats van hier een uitzondering te
    # moeten kennen.
    # GEEN VOORSELECTIE. De toelichting en de leringen zijn een CONCEPT om bij te schaven — daar
    # scheelt voorinvullen echt werk. Het oordeel is iets anders: dat is de ene beslissing die de
    # mens actief moet nemen, en elke default duwt hem naar een antwoord zodra de twee signalen
    # botsen. Ze staan eronder; hij kiest. Geen schrijfhuiswerk, wél een bewuste klik.
    keuze = "".join(
        f"<input type='radio' id='ro-{_e(w)}-{_e(pid)}' name='oordeel' value='{_e(w)}'>"
        f"<label class='einddoc-keuze' for='ro-{_e(w)}-{_e(pid)}'>{_e(lbl)}</label>"
        for w, lbl in (("behaald", "Goal achieved"), ("niet_behaald", "Not achieved")))
    return (f"<div class='card einddoc-concept'>"
            f"<div class='einddoc-ckop'><span class='chip amber'>needs your confirmation</span>"
            f"<span class='muted'>the report is assembled but not confirmed</span></div>"
            f"{signalen}"
            f"<form method='post' action='/action' class='pf einddoc-rform'>{hid()}"
            f"<input type='hidden' name='next' value='{nxt}'>"
            f"<div class='einddoc-keuzes'>{keuze}</div>"
            # VÓÓRINGEVULD uit het concept: de analyse staat er al, dus de mens vult aan in plaats
            # van blanco te typen. Overschrijven mag altijd — het is een voorstel, geen antwoord.
            f"{_field('Why', 'toelichting', value=voorstel_toelichting(tekst), fid=f'rt-{pid}', placeholder='What made it so?')}"
            f"{_field('Learnings — optional', 'learnings', kind='textarea', value=voorstel_learnings(tekst), fid=f'rl-{pid}', placeholder='Worth remembering?')}"
            f"<div class='qadd-row'>"
            f"<button class='btn ok sm' type='submit' name='action' value='verslag_bevestig'>"
            f"Confirm report</button>"
            f"<button class='flink' type='submit' name='action' value='verslag_overslaan' "
            f"title='Close without recording a result — the report says so honestly'>"
            f"Skip this</button></div></form></div>")


def _einddocument_delen(st: _Stores, pid: str, rw: bool, hid, back: str = "/") -> tuple[str, str]:
    """De Description-sectie: de ESSENTIE plus een weg naar het volledige rapport.

    Hiervóór stond het hele einddocument hier inline. Dat maakte de kaart onscanbaar — je opent
    een project om te zien waar het staat en krijgt een document van vijf schermen. De kaart toont
    nu een of twee zinnen; het rapport woont op `/rapport?pid=…` (zie views/rapport.py voor waarom
    een eigen route en geen uitklapper).

    GEEN INFORMATIEVERLIES: de essentie snijdt niets weg dat niet één klik verder staat, en bij een
    gekapte zin is de link geen aanbod maar noodzaak — daarom staat hij er dan ook altijd.

    DRIE TOESTANDEN, DRIE ZINNEN. Een document dat nog alleen de opdracht is (107x op productie) is
    iets anders dan geen document. Een essentie tonen bij een seed zou zeggen dat er een rapport
    is, en dat is niet waar; de 'klaar wanneer'-regel als samenvatting tonen zou bovendien bij 84
    van die 107 bijna letterlijk de projecttitel herhalen die er twee centimeter boven staat.

    De acties (`proj_doc_edit`, `proj_regen_doc`) horen bij het volledige rapport en verhuizen dus
    mee naar die route; wat hier blijft is de ingang ernaartoe."""
    store = getattr(st, "project_docs", None)
    doc = store.read(pid) if store is not None else ""
    p = st.projects.get(pid) or {}
    nxt = f"/rapport?pid={_e(pid)}&back={urllib.parse.quote(back, safe='')}"

    def lees(label: str) -> str:
        # GEEN %-formatting hier: `nxt` bevat url-gecodeerde tekens (%2F), en die leest %-formatting
        # als een format-specifier. De suite ving dat als een TypeError op elk project zonder
        # bruikbare essentie.
        return f"<p class='einddoc-meer'><a class='flink' href='{nxt}'>{_e(label)} →</a></p>"

    # HET MENSELIJKE SLUITSTUK, MAAR ALLEEN WAAR HET NIET OPDRINGT. Staat er al een écht rapport
    # (geen seed), dan is een formulier dat vraagt of we het mogen vervangen een stille downgrade
    # in beleefde vorm — daar blijft het bij een link naar de route. Gemeten op productie: 152 van
    # de 300 afsluitbare projecten hebben een leeg of seed-document en krijgen de vraag dus wél;
    # 148 hebben een echt rapport en krijgen hem niet.
    _c = store.concept(pid) if store is not None else {}
    if rw and (_c.get("tekst") or "").strip() and (not doc.strip() or heeft_seed_vorm(doc)):
        return _result_formulier(st, pid, p, _c, hid, nxt), ""

    # EEN WACHTEND CONCEPT IS EEN SIGNAAL, GEEN VERSLAG. De essentie blijft die van het BEVESTIGDE
    # document: onbevestigde modeltekst als samenvatting tonen zou de kaart weer laten zeggen dat er
    # iets ligt wat er niet ligt — precies wat we bij de seeds weghaalden. Wel een merkteken, want
    # er valt iets te doen.
    wacht = ""
    if store is not None and (store.concept(pid).get("tekst") or "").strip():
        wacht = (f"<p class='einddoc-meer'><a class='flink' href='{nxt}'>"
                 f"Draft report awaiting confirmation →</a></p>")

    if not doc.strip():
        body = ("<p class='muted'>No end document yet — the assigned inhabitant writes it on "
                "every successful pulse.</p>") + wacht
        return body, ""

    ess = essentie_van(doc)
    if ess.soort == "seed":
        body = ("<p class='muted'>No report written yet — only the assignment.</p>"
                + lees("Read the assignment") + wacht)
    elif ess.heeft_tekst:
        body = f"<p class='einddoc-kern'>{_e(ess.tekst)}</p>" + lees("Full report") + wacht
    else:
        # Trede 4: wel een rapport, maar geen zin die als essentie kan dienen (4x op productie).
        # Liever niets dan een fragment dat zich als samenvatting voordoet.
        body = lees("Full report") + wacht
    return body, ""


def _ai_namen(st) -> list[str]:
    """De namen van AI-vervulde rollen, voor de @-hint in de composer.

    UIT DE ECHTE ORG, niet uit een lijstje in code. De mock noemt @Sid en @Lotte; die twee
    hardcoden zou de hint laten liegen zodra een persona verdwijnt of erbij komt — dezelfde
    broosheid als een rol-id vastzetten. Slapende rollen tellen niet mee: een naam noemen die niet
    antwoordt is een uitnodiging die nergens toe leidt.

    Fail-soft: geen personas of een onleesbare store → lege lijst, en dan toont de composer gewoon
    geen hint."""
    uit = []
    try:
        for rec in st.records.all():
            if getattr(rec, "slaapt", False) or getattr(rec, "archived", False):
                continue
            pid = getattr(rec, "persona_id", "") or getattr(rec, "persona", "")
            if not pid:
                continue
            persona = st.personas.get(pid)
            naam = (persona or {}).get("name") if isinstance(persona, dict) else getattr(persona, "name", "")
            voornaam = str(naam or "").split()[0] if naam else ""
            if voornaam and voornaam not in uit:
                uit.append(voornaam)
    except Exception:                                        # noqa: BLE001
        return []
    return uit


def _psectie(kop: str, inhoud: str, *, bijschrift: str = "", acties: str = "") -> str:
    """Eén sectie in de hoofdkolom: kleine kop in kapitalen, acties rechts, inhoud eronder.

    De koppen zijn klein en gedempt (zoals in de mock), niet groot en display: de INHOUD is de
    hoofdzaak. De oude koppen "END DOCUMENT" en "WALL — CONTENT & CONVERSATION" schreeuwden en
    zeiden tegelijk niets over wat eronder stond."""
    bs = f"<span class='psec-bij'>{_e(bijschrift)}</span>" if bijschrift else ""
    ac = f"<span class='psec-act'>{acties}</span>" if acties else ""
    return (f"<section class='psec'><div class='psec-head'><h2>{_e(kop)}</h2>{bs}{ac}</div>"
            f"{inhoud}</section>")


def _rail_regel(icoon: str, label: str, waarde: str, *, control: str = "") -> str:
    """Eén regel in de rail: icoon, label, waarde rechts. `control` vervangt de waarde als het veld
    bewerkbaar is — dan staat het besturingselement zelf in de regel."""
    rechts = control or f"<span class='rail-v'>{_e(waarde)}</span>"
    return (f"<div class='rail-rij'><span class='rail-i'>{icoon}</span>"
            f"<span class='rail-l'>{_e(label)}</span>{rechts}</div>")


def _chip_knop(kop: str, waarde: str, *, leeg: bool = False, extra: str = "") -> str:
    """Eén chip uit de mock: pil met kop-label en waarde. `leeg` → gestippelde rand (de mock
    onderscheidt "nog niet ingevuld" met een streepjesrand, niet met grijze tekst — een leeg veld
    dat eruitziet als een gevuld veld nodigt niet uit)."""
    return (f"<span class='pchip{' pchip-leeg' if leeg else ''}{extra}'>"
            f"<span class='pchip-k'>{_e(kop)}</span>"
            f"<span class='pchip-v'>{_e(waarde)}</span></span>")


def _meta_rij(kop: str, waarde: str) -> str:
    """Eén regel in de rail: label links, waarde/control rechts. Uit de mock."""
    return (f"<div class='mrow'><span class='mk'>{_e(kop)}</span>"
            f"<span class='mv'>{waarde}</span></div>")


def _meta_rijen(st, p, rw: bool, hid, trekker_opts: str = "") -> str:
    """ALLE meta in één rail — status, assignee, impact, business, effort.

    Deze controls stonden in een pillenrij bóven de content. Dat had twee problemen: de rij duwde
    de inhoud naar beneden, en status — het veld dat je het vaakst verandert — verdween zodra je
    naar de conversatie scrollde. In de rail staat hij altijd in beeld.

    GEEN NIEUWE CONTROLS. Elke regel hieronder post naar dezelfde dispatch als de chip die hij
    vervangt (`proj_setimpact`, `proj_seteffort`, `proj_status`/`proj_done`, `proj_settrekker`);
    `_effort_control` verhuist ongewijzigd mee, met zijn eigen uren/dagen-model."""
    uit = []

    # Status: bewerkbaar in de rail zelf. Sinds de ontdubbeling woont lezen en veranderen op
    # dezelfde plek; die eis verhuist mee.
    _slbl = _PROJ_CHIP.get(p.get("status", ""), (p.get("status", "—"), ""))[0]
    if rw and hid is not None:
        items = ""
        for label, key, statuses in _PROJ_COLS:
            act = "proj_done" if key == "done" else "proj_status"
            to = "" if key == "done" else f"<input type='hidden' name='to' value='{_e(key)}'>"
            on = " on" if p.get("status", "") in statuses else ""
            items += (f"<form method='post' action='/action'>{hid()}{to}"
                      f"<button class='menuitem{on}' type='submit' name='action' value='{act}'>"
                      f"{_e(label)}</button></form>")
        uit.append(_meta_rij("Status",
                             f"<details class='cardmenu mmenu'>"
                             f"<summary class='ctrl' aria-label='change status'>{_e(_slbl)}"
                             f"<span class='car'>▾</span></summary>"
                             f"<div class='cardmenu-b'>{items}</div></details>"))
    else:
        uit.append(_meta_rij("Status", f"<span class='ctrl'>{_e(_slbl)}</span>"))

    uit.append(_meta_rij("Assignee", _eigenaar_control(st, p, rw, hid, trekker_opts)))

    for veld, kind, opts, kop in (("missie_impact", "missie", _MISSIE_OPTS, "Mission impact"),
                                  ("business_impact", "business", _BUSINESS_OPTS, "Business")):
        cur = p.get(veld, "")
        label = _IMPACT_LABEL.get(cur, cur) or "—"
        if not rw:
            uit.append(_meta_rij(kop, f"<span class='ctrl'>{_e(label)}</span>"))
            continue
        keuzes = "".join(
            f"<option value='{_e(v)}'{' selected' if v == cur else ''}>{_e(_IMPACT_LABEL.get(v, v))}</option>"
            for v, _ in opts)
        uit.append(_meta_rij(kop,
                             f"<form method='post' action='/action' class='mform'>{hid()}"
                             f"<input type='hidden' name='action' value='proj_setimpact'>"
                             f"<input type='hidden' name='kind' value='{_e(kind)}'>"
                             f"<select class='ctrl' name='value' onchange='{_AUTOSAVE}'>"
                             f"<option value=''>—</option>{keuzes}</select></form>"))

    _u = _effort_hours(p.get("effort"))
    uit.append(_meta_rij("Effort", _effort_control(p, rw, hid) if rw else
                         (f"<span class='ctrl'>"
                          f"{(f'{_u // 8} d' if _u and _u % 8 == 0 else f'{_u} u') if _u else '—'}"
                          f"</span>")))
    return "".join(uit)


def _eigenaar_control(st, p, rw: bool = False, hid=None, trekker_opts: str = "") -> str:
    """De trekker als rail-control: wie het DOET. De rol (waar het hangt) staat een regel lager.

    BEWERKBAAR, NIET ALLEEN TONEN. Bij de vorige herindeling verdween `proj_settrekker` bijna omdat
    het formulier in een verwijderde rij zat; de suite ving dat. Zelfde dispatch als altijd."""
    if rw and hid is not None and trekker_opts:
        return (f"<form method='post' action='/action' class='mform'>{hid()}"
                f"<input type='hidden' name='action' value='proj_settrekker'>"
                f"<select class='ctrl' name='trekker' onchange='{_AUTOSAVE}'>{trekker_opts}</select>"
                f"</form>")
    if p.get("agent"):
        persona = st.personas.get(p["agent"])
        naam = ((persona or {}).get("name") if isinstance(persona, dict)
                else getattr(persona, "name", "")) or "AI"
        return (f"<span class='ctrl'><span class='av ai'>{_e(_initials(naam))}</span>"
                f"{_e(naam)}</span>")
    if p.get("person"):
        naam = _person_name(st, p["person"]) or "—"
        return (f"<span class='ctrl'><span class='av'>{_e(_initials(naam))}</span>{_e(naam)}</span>")
    return "<span class='ctrl muted'>nobody yet</span>"


def render_project(st: _Stores, pid: str, csrf_token: str = "", msg: str = "", back: str = "/",
                   fragment: bool = False, username: str | None = None) -> str:
    p = st.projects.get(pid)
    if p is None:
        if fragment:
            return "<p class='muted'>Project no longer exists.</p>"
        return _page("Not found", "<p>Project not found.</p><p><a href='/'>← home</a></p>")
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

    # ---- ⋯ Meer: alleen ACTIES (archiveren, verwijderen) ----
    # De status-items zijn hiéruit verhuisd naar de Status-chip. Wat overblijft is geen eigenschap
    # van het project maar iets wat je ermee DOET — dat is precies de scheiding die de rail bedoelt.
    menu = ""
    if rw:
        menu = (f"<details class='cardmenu'><summary class='meertrigger' aria-label='more actions'>⋯</summary>"
                f"<div class='cardmenu-b'>"
                f"<form method='post' action='/action'>{hid()}<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='menuitem' type='submit' name='action' value='proj_archive'>Archive</button></form>"
                f"<form method='post' action='/action'>{hid()}<input type='hidden' name='next' value='{_e(back)}'>"
                f"<button class='menuitem danger' type='submit' name='action' value='proj_delete' "
                f"onclick=\"return confirm('Delete permanently? Archiving keeps the project.')\">Delete</button>"
                f"</form></div></details>")

    # ---- Titel (inline bewerkbaar) ----
    if rw:
        title = (f"<form method='post' action='/action' class='titleform'>{hid()}"
                 f"<input class='title-edit' name='scope' value='{_e(_scope_text(p))}' aria-label='project title'>"
                 f"<button class='btn ok sm title-save' type='submit' name='action' value='proj_rename'>save</button></form>")
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
                  f"<button class='dellink' type='submit'>clear date</button></form>")
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
    # De herkomst-chip staat naast de status: bij review kijk je hier, niet pas onderin het document.
    # ALLEEN DE TITEL. Deadline, status en het ⋯-menu stonden hier én in de nieuwe chips-rij/rail;
    # de screenshot liet drie dubbelingen zien. Twee plekken voor hetzelfde veld is hoe een scherm
    # zichzelf tegenspreekt — zelfde reden als waarom de trekker uit de rail ging.
    head = f"<div class='pcard-head'>{title}</div>"

    # ═══ RECHTS: STRUCTUUR (sticky kantlijn) ═══════════════════════════════════════════
    # 1) Projectdetails (rol+dangling, trekker, aangemaakt, zichtbaar, impacts, effort-buckets)
    owner = p.get("owner", "")
    is_ii = owner.startswith(_II_PREFIX)
    dangling = bool(owner) and not is_ii and orec is None
    rol_naam = "Individual Action" if is_ii else (_name(orec) if orec else (owner or "—"))
    if rw and not is_ii:
        warn = ("<div class='dangling-warn'><span class='chip coral-solid'>"
                "⚠ role no longer exists — pick a new one</span></div>") if dangling else ""
        # scope de owner-dropdown op de cirkel waar dit project hangt (= ouder-cirkel van de owner-rol)
        owner_circle = orec.parent if orec else None
        rol_v = (f"{warn}<form method='post' action='/action' class='fieldform'>{hid()}"
                 f"<input type='hidden' name='action' value='proj_setowner'>"
                 f"<select name='owner' onchange='{_AUTOSAVE}'>{_owner_options(st, owner, circle=owner_circle)}</select></form>")
    else:
        rol_v = (f"<a href='/node?id={_e(owner)}'>{_e(rol_naam)}</a>" if orec else _e(rol_naam))
    # De trekker-opties: één bron, twee gebruikers (de chip in de header en — read-only — de rail).
    _trekker_opts_html = (_trekker_options(st, owner, p.get("person") or "", p.get("agent") or "")
                          if rw else "")
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
        # EEN TOGGLE, GEEN VINKJE MET EEN ZIN ERNAAST. Zichtbaar is de normale toestand; de actie
        # die je soms wilt is verbergen. Het vinkje "only for this circle" vroeg je om een
        # negatieve eigenschap aan te zetten — een omweg om te zeggen "hou dit binnen".
        _verborgen = bool(p.get("private"))
        vis_v = (f"<form method='post' action='/action' class='mform'>{hid()}"
                 f"<input type='hidden' name='action' value='proj_setprivate'>"
                 f"<input type='hidden' name='private' value='{'' if _verborgen else '1'}'>"
                 f"<button class='ctrl' type='submit' "
                 f"title='{'Make visible to the whole circle tree' if _verborgen else 'Hide from other circles'}'>"
                 f"{'Only this circle' if _verborgen else 'Whole circle tree'}</button></form>")
    else:
        vis_v = "Only for this circle" if p.get("private") else "Whole circle tree"
    verzwakt_block = _verzwakt_block(p, hid, rw) if p.get("missie_impact") == "verzwakt" else ""
    # LABEL EN CONTROL OP ÉÉN REGEL. Hier stond `w = " wide"`, dat vijf van de zeven rijen
    # tweeregelig maakte: label op een eigen regel, dropdown op volle breedte eronder. Voor twee
    # velden was dat uitlijning (#154, waar Rol/Trekker gelijkgetrokken werden); bij vijf velden
    # stapelt het tot tien regels en tien volle-breedte-controls — de "zware kolom" waar Stefan
    # over viel. De dropdowns zelf blijven, en daarmee de uniformiteit die #154 maakte; alleen de
    # kolom wordt half zo hoog.
    w = ""
    details_dcol = (
        f"<div class='dcol'>"
        f"<span class='dk{w}'>Role</span><span class='dv{w}'>{rol_v}</span>"
        f"<span class='dk{w}'>Owner</span><span class='dv{w}'>{pers_v}</span>"
        f"<span class='dk'>Created</span><span class='dv'>{_e(_created_full(p.get('created_at')))}</span>"
        f"<span class='dk'>Visible</span><span class='dv'>{vis_v}</span>"
        f"<span class='dk{w}'>Mission impact</span><span class='dv{w}'>{_impact_select(p, 'missie_impact', 'missie', _MISSIE_OPTS, rw, hid)}</span>"
        f"<span class='dk{w}'>Business impact</span><span class='dv{w}'>{_impact_select(p, 'business_impact', 'business', _BUSINESS_OPTS, rw, hid)}</span>"
        f"<span class='dk{w}'>Effort</span><span class='dv{w}'>{_effort_control(p, rw, hid)}</span>"
        f"</div>")
    details_panel = _psec(_IC_INFO, "Project details", details_dcol + verzwakt_block)

    # 1b) De DoD-contract-box is vervallen (founder, 21 jul): de 'klaar wanneer' (uitgebreide DoD)
    # staat nu als kop van het einddocument (direct onder de titel), en de projectpoort is
    # De poort die daarbij hoorde (projects.dod_poort) is 4 sep 2026 ingetrokken:
    # een Done vereist geen einddocument. Zie tests/test_project_dod_poort.py.

    # 2) Checklist — vier onderscheidbare states + skill/payload (zie _checklists_html)
    checklists_html = _checklists_html(p, csrf_token, pid, back, rw, st=st)
    cl_new = ""
    if rw:
        # GEEN NAAMVELD MEER. Vrijwel elke lijst heette iets als "Acties uit overleg" of "Stappen"
        # — een naam die niemand leest en die je wel moet verzinnen vóór je je eerste taak kwijt
        # kunt. De naam is nu "tasks" en de knop maakt de lijst in één klik.
        cl_new = (f"<form method='post' action='/action' class='pf cl-newlist'>{hid()}"
                  f"<input type='hidden' name='title' value='tasks'>"
                  f"<button class='flink' type='submit' name='action' value='checklist_add'>"
                  f"+ new checklist</button></form>")
    cl_inner = (checklists_html or "<p class='muted'>No checklist yet.</p>") + cl_new
    checklist_panel = _psec(_IC_CHECK, "Checklist", cl_inner)

    # 3) Doel & relaties — placeholder (functie later)
    goal_knop = (f"<button type='button' class='rail-btn' disabled>{_IC_TARGET}"
                 f"<span>Link to goal · soon</span></button>")
    # ═══ DE RAIL: licht, één regel per veld, waarde rechts ════════════════════════════
    # De meta stond in .dcol-rijen die de kolom zwaar maakten. Wat naar de header verhuisde
    # (impact, business, inzet, status, trekker) staat hier NIET meer — twee plekken voor hetzelfde
    # veld is hoe een scherm zichzelf tegenspreekt. Wat hier blijft is wat de header niet draagt.
    # ═══ DE RAIL: ÉÉN HUIS VOOR ALLE META ═════════════════════════════════════════════
    # Status, assignee, impact, business en effort stonden in een pillenrij BOVEN de content. Die
    # rij duwde de inhoud omlaag, en status — het veld dat je het vaakst verandert — verdween uit
    # beeld zodra je naar de conversatie scrollde. Alles staat nu bij elkaar in een sticky rail;
    # `_meta_rijen` draagt de vijf verhuisde controls, de regels hieronder de rest.
    #
    # ARCHIEF EN VERWIJDEREN KRIJGEN EEN VASTE PLEK, onderaan de rail achter een scheiding. Ze
    # stonden onder een wall die met elk gesprek langer wordt; een actie die verder wegzakt naarmate
    # een project meer leeft, is geen bereikbare actie.
    rail = (f"<div class='rail-kop'>Details</div>"
            + _meta_rijen(st, p, rw, hid, _trekker_opts_html)
            + _meta_rij("Role", rol_v)
            + _meta_rij("Deadline", due_head or "—")
            + _meta_rij("Visible", vis_v)
            + _meta_rij("Created", _created_full(p.get("created_at")))
            + f"<div class='railsplit'></div>"
            + f"<div class='rail-acties'>{goal_knop}</div>"
            + (f"<div class='rail-kop rail-kop2'>More</div>"
               f"<div class='rail-meer'>{menu}</div>" if menu else ""))
    structure = rail

    # ═══ LINKS: WALL — inhoud & gesprek in tijdsvolgorde ═══════════════════════════════
    composer = ""
    if rw:
        nxt_full = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        bijlage = (f"<details class='acard-d comp-attach'><summary class='flink'>📎 attachment</summary>"
                   f"<div class='datepop att-pop'>"
                   f"<form method='post' action='/action' enctype='multipart/form-data' class='filepost'>"
                   f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                   f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                   f"<input type='hidden' name='action' value='attach_file'>"
                   f"<input type='hidden' name='next' value='{_e(nxt_full)}'>"
                   f"<label class='att-lbl'>File from your computer</label>"
                   f"<input type='file' name='file'>"
                   f"<button class='btn ok sm' type='submit'>Upload</button></form>"
                   f"<div class='att-sep'></div>"
                   f"<form method='post' action='/action'>{hid()}"
                   f"<label class='att-lbl'>Or paste a link</label>"
                   f"<input name='url' placeholder='https://…'>"
                   f"<input name='title' placeholder='Name (optional)'>"
                   f"<button class='btn ok sm' type='submit' name='action' value='attach_add'>Add</button></form>"
                   f"</div></details>")
        # De toolbar-rij (bijlage + Plaatsen) staat BUITEN de composer-form. Anders zit het upload-form
        # (class='filepost', multipart) genest ín comp-form — ongeldige HTML → de browser dropt de inner
        # form → de File wordt niet als multipart verstuurd (form-encoded, bestand valt weg). Plaatsen
        # submit de composer via het form=-attribuut; de bijlage is nu een eigen sibling-form.
        _cfid = f"cf-{_e(pid)}"
        # JIJ SCHRIJFT DIT, EN JE KUNT IEMAND VRAGEN. De composer was een kaal veld met een
        # abstracte uitleg ("@name asks an inhabitant"). Een avatar maakt zichtbaar dat het jouw
        # stem is, en echte namen maken de @-hint een uitnodiging in plaats van een instructie.
        # Bewust GEEN gok op de avatar: zonder ingelogde persoon staat er niets, want een verkeerd
        # initiaal is erger dan geen.
        _ik = st.people.by_email(username) if username and username != "guest" else None
        _av = (f"<span class='av' title='{_e(_ik.name)}'>{_e(_initials(_ik.name))}</span>"
               if _ik else "")
        _tagbaar = ", ".join(f"@{n}" for n in _ai_namen(st)[:2])
        # "Steer via the checklist" stond in het oude label en is GEEN decoratie: het zegt waar
        # sturen gebeurt, en dat is niet in het gesprek. Bij het lichter maken van het label viel
        # hij er bijna uit; hij hoort in de hint, naast de @-uitnodiging.
        _tip = (f"Tip: noem {_tagbaar} om een AI-collega mee te laten kijken. " if _tagbaar else "")
        _hint = f"<span class='muted comp-hint'>{_tip}Steer via the checklist.</span>"
        composer = (f"<form id='{_cfid}' method='post' action='/action' class='pf comp-form'>{hid()}"
                    f"<input type='hidden' name='author' value='human:'>"
                    # Het label "Conversation" stond hier én als sectiekop erboven. De sectiekop is de kop;
                    # wat hier hoort is wie er schrijft, niet nog een keer waar je bent.
                    f"<div class='comp-head'>{_av}</div>"
                    f"{md_editor('text', rows=2, placeholder='Write a reply, or ask a colleague to weigh in…', help=True)}"
                    f"{_hint}"
                    f"</form>"
                    f"<div class='comp-row'>"
                    f"{bijlage}"                                    # bijlage links op de toolbar-rij (eigen form)…
                    f"<button class='btn ok sm' type='submit' form='{_cfid}' name='action' value='proj_feed'>Post</button>"
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
    wall = (f"{composer}<div class='wall-scroll'>{stream_html}</div>")

    # ---- Bovenrand/labels + werkoverleg-CTA (conditioneel) ----
    labelbar = ""
    if _LABELS.get(p.get("label")):
        labelbar = f"<div class='clabel' style='background:{_LABELS[p['label']]};height:8px;border-radius:4px;margin-bottom:.6rem'></div>"
    meeting = back.startswith("/werkoverleg")
    wo_cta = (f"<a class='btn ok sm js-modal' href='{_e(back)}' data-href='{_e(back)}'>"
              f"← back to tactical meeting</a>") if meeting else ""
    top_bar = f"<div class='wo-back-bar'>{wo_cta}</div>" if meeting else ""
    foot_bar = f"<div class='wo-back-bar wo-back-foot'>{wo_cta}</div>" if meeting else ""

    einddoc_body, einddoc_acties = _einddocument_delen(st, pid, rw, hid, back)
    # ═══ DE HERINDELING ═══════════════════════════════════════════════════════════════
    # Header (crumb + titel + chips), dan drie secties in de hoofdkolom en een lichte rail. De
    # oude koppen "END DOCUMENT" en "WALL — CONTENT & CONVERSATION" zijn weg: ze schreeuwden en
    # zeiden niets over de inhoud eronder.
    _crumb = (f"<div class='pkaart-crumb'>{_e(_name(orec) if orec else (owner or 'project'))} "
              f"· project</div>")
    # ALLEEN DE TITEL BOVENAAN. De pillenrij is weg; alle meta staat rechts. Het verzwakt-blok
    # blijft hier: het is een SIGNAAL over dit project, geen instelbaar veld, en het hoort gezien te
    # worden zonder dat je de rail afgaat. (Het verdween ooit met de .dcol en werd onbereikbaar —
    # de suite ving dat, en die eis geldt nog steeds.)
    kop = f"<div class='pkaart-head'>{_crumb}{head}{_herkomst_chip(st, pid)}{verzwakt_block}</div>"
    secties = (_psectie("Description", einddoc_body, acties=einddoc_acties)
               # "+ new checklist" stond in de rail onder "Add". Hij hoort bij de checklist waar hij
               # iets aan toevoegt — zo staat het ook in de mock.
               + _psectie("Checklist", checklists_html, bijschrift="actions from the meeting",
                          acties=cl_new)
               + _psectie("Conversation", wall))
    detail = (f"{top_bar}{labelbar}{_banner(msg)}"
              f"<div class='pkaart'>{kop}"
              f"<div class='pkaart-body'><div class='pkaart-main'>{secties}</div>"
              f"<aside class='pkaart-rail'>{structure}</aside></div></div>{foot_bar}")
    if fragment:
        return f"<div data-noclose='1'>{detail}</div>" if meeting else detail
    main = (f"<div class='c2-main pdetail'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← back</a></div>{detail}</div>")
    inner = (f"{_DS_LINK}"
             f"{_nav('projectdetail')}"
             f"<div class='c2-wrap'>{main}</div>")
    return _page(_scope_text(p), inner)




