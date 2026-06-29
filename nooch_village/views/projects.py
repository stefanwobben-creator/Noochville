"""Project-views — brok 9 van de cockpit2-split."""
from __future__ import annotations

import json
import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.cockpit import _e, _page, _banner
from nooch_village.cockpit2_util import (
    _name, _initials, _age, _fmt_due, _created_full,
    _link_host, _psec, _person_name,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK,
    _IC_DESC, _IC_CLOCK, _IC_FILE, _IC_TARGET,
)
from nooch_village.views.feed import _mentionables, _feed_entry_html
from nooch_village.views.checklists import _checklists_html
from nooch_village import org
from nooch_village.cockpit2_util import _EXTRA_CSS

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


def _trekker_options(st: _Stores, sel_person="", sel_agent="") -> str:
    out = ["<option value=''>— geen trekker —</option>"]
    for pr in st.people.all():
        s = " selected" if pr.id == sel_person else ""
        out.append(f"<option value='person:{_e(pr.id)}'{s}>{_e(pr.name)}</option>")
    for pa in st.personas.all():
        s = " selected" if pa.id == sel_agent else ""
        out.append(f"<option value='persona:{_e(pa.id)}'{s}>🤖 {_e(pa.name)} (AI)</option>")
    return "".join(out)


def _owner_options(st: _Stores, sel_owner="") -> str:
    """Alle rollen (geen cirkels) als opties om een project naar een andere rol te verplaatsen.
    Cirkels doen geen uitvoerend werk, dus die staan niet in de lijst."""
    roles = [r for r in st.records.all() if not org.is_circle(r)]
    roles.sort(key=lambda r: _name(r).lower())
    out = []
    if sel_owner and st.records.get(sel_owner) is None:
        # huidige eigenaar bestaat niet meer (dangling) — toon dat expliciet en geselecteerd
        out.append(f"<option value='{_e(sel_owner)}' selected>⚠ {_e(sel_owner)} (bestaat niet meer)</option>")
    for r in roles:
        s = " selected" if r.id == sel_owner else ""
        out.append(f"<option value='{_e(r.id)}'{s}>{_e(_name(r))}</option>")
    return "".join(out)


_PROJ_COLS = [("Actief", "actief", ("running", "queued")), ("Wacht", "wacht", ("blocked",)),
              ("Done", "done", ("done",)), ("Toekomst", "toekomst", ("future",))]


_LABELS = {"groen": "#1F9D55", "geel": "#FFCE2E", "koraal": "#FF6B5B",
           "blauw": "#2B5BB5", "paars": "#7A5BD1", "": ""}


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
    bar = ""
    if p.get("label") in _LABELS and _LABELS.get(p.get("label")):
        bar = f"<div class='clabel' style='background:{_LABELS[p['label']]}'></div>"
    meta = (f"<div class='muted' style='font-size:.72rem;margin-top:.25rem'>"
            f"{_trekker_html(st, p)} · {_e(_age(p.get('created_at')))}</div>")
    drag = ' draggable="true"' if csrf_token else ''
    return (f"<div class='card pcard' data-pid='{_e(pid)}' data-href='{href}'{drag}>"
            f"{bar}<div class='ptitle'>{_e(_scope_text(p))}</div>{meta}{_progress_badge(p)}</div>")


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
        f"<div class='qadd-row'>"
        f"<button class='btn ok' type='submit' name='action' value='proj_add'>Project toevoegen</button>"
        f"<button type='button' class='qadd-x' onclick=\"this.closest('details').open=false\" "
        f"aria-label='annuleren'>✕</button></div>"
        f"</form></details>")


