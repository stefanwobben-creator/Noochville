"""Overview-views — brok 10 van de cockpit2-split."""
from __future__ import annotations

import json
import urllib.parse
from typing import TYPE_CHECKING

from nooch_village.cockpit import _e, _page, _banner
from nooch_village.cockpit2_util import (
    _name, _initials, _tabbar, _todo, _avatar, _age,
    _psec, _person_name, _ICON_ADD_EMOJI,
    _IC_CHECK, _IC_CLOCK, _IC_LINK, _IC_TARGET,
)
from nooch_village.views.feed import _mentionables
from nooch_village.views.checklists import _checklists_tab_html
from nooch_village.views.metrics import _metrics_tab_html
from nooch_village.views.strategy import _strategy_tab_html
from nooch_village.views.backlog import render_backlog_tab
from nooch_village.views.projects import (
    _projects_tab_html, _scope_text, _person_projects_html, _modal_html,
)
from nooch_village import org, ai_match
from nooch_village.cockpit2_util import _EXTRA_CSS, _BUILD, _CIRCLE_TABS, _ROLE_TABS, WEBSITE_DEVELOPER_ROLE

if TYPE_CHECKING:
    from nooch_village.cockpit2 import _Stores

def _filler_html(st: _Stores, node_id: str, rec) -> str:
    fillers = st.assign.fillers_of(node_id, record=rec)
    if not fillers:
        return "<span class='muted'>Nog niet vervuld.</span>"
    out = []
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id)
            nm = p.name if p else f.id
            out.append(f"<span class='person'><span class='av'>{_e(_initials(nm))}</span>"
                       f"<a href='/person?id={_e(f.id)}'>{_e(nm)}</a></span>")
        else:
            pa = st.personas.get(f.id)
            nm = (pa.name if pa else f.id) + " (AI)"
            out.append(f"<span class='person'><span class='av ai'>AI</span>{_e(nm)}</span>")
    return "<div>" + " &nbsp; ".join(out) + "</div>"


def _members_of_circle(st: _Stores, circle_id: str) -> list:
    seen, ppl = set(), []
    anchors = [circle_id] + [r.id for r in org.roles_of(st.records.all(), circle_id)]
    for aid in anchors:
        rec = st.records.get(aid)
        for f in st.assign.fillers_of(aid, record=rec):
            if f.type == "person" and f.id not in seen:
                seen.add(f.id)
                p = st.people.get(f.id)
                if p:
                    ppl.append(p)
    return sorted(ppl, key=lambda p: p.name)


def _tree_html(st: _Stores, current_id: str) -> str:
    recs = st.records.all()

    def node_li(rec) -> str:
        is_c = org.is_circle(rec)
        cls = "c" if is_c else ""
        here = " here" if rec.id == current_id else ""
        label = f"<a class='{cls}{here}' href='/node?id={_e(rec.id)}'>{_e(_name(rec))}</a>"
        if is_c:
            # Kernrollen (Lead/Rep/Secretary/Facilitator) niet in de navigatie: die zie je via
            # de cirkel -> Rollen. Houdt de boom rustig.
            kids = sorted([k for k in org.children_of(recs, rec.id)
                           if org.is_circle(k) or _name(k).strip().lower() not in _CORE_ROLE_NAMES],
                          key=lambda r: (not org.is_circle(r), _name(r).lower()))
            return f"<li>{label}<ul>{''.join(node_li(k) for k in kids)}</ul></li>"
        return f"<li>{label}</li>"

    body = "".join(node_li(r) for r in org.roots(recs)) or "<li class='muted'>leeg</li>"
    legend = ("<div class='legend'>"
              "<span><span class='dot' style='background:var(--green)'></span>werkt</span>"
              "<span><span class='dot' style='background:var(--yellow)'></span>basis</span>"
              "<span><span class='dot' style='background:var(--border)'></span>nog te bouwen</span></div>")
    return f"<div class='tree'><h3>Organisatie</h3><ul>{body}</ul></div>{legend}"


def _ai_chip(st: _Stores, t) -> str:
    pa = st.personas.get(t.agent)
    nm = pa.name if pa else t.agent
    skill = f" · {_e(t.wat)}" if t.wat else ""
    return f"<span class='chip'>🤖 {_e(nm)}{skill}</span>"


def _suggest_for_acc(st: _Stores, role_id: str, acc_index: int, acc_text: str):
    """Welke (AI, skill) past bij deze accountability en is nog niet gekoppeld. Voedt het cadeautje.
    Matching loopt via ai_match (lexicaal + concept + optioneel gecachet LLM-oordeel)."""
    attached = {(t.agent, t.wat) for t in st.ai.for_acc(role_id, acc_index)}
    return ai_match.suggest(st.personas.all(), acc_text, attached, st.match)