def _inline_add_project(st: _Stores, rec, csrf_token: str, back: str) -> str:
    """Universele inline '+ project' (één patroon, geen aparte modal). Op een cirkel kies je de rol;
    op een rol staat de eigenaar vast. Dekt ook lege rollen/cirkels die per-kolom-quickadd mist."""
    if not csrf_token:
        return ""
    if org.is_circle(rec):
        roles = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
        ro = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
        owner_field = f"<label class='att-lbl'>Rol</label><select name='owner'>{ro}</select>"
    else:
        owner_field = f"<input type='hidden' name='owner' value='{_e(rec.id)}'>"
    return (
        f"<details class='qadd qadd-top'><summary>+ project</summary>"
        f"<form method='post' action='/action' class='qadd-form'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='next' value='{_e(back)}'>"
        f"<textarea name='scope' rows='2' placeholder='Te bereiken uitkomst…' aria-label='nieuw project'></textarea>"
        f"{owner_field}"
        f"<label class='att-lbl'>Status</label><select name='col'>"
        f"<option value='actief'>Actief</option><option value='wacht'>Wacht</option>"
        f"<option value='toekomst'>Toekomst</option></select>"
        f"<label class='att-lbl'>Trekker (persoon of AI)</label><select name='trekker'>{_trekker_options(st)}</select>"
        f"<div class='qadd-row'><button class='btn ok' type='submit' name='action' value='proj_add'>"
        f"Project toevoegen</button></div></form></details>")


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
        f"window.__mentions={mentions_json};"
        "window.wrapSel=function(btn,pre,post){var f=btn.closest('form');var t=f&&f.querySelector('textarea');"
        "if(!t)return;var s=t.selectionStart,e=t.selectionEnd,v=t.value;"
        "t.value=v.slice(0,s)+pre+v.slice(s,e)+post+v.slice(e);t.focus();"
        "t.selectionStart=s+pre.length;t.selectionEnd=e+pre.length;};"
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
        "function openCard(u){last=u;"
        "fetch(frag(u)).then(function(r){return r.text();}).then(function(h){bd.innerHTML=h;ov.style.display='flex';"
        "window.__noclose=!!bd.querySelector('[data-noclose]');"
        "var xb=document.querySelector('.ovl-x');if(xb)xb.style.display=window.__noclose?'none':'';wire();});}"
        "function reopen(){if(last)openCard(last);}"
        "function shut(){ov.style.display='none';bd.innerHTML='';if(dirty){dirty=false;location.reload();}}"
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
        "fetch('/action',opts).then(function(){"
        "if(act==='wo_close'||act==='rov2_end'){confetti();setTimeout(shut,700);}"
        "else if(act==='proj_delete'||act==='proj_archive'||act==='proj_add'){shut();}"
        "else{var r=f.getAttribute('data-reopen');if(r){last=r;}reopen();toast('\\u2713 opgeslagen');}});});});"
        "bd.querySelectorAll('textarea').forEach(mentionWire);"
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
        "fetch('/action',{method:'POST',body:d}).then(function(){reopen();toast('\\u2713 verplaatst');});});});"
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
            return (("ii", owner), "zzz", "Individual Initiative", owner, "")
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
    return (f"<details style='margin-top:.6rem'><summary>🗄 Gearchiveerd ({len(archived)})</summary>"
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
    return (f"<details open style='margin:.6rem 0'><summary>📝 Concepten — wachten op akkoord "
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


def _projects_tab_html(st: _Stores, rec, csrf_token: str, group: str = "", add: bool = True) -> str:
    allp = st.projects.all()
    back_base = f"/node?id={rec.id}&tab=projects"

    addlink = _inline_add_project(st, rec, csrf_token, back_base) if add else ""

    if not org.is_circle(rec):
        # ROL: eigen projecten, gegroepeerd per persoon (de doener). Lege lanes tonen we niet.
        mine = [p for p in allp if p.get("owner") == rec.id and not p.get("archived")]
        projs = [p for p in mine if p.get("status") != "draft"]
        drafts = [p for p in mine if p.get("status") == "draft"]
        archived = [p for p in allp if p.get("owner") == rec.id and p.get("archived")]
        board = _projects_board(st, projs, rec.id, csrf_token, back_base, "persoon", quickadd=add)
        if not board:
            board = ("<p class='muted'>Nog geen projecten. Voeg er een toe met + project.</p>" if add
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
        board = ("<p class='muted'>Nog geen projecten. Voeg er een toe met + project.</p>" if add
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


def _person_projects_html(st: _Stores, pid: str) -> str:
    role_ids = set(st.assign.roles_of("person", pid))
    projs = [p for p in st.projects.all()
             if not p.get("archived") and (p.get("person") == pid or p.get("owner") in role_ids)]
    projs.sort(key=lambda p: (p.get("status") == "done", -(p.get("created_at") or 0)))
    if not projs:
        return ""
    items = ""
    for p in projs:
        orec = st.records.get(p.get("owner"))
        owner = _e(_name(orec) if orec else (p.get("owner") or ""))
        scope = p.get("scope")
        if isinstance(scope, dict):
            scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
        items += (f"<li>{_proj_chip(p.get('status',''))} {_e(str(scope or '—'))} "
                  f"<span class='muted'>· {owner}</span></li>")
    return f"<div class='c2-sec'><h3>Projecten ({len(projs)})</h3><ul class='clean'>{items}</ul></div>"


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
    from nooch_village.cockpit2 import _owner_ai

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='next' value='{_e(f'/project?pid={pid}&back=' + urllib.parse.quote(back, safe=''))}'>")

    status = p.get("status", "")

    # ---- Rechterkolom: de dialoog (mensen + AI) ----
    role_name = _name(orec) if orec else ""
    mention_names = [m["l"] for m in _mentionables(st)[0]]   # voor highlight in de bubble
    # Nieuwste boven.
    feed = "".join(_feed_entry_html(st, m, role_name=role_name, pid=pid, csrf_token=csrf_token,
                                    mention_names=mention_names)
                   for m in reversed(p.get("log") or []))
    if not feed:
        feed = "<p class='muted'>Nog geen updates of reacties.</p>"
    composer = ""
    if rw:
        # Directe textarea met mini-toolbar op de gele achtergrond; Plaatsen links uitgelijnd.
        composer = (f"<form method='post' action='/action' class='pf comp-form'>{hid()}"
                    f"<input type='hidden' name='author' value='human:'>"
                    f"<div class='editor'>"
                    f"<div class='editor-tb'>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'**','**')\" title='Vet'><b>B</b></button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'*','*')\" title='Cursief'><i>I</i></button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'~~','~~')\" title='Doorhalen'><s>S</s></button>"
                    f"<span class='tb-sep'></span>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'- ','')\" title='Lijst'>•</button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'## ','')\" title='Kop'>H</button>"
                    f"<button type='button' class='tb-b' onclick=\"wrapSel(this,'[','](url)')\" title='Link'>{_IC_LINK}</button>"
                    f"<details class='emoji-pick tb-help'><summary title='Opmaak-hulp'>?</summary>"
                    f"<div class='md-help'>**vet** · *cursief* · ~~doorhalen~~ · # kop · - lijst · [tekst](url)</div>"
                    f"</details></div>"
                    f"<textarea name='text' rows='2' placeholder='Schrijf een reactie…'></textarea>"
                    f"</div>"
                    f"<div class='comp-row'>"
                    f"<button class='btn ok sm' type='submit' name='action' value='proj_feed'>Plaatsen</button>"
                    f"</div></form>")
        ai = _owner_ai(st, orec)
        if ai is not None:
            composer += (f"<form method='post' action='/action' class='ai-ask'>{hid()}"
                         f"<button class='btn ghost sm ai-ask-btn' type='submit' name='action' value='ai_reply'>"
                         f"🤖 Vraag {_e(ai.name)} om mee te denken</button></form>")
    discussie = _psec(_IC_CHAT, "Dialoog", composer + feed)   # schrijf-box boven, reacties eronder

    # ---- Status zit volledig in het …-menu (huidige status gemarkeerd); geen los chip-label ----
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

    # ---- Header (volledige breedte): titel inline + status + …-menu ----
    if rw:
        title = (f"<form method='post' action='/action' class='titleform'>{hid()}"
                 f"<input class='title-edit' name='scope' value='{_e(_scope_text(p))}' aria-label='projecttitel'>"
                 f"<button class='btn ok sm title-save' type='submit' name='action' value='proj_rename'>opslaan</button></form>")
    else:
        title = f"<h2 class='ptitle-ro'>{_e(_scope_text(p))}</h2>"
    # Deadline-chip vóór de status (overzicht), met Overdue-markering.
    due_head = ""
    if p.get("due"):
        over = _due_overdue(p["due"])
        badge = "<span class='chip coral-solid'>Overdue</span>" if over else ""
        due_head = (f"<span class='chip {'coral' if over else 'outline'}'>"
                    f"{_IC_CLOCK}{_e(_fmt_due(p['due']))}</span>{badge}")
    head = (f"<div class='pcard-head'>{title}"
            f"<div class='pcard-head-r'>{due_head}{menu or _proj_chip(status)}</div></div>")

    # ---- Details: kader zonder achtergrond, tweekoloms, links uitgelijnd, altijd open ----
    owner = p.get("owner", "")
    is_ii = owner.startswith(_II_PREFIX)
    dangling = bool(owner) and not is_ii and orec is None
    if is_ii:
        rol_naam = "Individual Initiative"
    else:
        rol_naam = _name(orec) if orec else (owner or "—")
    if rw and not is_ii:
        # Rol verplaatsen: keuzelijst van rollen, direct opslaan bij wijziging.
        warn = ("<span class='chip coral-solid' style='margin-bottom:.3rem'>"
                "⚠ rol bestaat niet meer — kies een nieuwe</span>") if dangling else ""
        rol_v = (f"{warn}<form method='post' action='/action' class='ownerform'>{hid()}"
                 f"<select name='owner' "
                 f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
                 f"{_owner_options(st, owner)}</select>"
                 f"<button type='submit' name='action' value='proj_setowner' "
                 f"class='btn sm' style='margin-left:.3rem'>verplaats</button></form>")
    else:
        rol_v = (f"<a href='/node?id={_e(owner)}'>{_e(rol_naam)}</a>" if orec else _e(rol_naam))
    if rw:
        # Persoon/AI (trekker) wijzigen: keuzelijst, direct opslaan bij wijziging.
        pers_v = (f"<form method='post' action='/action' class='trekkerform'>{hid()}"
                  f"<select name='trekker' "
                  f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
                  f"{_trekker_options(st, p.get('person') or '', p.get('agent') or '')}</select>"
                  f"<button type='submit' name='action' value='proj_settrekker' "
                  f"class='btn sm' style='margin-left:.3rem'>wijzig</button></form>")
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
    details = (
        f"<div class='detailsbox'><div class='psec-h'>{_IC_INFO}<span>Details</span></div>"
        f"<div class='dcol'>"
        f"<span class='dk'>Rol</span><span class='dv'>{rol_v}</span>"
        f"<span class='dk'>Persoon</span><span class='dv'>{pers_v}</span>"
        f"<span class='dk'>Aangemaakt</span><span class='dv'>{_e(_created_full(p.get('created_at')))}</span>"
        f"<span class='dk'>Zichtbaar</span><span class='dv'>{vis_v}</span>"
        f"</div></div>")

    # ---- Omschrijving (inline, omkaderd) ----
    if rw:
        desc_body = (f"<form method='post' action='/action' class='descform'>{hid()}"
                     f"<textarea name='description' rows='3' placeholder='Voeg een omschrijving toe…'>"
                     f"{_e(p.get('description',''))}</textarea>"
                     f"<button class='btn ok' type='submit' name='action' value='proj_describe' "
                     f"style='margin-top:.3rem'>opslaan</button></form>")
    else:
        desc_body = f"<div>{_e(p.get('description','')) or '<span class=muted>geen omschrijving</span>'}</div>"
    omschrijving = _psec(_IC_DESC, "Omschrijving", desc_body)

    # ---- Bijlagen-overzicht: Links + Bestanden (card-pattern). Toevoegen via de Bijlage-kaart. ----
    def _att_rm(aid):
        return ("" if not rw else
                f"<form method='post' action='/action' class='att-x'>{hid()}"
                f"<input type='hidden' name='aid' value='{_e(aid)}'>"
                f"<button class='dellink' type='submit' name='action' value='attach_remove' "
                f"title='verwijderen'>✕</button></form>")
    link_cards, file_cards = "", ""
    for a in (p.get("attachments") or []):
        if a.get("kind", "link") == "file":
            nm = a.get("title") or a.get("name", "bestand")
            href = f"/file?pid={_e(pid)}&aid={_e(a.get('id', ''))}"
            file_cards += (f"<div class='attcard'><span class='att-ic'>{_IC_FILE}</span>"
                           f"<a class='att-name' href='{href}' target='_blank' rel='noopener'>{_e(nm)}</a>"
                           f"{_att_rm(a.get('id', ''))}</div>")
        else:
            nm = a.get("title") or _link_host(a.get("url", ""))
            link_cards += (f"<div class='attcard'><span class='att-ic'>{_IC_LINK}</span>"
                           f"<a class='att-name' href='{_e(a.get('url', ''))}' target='_blank' rel='noopener'>{_e(nm)}</a>"
                           f"{_att_rm(a.get('id', ''))}</div>")
    verrijking = ""
    if link_cards:
        verrijking += _psec(_IC_LINK, "Links", link_cards)
    if file_cards:
        verrijking += _psec(_IC_FILE, "Bijlagen", file_cards)

    checklists_html = _checklists_html(p, csrf_token, pid, back, rw)

    # ---- Actie-kaarten (Trello 'Add to card') ----
    actioncards = ""
    if rw:
        due = p.get("due") or ""
        due_lbl = _fmt_due(due) or "Datum"
        date_rm = ("" if not due else
                   f"<form method='post' action='/action' style='margin-top:.5rem'>{hid()}"
                   f"<input type='hidden' name='action' value='proj_setdue'>"
                   f"<input type='hidden' name='due' value=''>"
                   f"<button class='dellink' type='submit'>datum verwijderen</button></form>")
        date_card = (
            f"<details class='acard-d'><summary class='acard'>"
            f"{_IC_CLOCK}<span>{_e(due_lbl)}</span></summary>"
            f"<div class='datepop'><form method='post' action='/action'>{hid()}"
            f"<input type='hidden' name='action' value='proj_setdue'>"
            f"<input type='date' name='due' value='{_e(due)}' "
            f"onchange='this.form.requestSubmit?this.form.requestSubmit():this.form.submit()'>"
            f"</form>{date_rm}</div></details>")
        checklist_card = (
            f"<details class='acard-d'><summary class='acard'>{_IC_CHECK}<span>Checklist</span></summary>"
            f"<div class='datepop'><form method='post' action='/action'>{hid()}"
            f"<input name='title' placeholder='Naam checklist'>"
            f"<button class='btn ok' type='submit' name='action' value='checklist_add' "
            f"style='margin-left:.4rem'>Voeg toe</button></form></div></details>")
        nxt_full = f"/project?pid={pid}&back=" + urllib.parse.quote(back, safe="")
        bijlage_card = (
            f"<details class='acard-d'><summary class='acard'>{_IC_LINK}<span>Bijlage</span></summary>"
            f"<div class='datepop att-pop'>"
            f"<form method='post' action='/action' enctype='multipart/form-data' class='filepost'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='pid' value='{_e(pid)}'>"
            f"<input type='hidden' name='action' value='attach_file'>"
            f"<input type='hidden' name='next' value='{_e(nxt_full)}'>"
            f"<label class='att-lbl'>Bestand van je computer</label>"
            f"<input type='file' name='file'>"
            f"<button class='btn ok sm' type='submit' style='margin-top:.4rem'>Upload</button></form>"
            f"<div class='att-sep'></div>"
            f"<form method='post' action='/action'>{hid()}"
            f"<label class='att-lbl'>Of een link plakken</label>"
            f"<input name='url' placeholder='https://…'>"
            f"<input name='title' placeholder='Naam (optioneel)' style='margin-top:.3rem'>"
            f"<button class='btn ok sm' type='submit' name='action' value='attach_add' "
            f"style='margin-top:.4rem'>Toevoegen</button></form>"
            f"</div></details>")
        actioncards = (
            "<div class='actioncards'>"
            f"{date_card}{checklist_card}{bijlage_card}"
            f"<button type='button' class='acard acard-off' disabled "
            f"title='binnenkort'>{_IC_TARGET}<span>Goals</span></button>"
            "</div>")

    labelbar = ""
    if _LABELS.get(p.get("label")):
        labelbar = f"<div class='clabel' style='background:{_LABELS[p['label']]};height:8px;border-radius:4px;margin-bottom:.6rem'></div>"

    # Geopend vanuit het werkoverleg: prominente terug-CTA boven én onder; het kruisje wordt
    # uitgeschakeld (zie modal-JS via data-noclose) zodat je via deze CTA terugkeert.
    meeting = back.startswith("/werkoverleg")
    wo_cta = (f"<a class='btn ok sm js-modal' href='{_e(back)}' data-href='{_e(back)}'>"
              f"← terug naar werkoverleg</a>") if meeting else ""
    top_bar = f"<div class='wo-back-bar'>{wo_cta}</div>" if meeting else ""
    foot_bar = f"<div class='wo-back-bar wo-back-foot'>{wo_cta}</div>" if meeting else ""

    maincol = details + actioncards + omschrijving + checklists_html + verrijking
    detail = (f"{top_bar}{labelbar}{_banner(msg)}{head}"
              f"<div class='pgrid'><div class='pmain'>{maincol}</div>"
              f"<aside class='pdisc'>{discussie}</aside></div>{foot_bar}")
    if fragment:
        return f"<div data-noclose='1'>{detail}</div>" if meeting else detail
    main = (f"<div class='c2-main' style='max-width:980px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{detail}</div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · projectdetail · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page(_scope_text(p), inner)