def _acc_row(st: _Stores, rec, i: int, text: str, csrf_token: str) -> str:
    """Eén accountability-regel. Is er AI op gekoppeld, dan tonen we dat SUBTIEL (één 🤖-marker,
    klikbaar om te beheren); het 'wat' staat gebundeld in het AI-overzicht onder de rol. Zo niet
    dubbel. Het 🎁 verschijnt alleen als er een passende, nog niet gekoppelde AI-skill is."""
    tasks = st.ai.for_acc(rec.id, i)
    url = f"/aitask?role={_e(rec.id)}&acc={i}"
    marker = ""
    if tasks:
        if csrf_token:
            marker = (f"<a class='ai-on js-modal' href='{url}' data-href='{url}' "
                      f"title='AI-empowered — beheren'>🤖</a>")
        else:
            marker = "<span class='ai-on' title='AI-empowered'>🤖</span>"
    aff = ""
    if csrf_token and _suggest_for_acc(st, rec.id, i, text):
        aff = (f"<a class='ai-gift js-modal' href='{url}' data-href='{url}' "
               f"title='Er is een AI-skill die deze accountability autonoom kan uitvoeren'>🎁</a>")
    return (f"<div class='accrow'><div class='acc-text'>{_e(text)}</div>"
            f"<div class='acc-ai'>{marker}{aff}</div></div>")


def _role_ai_overview(st: _Stores, rec, csrf_token: str = "") -> str:
    """Overzicht (één keer, niet per accountability herhaald): wat doet elke AI autonoom in DEZE rol.
    Gegroepeerd per agent -> per skill de accountabilities die hij dekt."""
    tasks = st.ai.for_role(rec.id)
    if not tasks:
        return ""
    accs = rec.definition.accountabilities or []
    by_agent: dict[str, dict[str, list]] = {}
    for t in tasks:
        acc_txt = accs[t.acc_index] if 0 <= t.acc_index < len(accs) else "—"
        by_agent.setdefault(t.agent, {}).setdefault(t.wat or "—", []).append(acc_txt)
    blocks = ""
    for agent, skills in by_agent.items():
        pa = st.personas.get(agent)
        nm = pa.name if pa else agent
        rows = ""
        for wat, acclist in skills.items():
            uniq = ", ".join(dict.fromkeys(acclist))
            rows += f"<li><b>{_e(wat)}</b> <span class='muted'>· {_e(uniq)}</span></li>"
        manage = ""
        if csrf_token:
            url = f"/aitask?role={_e(rec.id)}&acc=0"
            manage = f" <a class='flink js-modal' href='{url}' data-href='{url}'>beheren</a>"
        blocks += (f"<div class='ai-ov'><div class='ai-ov-h'>{_avatar(nm, True)}"
                   f"<b>{_e(nm)}</b> <span class='muted'>doet autonoom in deze rol:</span>{manage}</div>"
                   f"<ul class='clean ai-ov-list'>{rows}</ul></div>")
    return f"<div class='c2-sec'><h3>AI in deze rol</h3>{blocks}</div>"


def _overview_html(st: _Stores, rec, csrf_token: str = "") -> str:
    d = rec.definition
    is_c = org.is_circle(rec)
    parts = [f"<div class='c2-sec'><h3>Purpose</h3><div>{_e(d.purpose) or '<span class=muted>—</span>'}</div></div>"]
    if is_c:
        # Strategie geïntegreerd in overview (aparte strategy-tab vervallen). Purpose staat
        # hierboven al → chain overslaan.
        parts.append(_strategy_tab_html(st, rec, with_purpose_chain=False))
    doms = d.domains or []
    parts.append("<div class='c2-sec'><h3>Domains</h3>"
                 + ("<ul class='clean'>" + "".join(f"<li>{_e(x)}</li>" for x in doms) + "</ul>"
                    if doms else "<span class='muted'>Geen domein.</span>") + "</div>")
    accs = d.accountabilities or []
    if not is_c:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3>"
                     + ("".join(_acc_row(st, rec, i, a, csrf_token) for i, a in enumerate(accs))
                        if accs else "<span class='muted'>Geen accountabilities.</span>") + "</div>")
        parts.append(_role_ai_overview(st, rec, csrf_token))
    elif accs:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3><ul class='clean'>"
                     + "".join(f"<li>{_e(x)}</li>" for x in accs) + "</ul></div>")
    if not is_c:
        parts.append(f"<div class='c2-sec'><h3>Role Fillers</h3>{_filler_html(st, rec.id, rec)}</div>")
    return "".join(parts)


def _fillsummary(st: _Stores, rec) -> str:
    fs = st.assign.fillers_of(rec.id, record=rec)
    if not fs:
        return "— niet vervuld"
    names = []
    for f in fs:
        if f.type == "person":
            p = st.people.get(f.id); names.append(p.name if p else f.id)
        else:
            names.append("AI")
    return "· " + ", ".join(names)


_CORE_ROLE_NAMES = {"circle lead", "lead link", "facilitator", "secretary", "secretaris",
                    "rep link", "circle rep", "cross link"}


# Genderneutraal 'persoon + toevoegen'-icoon (silhouet + plus), kleurt mee met currentColor.
_ICON_ADD_PERSON = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='9' cy='8' r='3.2'/>"
    "<path d='M3.5 20c0-3.2 2.5-5.6 5.5-5.6s5.5 2.4 5.5 5.6'/>"
    "<path d='M18.5 8.5v5M16 11h5'/></svg>")

# Reactie toevoegen: neutrale lijn-smiley met plus (zelfde stijl als persoon-toevoegen).


def _fillers_block(st: _Stores, role) -> str:
    """Rechts uitgelijnde rolvervullers; bij 3+ gestapelde avatars + '+ nog N'."""
    fillers = st.assign.fillers_of(role.id, record=role)
    resolved = []
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id)
            resolved.append((p.name if p else f.id, False, f.id))
        else:
            pa = st.personas.get(f.id)
            resolved.append(((pa.name if pa else f.id), True, f.id))
    if not resolved:
        return "<span class='muted' style='font-size:.8rem'>niet vervuld</span>"
    if len(resolved) >= 3:
        avs = "".join(f"<span class='stack-av'>{_avatar(n, ai)}</span>" for n, ai, fid in resolved[:3])
        extra = f"<span class='muted' style='font-size:.82rem'>+ nog {len(resolved)-3}</span>" if len(resolved) > 3 else ""
        return f"<div class='fillers stack'>{avs}{extra}</div>"
    rows = ""
    for n, ai, fid in resolved:
        nm = (f"<a href='/person?id={_e(fid)}'>{_e(n)}</a>" if not ai else f"{_e(n)} (AI)")
        rows += f"<div class='fperson'>{_avatar(n, ai)}<span>{nm}</span></div>"
    return f"<div class='fillers'>{rows}</div>"


def _role_row(st: _Stores, role, csrf_token: str) -> str:
    purpose = role.definition.purpose or ""
    pur = f"<div class='muted rrole-pur'>{_e(purpose)}</div>" if purpose else ""
    assign = ""
    if csrf_token:
        url = f"/rolefillers?role={_e(role.id)}"
        assign = (f"<a class='manage-ico js-modal' href='{url}' data-href='{url}' "
                  f"title='rolvervullers beheren'>{_ICON_ADD_PERSON}</a>")
    return (f"<div class='rrole'>"
            f"<div class='rrole-info'><a href='/node?id={_e(role.id)}'>{_e(_name(role))}</a>{pur}</div>"
            f"<div class='rrole-fill'>{_fillers_block(st, role)}</div>"
            f"<div class='rrole-act'>{assign}</div></div>")


def _roles_html(st: _Stores, rec, csrf_token: str = "") -> str:
    recs = st.records.all()
    subs = sorted(org.subcircles_of(recs, rec.id), key=lambda r: _name(r).lower())
    roles = sorted(org.roles_of(recs, rec.id), key=lambda r: _name(r).lower())
    core = [r for r in roles if _name(r).strip().lower() in _CORE_ROLE_NAMES]
    rest = [r for r in roles if _name(r).strip().lower() not in _CORE_ROLE_NAMES]
    out = []
    if core:
        out.append("<div class='c2-sec'><h3>Kernrollen</h3>"
                   + "".join(_role_row(st, r, csrf_token) for r in core) + "</div>")
    out.append("<div class='c2-sec'><h3>Rollen</h3>"
               + ("".join(_role_row(st, r, csrf_token) for r in rest)
                  if rest else "<span class='muted'>Geen rollen.</span>") + "</div>")
    if subs:
        out.append("<div class='c2-sec'><h3>Subcirkels</h3><ul class='clean'>"
                   + "".join(f"<li><a href='/node?id={_e(s.id)}'>{_e(_name(s))}</a> "
                             f"<span class='chip'>cirkel</span></li>" for s in subs) + "</ul></div>")
    return "".join(out)


def _members_html(st: _Stores, rec, csrf_token: str = "") -> str:
    # Deelnemerbeheer (toevoegen/verwijderen/wijzigen) zit op de admin-pagina (/admin),
    # niet hier. Members toont alleen wie deze cirkel vervullen.
    ppl = _members_of_circle(st, rec.id)
    admin = ("<p class='muted' style='font-size:.8rem;margin-top:.8rem'>"
             "Deelnemers toevoegen of beheren? → <a href='/admin'>Deelnemers (admin)</a></p>"
             if csrf_token else "")
    if not ppl:
        return ("<div class='c2-sec'><h3>Members</h3><span class='muted'>Geen mensen.</span>"
                f"{admin}</div>")
    cells = "".join(
        f"<div class='card'><span class='person'><span class='av'>{_e(_initials(p.name))}</span>"
        f"<a href='/person?id={_e(p.id)}'>{_e(p.name)}</a></span></div>" for p in ppl)
    return f"<div class='c2-sec'><h3>Members ({len(ppl)})</h3>{cells}{admin}</div>"


def render_admin(st: _Stores, csrf_token: str = "", msg: str = "") -> str:
    """Admin-pagina 'Deelnemers': mensen toevoegen, wijzigen (naam/e-mail), wachtwoord
    resetten en verwijderen. Login vereist (route niet publiek). Eén plek voor people-beheer,
    los van de Members-tab van een cirkel."""
    people = st.people.all()
    rw = bool(csrf_token)

    def _status(p):
        if getattr(p, "last_login", 0):
            return f"<span class='chip green'>actief</span> <span class='muted'>· {_e(_age(p.last_login))}</span>"
        if getattr(p, "password_hash", ""):
            return "<span class='chip outline'>uitgenodigd</span>"
        return "<span class='chip muted'>geen toegang</span>"

    rows = ""
    for p in people:
        nrol = len(st.assign.roles_of("person", p.id))
        if rw:
            edit = (
                f"<form method='post' action='/action' class='fieldform' style='gap:.4rem'>"
                f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(p.id)}'>"
                f"<input type='hidden' name='next' value='/admin'>"
                f"<input type='text' name='name' value='{_e(p.name)}' aria-label='naam'>"
                f"<input type='email' name='email' value='{_e(p.email)}' aria-label='e-mail'>"
                f"<button class='btn ok sm' type='submit' name='action' value='person_edit'>opslaan</button>"
                f"</form>")
            pw = (f"<form method='post' action='/action' style='display:inline'>"
                  f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                  f"<input type='hidden' name='pid' value='{_e(p.id)}'>"
                  f"<button class='btn sm' type='submit' name='action' value='person_reset_password'>"
                  f"wachtwoord resetten</button></form>")
            warn = (f" — verwijdert ook {nrol} rol-toewijzing(en)" if nrol else "")
            rm = (f"<form method='post' action='/action' style='display:inline'>"
                  f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                  f"<input type='hidden' name='pid' value='{_e(p.id)}'>"
                  f"<input type='hidden' name='next' value='/admin'>"
                  f"<button class='dellink' type='submit' name='action' value='person_remove' "
                  f"onclick=\"return confirm('{_e(p.name)} verwijderen?{warn}')\">verwijderen</button></form>")
            actions = f"<div class='admin-act'>{pw} {rm}</div>"
        else:
            edit = f"<b>{_e(p.name)}</b> <span class='muted'>· {_e(p.email) or 'geen e-mail'}</span>"
            actions = ""
        rows += (f"<div class='admin-row'><div class='admin-main'>{edit}</div>"
                 f"<div class='admin-meta'>{_status(p)} <span class='muted'>· {nrol} rol(len)</span>"
                 f"{actions}</div></div>")

    add = ""
    if rw:
        add = (
            f"<details class='c2-add' open style='margin-bottom:1rem'>"
            f"<summary style='cursor:pointer;font-weight:600'>+ Deelnemer toevoegen</summary>"
            f"<form method='post' action='/action' style='margin-top:.75rem;display:grid;gap:.5rem;max-width:380px'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='action' value='person_add'>"
            f"<input type='hidden' name='next' value='/admin'>"
            f"<input type='text' name='voornaam' placeholder='Voornaam' required>"
            f"<input type='text' name='achternaam' placeholder='Achternaam' required>"
            f"<input type='email' name='email' placeholder='E-mailadres' required>"
            f"<button class='btn ok' type='submit'>Toevoegen</button>"
            f"</form></details>")

    css = ("<style>"
           ".admin-row{display:flex;justify-content:space-between;align-items:center;gap:1rem;"
           "flex-wrap:wrap;padding:.55rem 0;border-bottom:1px solid var(--border)}"
           ".admin-main{flex:1 1 340px;min-width:0}"
           ".admin-main .fieldform input[name=name]{flex:0 1 11rem}"
           ".admin-main .fieldform input[name=email]{flex:1 1 13rem}"
           ".admin-meta{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;font-size:.85rem}"
           ".admin-act{display:inline-flex;gap:.4rem;margin-left:.4rem}"
           "</style>")
    main = (f"<div class='c2-main'><div class='c2-bar'><a href='/'>← home</a></div>"
            f"<h1>Deelnemers <span class='chip'>admin</span></h1>{_banner(msg)}"
            f"<p class='muted'>Mensen toevoegen, wijzigen, wachtwoord resetten of verwijderen. "
            f"Deze pagina vereist login.</p>{add}"
            f"<div class='c2-sec'><h3>Deelnemers ({len(people)})</h3>{rows or '<span class=muted>Nog niemand.</span>'}</div></div>")
    inner = (f"<style>{_EXTRA_CSS}</style>{css}"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             f"<a href='/'>home</a> · <a href='/admin'>deelnemers</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Deelnemers — admin", inner)


def _att_html(st: _Stores, rec, kind: str, leeg: str) -> str:
    items = st.att.list(rec.id, kind)
    if not items:
        return (f"<p class='muted'>{_e(leeg)}</p>"
                "<p class='muted' style='font-size:.8rem'>De opslag werkt al; het invoeren/"
                "tonen (en de meeting-koppeling) komt nog.</p>")
    out = "<ul class='clean'>"
    for a in items:
        meta = ""
        if a.meta:
            meta = " <span class='pill'>" + _e(", ".join(f"{k}: {v}" for k, v in a.meta.items())) + "</span>"
        out += f"<li><b>{_e(a.title) or '—'}</b>{meta}<br><span class='muted'>{_e(a.body)}</span></li>"
    return out + "</ul>"

def render_node(st: _Stores, node_id: str, tab: str, csrf_token: str = "", msg: str = "",
                group: str = "", clf: str = "due", mw: str = "maand", username: str | None = None) -> str:
    rec = st.records.get(node_id)
    if rec is None:
        return _page("Niet gevonden", "<p>Node niet gevonden.</p><p><a href='/'>← home</a></p>")
    is_c = org.is_circle(rec)
    tabs = _CIRCLE_TABS if is_c else _ROLE_TABS
    if tab not in tabs:
        tab = "overview"
    recs = st.records.all()
    crumb = " › ".join(
        f"<a href='/node?id={_e(i)}'>{_e(_name(st.records.get(i)))}</a>"
        for i in org.breadcrumb(recs, node_id))
    chip = "<span class='chip'>cirkel</span>" if is_c else "<span class='chip'>rol</span>"

    if tab == "overview":
        content = _overview_html(st, rec, csrf_token)
    elif tab == "strategy":
        content = _strategy_tab_html(st, rec)
    elif tab == "roles":
        content = _roles_html(st, rec, csrf_token)
    elif tab == "members":
        content = _members_html(st, rec, csrf_token)
    elif tab == "notes":
        if rec.id == WEBSITE_DEVELOPER_ROLE:
            # De Notes-tab van de Website Developer is de Backlog Builder.
            content = render_backlog_tab(st, rec, csrf_token, username)
        else:
            content = ("<div class='c2-sec'><h3>Notes</h3>"
                       + _att_html(st, rec, "note", "Nog geen notities op deze rol/cirkel.")
                       + "<p class='muted' style='font-size:.8rem'>Hierin vouwen we Nooch's "
                       "concurrenten-notities.</p></div>")
    elif tab == "metrics":
        content = _metrics_tab_html(st, rec, csrf_token, win=mw)
    elif tab == "checklists":
        content = _checklists_tab_html(st, rec, csrf_token, flt=clf)
    elif tab == "projects":
        content = _projects_tab_html(st, rec, csrf_token, group=group, username=username)
    elif tab == "policies":
        content = _todo("Policies per cirkel (nu alleen harde policies op de anchor-cirkel).")
    else:  # history
        content = _todo("Wijzigingsgeschiedenis per rol/cirkel (records dragen al versies; de "
                        "weergave moet nog).")

    # Meetings zijn een CIRKEL-functie (een rol heeft geen governance/tactical meeting).
    if is_c and csrf_token:
        rov_url = f"/roloverleg2?circle={_e(node_id)}"
        from nooch_village.views.roloverleg import _rov_items
        open_cls = "btn ok" if _rov_items(st, node_id) else "btn"   # groen = lopend roloverleg
        wo_url = f"/werkoverleg?circle={_e(node_id)}"
        wo_cls = "btn ok" if st.werk.is_open(node_id) else "btn"    # groen = lopend werkoverleg
        meet = (f"<div class='c2-meet'>"
                f"<a class='{open_cls} js-modal' href='{rov_url}' data-href='{rov_url}'>Governance meeting</a>"
                f"<a class='{wo_cls} js-modal' href='{wo_url}' data-href='{wo_url}'>Tactical meeting</a></div>")
    else:
        meet = ""
    main = (f"<div class='c2-main'><div class='c2-bar'>{crumb}</div>"
            f"<h1>{_e(_name(rec))} {chip}</h1>{_banner(msg)}{meet}"
            f"{_tabbar(node_id, tabs, tab)}{content}</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, node_id)}</div>"
    modal = _modal_html(json.dumps(_mentionables(st)[0])) if csrf_token else ""
    inner = (f"<style>{_EXTRA_CSS}</style>"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · "
             "<a href='/'>home</a> · <a href='/catalog'>catalogus</a> · <a href='/admin'>deelnemers</a></div>"
             f"<div class='c2-wrap'>{main}{rail}</div>{modal}")
    return _page(_name(rec), inner)


def render_person(st: _Stores, pid: str) -> str:
    p = st.people.get(pid)
    if p is None:
        return _page("Niet gevonden", "<p>Persoon niet gevonden.</p><p><a href='/'>← home</a></p>")
    role_ids = st.assign.roles_of("person", pid)
    rows = ""
    for rid in sorted(role_ids):
        rec = st.records.get(rid)
        if rec is None:
            continue
        crumb = " › ".join(_e(_name(st.records.get(i)))
                           for i in org.breadcrumb(st.records.all(), rid)[:-1])
        rows += (f"<li><a href='/node?id={_e(rid)}'>{_e(_name(rec))}</a> "
                 f"<span class='muted'>{('· ' + crumb) if crumb else ''}</span></li>")
    # Notificaties: @-mentions van mij of van een rol die ik vervul.
    targets = {("person", pid)} | {("role", rid) for rid in role_ids}
    notes = st.notif.for_targets(targets)
    nrows = ""
    for n in notes[:25]:
        proj = st.projects.get(n.get("project_id"))
        ptitle = _scope_text(proj) if proj else "project"
        href = f"/project?pid={_e(n.get('project_id',''))}&back={urllib.parse.quote('/person?id=' + pid, safe='')}"
        dot = "" if n.get("read") else "<span class='nt-dot'></span>"
        nrows += (f"<li class='nt-item'>{dot}<a class='js-modal' href='{href}' data-href='{href}'>"
                  f"{_e(ptitle)}</a> <span class='muted'>· {_e((n.get('snippet') or '')[:80])}</span> "
                  f"<span class='muted' style='font-size:.72rem'>{_e(_age(n.get('at')))}</span></li>")
    unread = sum(1 for n in notes if not n.get("read"))
    notif_html = (f"<div class='c2-sec'><h3>🔔 Notificaties ({unread} nieuw)</h3>"
                  + (f"<ul class='clean nt-list'>{nrows}</ul>" if nrows
                     else "<span class='muted'>Geen notificaties.</span>") + "</div>")
    main = (f"<div class='c2-main'><h1><span class='av' style='width:28px;height:28px'>"
            f"{_e(_initials(p.name))}</span> {_e(p.name)}</h1>"
            f"<div class='muted'>{_e(p.email) or 'geen e-mail'}</div>"
            f"{notif_html}"
            f"<div class='c2-sec'><h3>Mijn rollen ({len(role_ids)})</h3>"
            + (f"<ul class='clean'>{rows}</ul>" if rows else "<span class='muted'>Geen rollen.</span>")
            + "</div>" + _person_projects_html(st, pid) + "</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, '')}</div>"
    inner = (f"<style>{_EXTRA_CSS}</style>"
             f"<div class='bar'>cockpit 2 · GlassFrog (PoC) · build {_BUILD} · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}{rail}</div>")
    return _page(p.name, inner)


def render_patterns(csrf_token: str = "") -> str:
    """Levende styleguide: elk atoom/molecuul één keer. Bron van waarheid; geen losse varianten."""
    def sec(title, body):
        return f"<div class='c2-sec'><h3>{_e(title)}</h3><div style='display:flex;gap:.5rem;flex-wrap:wrap;align-items:center'>{body}</div></div>"
    buttons = ("<button class='btn ok'>Primair</button>"
               "<button class='btn'>Neutraal</button>"
               "<button class='btn no'>Gevaar</button>"
               "<button class='btn ok sm'>Primair sm</button>"
               "<button class='btn sm'>Neutraal sm</button>"
               "<button class='btn ghost sm'>Ghost sm</button>"
               "<a class='dellink' href='#'>verwijderen</a>")
    chips = ("<span class='chip green'>green</span><span class='chip muted'>muted</span>"
             "<span class='chip outline'>outline</span><span class='chip coral'>coral</span>"
             "<span class='chip coral-solid'>Overdue</span><span class='chip'>tint (default)</span>"
             "<span class='badge ro'>read</span><span class='badge rw'>edit</span>")
    cards = (f"<button class='acard'>{_IC_CLOCK}<span>Datum</span></button>"
             f"<button class='acard'>{_IC_CHECK}<span>Checklist</span></button>"
             f"<button class='acard acard-off' disabled>{_IC_TARGET}<span>Goals</span></button>")
    att = f"<div class='attcard'><span class='att-ic'>{_IC_LINK}</span><a class='att-name' href='#'>voorbeeld bijlage</a></div>"
    due = (f"<span class='chip outline'>{_IC_CLOCK}25 jun 2026</span>"
           f"<span class='chip coral'>{_IC_CLOCK}1 jan 2020</span><span class='chip coral-solid'>Overdue</span>")
    av = _avatar("Stefan Wobben", False) + _avatar("Codie", True)
    icons = (f"<span class='manage-ico' title='persoon toevoegen'>{_ICON_ADD_PERSON}</span>"
             f"<span class='manage-ico' title='reactie toevoegen'>{_ICON_ADD_EMOJI}</span>")
    body = (sec("Knoppen — atoom: .btn [.ok|.no] [.sm] [.ghost] + .dellink", buttons)
            + sec("Lijn-iconen (neutraal, currentColor)", icons)
            + sec("Status & chips & badges", chips)
            + sec("Action-cards (molecule)", cards)
            + sec("Bijlage-card", att)
            + sec("Deadline-chip", due)
            + sec("Avatar", av))
    main = (f"<div class='c2-main'><h1>Patterns</h1>"
            f"<p class='muted'>Levende referentie. Gebruik deze atomen en moleculen; verzin geen varianten.</p>{body}</div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · patterns · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page("Patterns", inner)




def render_rolefillers(st: _Stores, role_id: str, csrf_token: str = "", fragment: bool = False) -> str:
    rec = st.records.get(role_id)
    if rec is None:
        return ("<p class='muted'>Onbekende rol.</p>" if fragment
                else _page("Niet gevonden", "<p>Onbekend.</p>"))
    back = f"/node?id={(rec.parent or rec.id)}&tab=roles"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='role' value='{_e(role_id)}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")

    fillers = st.assign.fillers_of(role_id, record=rec)
    rows = ""
    for f in fillers:
        if f.type == "person":
            p = st.people.get(f.id); label = (p.name if p else f.id); ai = False
            name = f"<a href='/person?id={_e(f.id)}'>{_e(label)}</a>"
        else:
            pa = st.personas.get(f.id); label = (pa.name if pa else f.id); ai = True
            name = f"{_e(label)} (AI)"
        prev = f" <span class='muted' style='font-size:.8rem'>· {_e(f.focus)}</span>" if f.focus else ""
        rows += (
            f"<div class='frow'>"
            f"<details class='ffocus' style='flex:1'>"
            f"<summary>{_avatar(label, ai)} {name}{prev}</summary>"
            f"<form method='post' action='/action' style='margin:.3rem 0 .2rem 30px'>{hid()}"
            f"<input type='hidden' name='filler' value='{f.type}:{_e(f.id)}'>"
            f"<input name='focus' value='{_e(f.focus)}' placeholder='Focus (optioneel)' "
            f"style='padding:.3rem .4rem;border:1px solid var(--border);border-radius:var(--radius)'> "
            f"<button class='btn' type='submit' name='action' value='role_focus'>Focus opslaan</button>"
            f"</form></details>"
            f"<form method='post' action='/action' style='display:inline'>{hid()}"
            f"<input type='hidden' name='filler' value='{f.type}:{_e(f.id)}'>"
            f"<button class='dellink' type='submit' name='action' value='role_unassign'>verwijderen</button>"
            f"</form></div>")
    if not rows:
        rows = "<p class='muted'>Nog niemand toegewezen.</p>"
    # Alleen mensen vervullen een rol; AI koppel je per accountability (niet hier).
    opts = "<option value=''>— kies persoon —</option>"
    opts += "".join(f"<option value='person:{_e(p.id)}'>{_e(p.name)}</option>" for p in st.people.all())
    add = (f"<div class='pf' style='margin-top:.6rem'><form method='post' action='/action'>{hid()}"
           f"<label>Toevoegen aan {_e(_name(rec))}</label>"
           f"<select name='filler'>{opts}</select>"
           f"<button class='btn ok' type='submit' name='action' value='role_assign' "
           f"style='margin-top:.4rem'>Toewijzen</button></form></div>")
    frag = (f"<h2 style='margin-top:0'>Rolvervullers beheren — {_e(_name(rec))}</h2>"
            f"<div>{rows}</div>{add}")
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{frag}</div>")
    return _page("Rolvervullers", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")


def render_aitask(st: _Stores, role_id: str, acc_index: int, csrf_token: str = "",
                  fragment: bool = False) -> str:
    rec = st.records.get(role_id)
    accs = rec.definition.accountabilities if rec else []
    acc_text = accs[acc_index] if (rec and 0 <= acc_index < len(accs)) else ""
    back = f"/node?id={role_id}&tab=overview"

    def hid():
        return (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='role' value='{_e(role_id)}'>"
                f"<input type='hidden' name='acc' value='{acc_index}'>"
                f"<input type='hidden' name='next' value='{_e(back)}'>")

    def pickform(agent: str, skill: str, label: str, cls: str) -> str:
        return (f"<form method='post' action='/action' style='display:inline'>{hid()}"
                f"<input type='hidden' name='pick' value='{_e(agent)}::{_e(skill)}'>"
                f"<button class='{cls}' type='submit' name='action' value='aitask_add'>{label}</button></form>")

    # 1) Voorgesteld: (AI, skill) die lexicaal bij deze accountability past (het cadeautje).
    sugg = _suggest_for_acc(st, role_id, acc_index, acc_text)
    sugg_html = ""
    if sugg:
        items = "".join(f"<div class='frow'><span style='flex:1'>🤖 {_e(p.name)} · {_e(sk)}</span>"
                        f"{pickform(p.id, sk, 'koppel', 'btn ok')}</div>" for p, sk in sugg)
        sugg_html = (f"<div class='sugg'><div class='sugg-h'>🎁 Voorgesteld</div>{items}</div>")

    # 2) Al gekoppeld: verwijderbaar.
    rows = ""
    for t in st.ai.for_acc(role_id, acc_index):
        rows += (f"<div class='frow'><span style='flex:1'>{_ai_chip(st, t)}</span>"
                 f"<form method='post' action='/action' style='display:inline'>"
                 f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='tid' value='{_e(t.id)}'>"
                 f"<input type='hidden' name='next' value='{_e(back)}'>"
                 f"<button class='dellink' type='submit' name='action' value='aitask_remove'>verwijderen</button>"
                 f"</form></div>")

    # 3) Selecteren uit een rugzakje (geen vrije tekst): combinaties AI · skill, niet al gekoppeld.
    personas = st.personas.all()
    attached = {(t.agent, t.wat) for t in st.ai.for_acc(role_id, acc_index)}
    combos = [(p, sk) for p in personas for sk in (p.skills or []) if (p.id, sk) not in attached]
    if combos:
        opts = "".join(f"<option value='{_e(p.id)}::{_e(sk)}'>🤖 {_e(p.name)} · {_e(sk)}</option>"
                       for p, sk in combos)
        select = (f"<div class='pf'><form method='post' action='/action'>{hid()}"
                  f"<label>Kies een skill uit het rugzakje van een AI</label>"
                  f"<select name='pick'>{opts}</select>"
                  f"<button class='btn ok' type='submit' name='action' value='aitask_add' "
                  f"style='margin-top:.4rem'>Koppel</button></form></div>")
    elif personas:
        select = "<p class='muted'>Alle skills van de AI's zijn hier al gekoppeld, of de rugzakjes zijn leeg.</p>"
    else:
        select = ("<p class='muted'>Er zijn nog geen AI-inwoners. Maak er eerst een aan, "
                  "dan kun je een skill koppelen.</p>")

    # 4) Rugzak uitbreiden (set-up): een nieuwe skill aan een AI toevoegen.
    bag = ""
    if personas:
        popts = "".join(f"<option value='{_e(p.id)}'>🤖 {_e(p.name)}</option>" for p in personas)
        bag = (f"<details class='bagadd'><summary>Rugzak van een AI uitbreiden</summary>"
               f"<form method='post' action='/action'>"
               f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
               f"<input type='hidden' name='next' value='{_e(back + '&_aitask=' + str(acc_index))}'>"
               f"<label>AI-inwoner</label><select name='agent'>{popts}</select>"
               f"<label>Nieuwe skill</label><input name='skill' placeholder='bijv. schrijft de code'>"
               f"<button class='btn' type='submit' name='action' value='persona_skill_add' "
               f"style='margin-top:.4rem'>Aan rugzak toevoegen</button></form></details>")

    frag = (f"<h2 style='margin-top:0'>AI op deze accountability</h2>"
            f"<p class='muted'>Accountability: {_e(acc_text) or '—'}</p>"
            f"<p style='font-size:.82rem;color:var(--gray)'>De mens blijft verantwoordelijk; de AI "
            f"voert <b>zelfstandig</b> een skill uit z'n rugzakje uit. Je typt niets, je "
            f"<b>selecteert</b> een skill.</p>{sugg_html}{rows}{select}{bag}")
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{frag}</div>")
    return _page("AI op accountability", f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")

