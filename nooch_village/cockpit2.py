"""Cockpit 2 — de GlassFrog-vormige weergave (PoC).

Read-only "plaatje": rendert de organisatie als GlassFrog (cirkel-/rolpagina's met tabs +
org-verkenner), bovenop het nieuwe datamodel (records, people, assignments, attachments). Wat we
hebben tonen we echt; wat we nog niet hebben grijzen we uit ("nog te bouwen"), zodat in één blik
zichtbaar is welke brokken resten.

Design: hergebruikt het bestaande design system van cockpit 1 (tokens + _page).
Aparte server (poort 8766) zodat cockpit 1 ongemoeid blijft. Bootstrapt bij een lege dataset de
echte Nooch-structuur (glassfrog_import.nooch_poc_org) in data/poc/, zonder de live data aan te raken.

    python -m nooch_village.cockpit2            # http://127.0.0.1:8766
"""
from __future__ import annotations
import json
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nooch_village.cockpit import _e, _page, _banner     # zelfde design system
from nooch_village.governance import Records
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore
from nooch_village.personas import PersonaStore
from nooch_village.projects import ProjectLedger
from nooch_village.ai_tasks import AITaskStore
from nooch_village import ai_match
from nooch_village import org
from nooch_village.glassfrog_import import import_org, nooch_poc_org

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# Alleen layout-specifieke klassen; kleuren/typografie komen uit de design-tokens van cockpit 1.
_EXTRA_CSS = """
.c2-bar{color:var(--gray);font-size:.85rem;margin:.2rem 0 .5rem}
.c2-wrap{display:flex;gap:1.2rem;align-items:flex-start;margin-top:.6rem}
.c2-main{flex:1 1 auto;min-width:0}
.c2-rail{flex:0 0 280px;max-width:280px}
.c2-meet{display:flex;gap:.4rem;margin:.4rem 0}
.c2-tabs{display:flex;flex-wrap:wrap;gap:.1rem;border-bottom:1px solid var(--border);margin:.7rem 0 1rem}
.c2-tab{padding:.4rem .7rem;font-size:.85rem;border-bottom:2px solid transparent;color:var(--gray);text-decoration:none}
.c2-tab.on{border-bottom-color:var(--green-dark);color:var(--green-dark);font-weight:700}
.c2-tab .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-left:.35rem;vertical-align:middle}
.dot.live{background:var(--green)}.dot.basic{background:var(--yellow)}.dot.grey{background:var(--border)}
.c2-sec{margin:1.1rem 0}
.c2-sec h3{font-family:var(--font-display);font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;color:var(--green-dark);margin:0 0 .3rem}
ul.clean{list-style:none;padding:0;margin:0}
ul.clean li{padding:.22rem 0;border-bottom:1px solid var(--border)}
ul.clean li:last-child{border-bottom:none}
.todo{background:var(--cream-2);border:1px dashed var(--border);border-radius:var(--radius);padding:1rem;color:var(--muted)}
.todo b{color:var(--gray)}
.person{display:inline-flex;align-items:center;gap:.35rem;padding:.15rem 0}
.av{width:22px;height:22px;border-radius:50%;background:var(--green);color:#fff;font-size:.62rem;display:inline-flex;align-items:center;justify-content:center;font-weight:700;flex:0 0 auto}
.av.ai{background:#7A5BD1}
.tree{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.7rem .85rem;box-shadow:var(--shadow)}
.tree h3{font-family:var(--font-display);font-size:.72rem;text-transform:uppercase;color:var(--green-dark);margin:.1rem 0 .4rem}
.tree ul{list-style:none;margin:0;padding-left:.8rem}.tree>ul{padding-left:0}
.tree li{padding:.12rem 0;font-size:.86rem}
.tree .c{font-weight:700}
.tree .here{background:var(--green-tint);border-radius:5px;padding:0 .3rem}
.legend{font-size:.74rem;color:var(--muted);margin-top:.6rem;display:flex;gap:.9rem;flex-wrap:wrap}
.legend .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:.25rem}
.pill{display:inline-block;font-size:.72rem;padding:.05rem .45rem;border-radius:var(--radius-pill);background:var(--cream-2);color:var(--gray);margin-left:.3rem}
.card{border:1px solid var(--border);border-radius:var(--radius);padding:.5rem .7rem;margin:.3rem 0;background:var(--surface)}
.pboard{display:flex;gap:.6rem;align-items:flex-start;overflow-x:auto}
.pcol{flex:1 1 0;min-width:160px;background:var(--cream-2);border:1px solid var(--border);border-radius:var(--radius);padding:.4rem}
.pcol-scroll{max-height:540px;overflow-y:auto}
.swim{margin:.6rem 0}
.swim-h{font-family:var(--font-display);font-weight:700;font-size:.85rem;color:var(--green-dark);margin:.2rem 0 .25rem}
.pcol-h{font-family:var(--font-display);font-weight:700;font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;color:var(--green-dark);margin-bottom:.3rem}
.pcol .card{padding:.4rem .5rem;margin:.25rem 0;font-size:.85rem}
.dellink{background:none;border:none;color:var(--coral);font:inherit;font-size:.78rem;text-decoration:underline;cursor:pointer;padding:0;margin-left:.3rem}
.card.arch{opacity:.6}
.pcard{cursor:pointer;position:relative;transition:box-shadow .1s,border-color .1s}
.pcard:hover{border-color:var(--green);box-shadow:0 0 0 2px var(--green-tint)}
.pcard:active{cursor:grabbing}
.ptitle{font-weight:600}
.clabel{height:7px;border-radius:4px;margin:-.1rem 0 .35rem}
.pbadge{display:flex;align-items:center;gap:.35rem;margin-top:.35rem;font-size:.7rem;color:var(--muted)}
.pbar{height:6px;background:var(--border);border-radius:999px;overflow:hidden;width:70px}
.pbar>div{height:100%;background:var(--green)}
.pcol.over{outline:2px dashed var(--green);outline-offset:-2px;background:var(--green-tint)}
/* override de basis-details-stijl (wit kaartje) → ghost in de kolomkleur, Trello-stijl */
.qadd{margin-top:.15rem;background:none;border:none;box-shadow:none;padding:0}
.qadd>summary{list-style:none;cursor:pointer;color:var(--gray);font-family:var(--font-body);font-weight:500;font-size:.84rem;padding:.4rem .55rem;border-radius:var(--radius)}
.qadd>summary:hover{background:rgba(27,27,27,.07);color:var(--ink)}
.qadd>summary::-webkit-details-marker{display:none}
.qadd[open]{padding:0}
.qadd[open]>summary{display:none}
.qadd-form{display:flex;flex-direction:column;gap:.4rem;margin-top:.1rem}
.qadd-form textarea{width:100%;box-sizing:border-box;padding:.45rem .55rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);box-shadow:var(--shadow);font:inherit;font-size:.85rem;resize:vertical}
.qadd-row{display:flex;align-items:center;gap:.4rem}
.qadd-x{background:none;border:none;font-size:1rem;color:var(--gray);cursor:pointer;padding:.1rem .3rem}
/* '+ project' krijgt dezelfde subtiele knop-vormgeving als de meeting-knoppen */
.addlink{display:inline-block;font-family:var(--font-body);font-weight:600;font-size:12px;
  border:1px solid rgba(27,27,27,.14);border-radius:var(--radius-pill);background:transparent;
  color:var(--gray);padding:.3rem .85rem;text-decoration:none;cursor:pointer;vertical-align:middle}
.addlink:hover{background:rgba(27,27,27,.05);color:var(--ink);text-decoration:none}
/* rollen-tab: rij met purpose + rechts uitgelijnde vervullers + toewijs-icoon */
.rrole{display:flex;align-items:flex-start;gap:1rem;padding:.6rem 0;border-bottom:1px solid var(--border)}
.rrole-info{flex:1 1 auto;min-width:0}
.rrole-pur{font-size:.84rem;margin-top:.1rem}
.rrole-fill{flex:0 0 220px;min-width:0}          /* vaste rechterkolom; inhoud links uitgelijnd */
.rrole-act{flex:0 0 auto}
.fillers{display:flex;flex-direction:column;gap:.15rem;align-items:flex-start}
.fperson{display:inline-flex;align-items:center;gap:.35rem;font-size:.86rem;color:var(--gray)}
.fillers.stack{flex-direction:row;align-items:center;gap:.3rem}
.stack-av{margin-left:-8px}.stack-av:first-child{margin-left:0}
.stack-av .av{border:2px solid var(--surface)}
.manage-ico{display:inline-flex;align-items:center;justify-content:center;color:var(--subtle);
  padding:.25rem;border-radius:var(--radius)}
.manage-ico:hover{color:var(--green-dark);background:rgba(27,27,27,.06)}
.accrow{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;padding:.35rem 0;border-bottom:1px solid var(--border)}
.acc-text{flex:1 1 auto;min-width:0}
.acc-ai{flex:0 0 auto;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;justify-content:flex-end}
.aichip{display:inline-block;background:#EFEAF9;color:#5b3fa6;border-radius:var(--radius-pill);padding:.05rem .5rem;font-size:.74rem;font-weight:600}
.ai-gift{font-size:1rem;text-decoration:none;cursor:pointer;line-height:1}
.chiplink{text-decoration:none}
.swrow{display:flex;gap:.3rem;flex-wrap:wrap;margin:.2rem 0 .8rem}
.sw{background:var(--cream-2);color:var(--gray);border:1px solid var(--border);border-radius:var(--radius-pill);padding:.2rem .7rem;font-size:.76rem;font-weight:600;cursor:pointer}
.sw:hover{border-color:var(--green)}
.sw.on{background:var(--green);color:#fff;border-color:var(--green)}
.pmeta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem .9rem;margin:.4rem 0 .2rem}
.pmeta>div{display:flex;flex-direction:column;gap:.1rem;min-width:0}
.pmeta .k{font-size:.66rem;text-transform:uppercase;letter-spacing:.04em;color:var(--subtle);font-weight:700}
.dot{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;margin-right:.35rem;vertical-align:middle}
.acc-sub{padding:.15rem 0 .4rem 1.4rem;border-bottom:1px solid var(--border)}
.sugg{background:#F4F1FB;border:1px solid #E0D7F5;border-radius:var(--radius);padding:.5rem .7rem;margin:.5rem 0}
.sugg-h{font-weight:700;color:#5b3fa6;font-size:.82rem;margin-bottom:.3rem}
.koppel{background:#5b3fa6;color:#fff;border:none;border-radius:var(--radius-pill);padding:.15rem .7rem;font-size:.76rem;font-weight:600;cursor:pointer}
.bagadd{background:none;border:none;box-shadow:none;padding:0;margin-top:.8rem}
.bagadd>summary{cursor:pointer;color:var(--subtle);font-size:.82rem;list-style:none}
.bagadd>summary:hover{color:#5b3fa6}
.frow{display:flex;align-items:flex-start;gap:.5rem;padding:.4rem 0;border-bottom:1px solid var(--border)}
.ffocus{background:none;border:none;box-shadow:none;padding:0;margin:0}
.ffocus>summary{list-style:none;cursor:pointer}
.ffocus>summary::-webkit-details-marker{display:none}
.ovl{position:fixed;inset:0;background:rgba(27,27,27,.45);z-index:50;display:flex;align-items:flex-start;justify-content:center}
.ovl-box{background:var(--surface);max-width:720px;width:92%;margin:4vh auto;border-radius:12px;padding:1.3rem 1.5rem;max-height:88vh;overflow:auto;position:relative;box-shadow:0 12px 48px rgba(27,27,27,.35)}
.ovl-x{position:absolute;top:.5rem;right:.7rem;border:none;background:none;font-size:1.2rem;cursor:pointer;color:var(--gray)}
.vswitch{display:inline-flex;gap:.2rem;align-items:center}
.vbtn{font-size:12px;font-weight:600;padding:.3rem .85rem;border:1px solid var(--border);border-radius:var(--radius-pill);color:var(--gray);text-decoration:none}
.vbtn.on{background:var(--green);color:#fff;border-color:var(--green)}
.ck-prog{display:flex;align-items:center;gap:.5rem;margin:.3rem 0 .5rem}
.ck-list{}.ck-item{display:flex;align-items:center;gap:.4rem;padding:.2rem 0;border:none}
.ck-box{width:18px;height:18px;border:1px solid var(--border);border-radius:4px;background:#fff;cursor:pointer;font-size:.7rem;line-height:1;color:#fff;flex:0 0 auto}
.ck-box.on{background:var(--green);border-color:var(--green)}
.ck-done{text-decoration:line-through;color:var(--muted)}
.btn.grey{color:var(--muted);border-style:dashed;cursor:not-allowed}
@media(max-width:760px){.c2-wrap{flex-direction:column}.c2-rail{max-width:none;flex-basis:auto}}
"""

# Welke tabs "leven" (echt werken) en welke nog grijs zijn. Status: live | basic | grey.
_TAB_STATUS = {
    "overview": "live", "roles": "live", "members": "live", "notes": "basic",
    "metrics": "basic", "checklists": "basic", "projects": "live",
    "policies": "grey", "history": "grey",
}
_TAB_LABEL = {
    "overview": "Overview", "roles": "Roles", "members": "Members", "policies": "Policies",
    "notes": "Notes", "projects": "Projects", "checklists": "Checklists",
    "metrics": "Metrics", "history": "History",
}
_CIRCLE_TABS = ["overview", "roles", "members", "policies", "notes", "projects",
                "checklists", "metrics", "history"]
_ROLE_TABS = ["overview", "policies", "notes", "projects", "checklists", "metrics", "history"]


def _default_data_dir() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "data", "poc")


class _Stores:
    def __init__(self, dd: str):
        os.makedirs(dd, exist_ok=True)
        self.dd = dd
        self.records = Records(os.path.join(dd, "governance_records.json"))
        self.people = PeopleStore(os.path.join(dd, "people.json"))
        self.assign = Assignments(os.path.join(dd, "assignments.json"))
        self.att = AttachmentStore(os.path.join(dd, "attachments.json"))
        self.personas = PersonaStore(os.path.join(dd, "personas.json"))
        self.projects = ProjectLedger(os.path.join(dd, "projects.json"))
        self.ai = AITaskStore(os.path.join(dd, "ai_tasks.json"))
        self.match = ai_match.MatchCache(os.path.join(dd, "ai_match_cache.json"))


def _bootstrap(dd: str) -> None:
    """Lege PoC-dataset? Laad dan de echte Nooch-structuur in (eenmalig)."""
    st = _Stores(dd)
    if not st.records.all():
        import_org(nooch_poc_org(), st.records, st.people, st.assign)


def _name(rec) -> str:
    return getattr(rec.definition, "name", "") or rec.id


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper() or "?"


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
            kids = sorted(org.children_of(recs, rec.id),
                          key=lambda r: (not org.is_circle(r), _name(r).lower()))
            return f"<li>{label}<ul>{''.join(node_li(k) for k in kids)}</ul></li>"
        return f"<li>{label}</li>"

    body = "".join(node_li(r) for r in org.roots(recs)) or "<li class='muted'>leeg</li>"
    legend = ("<div class='legend'>"
              "<span><span class='dot' style='background:var(--green)'></span>werkt</span>"
              "<span><span class='dot' style='background:var(--yellow)'></span>basis</span>"
              "<span><span class='dot' style='background:var(--border)'></span>nog te bouwen</span></div>")
    return f"<div class='tree'><h3>Organisatie</h3><ul>{body}</ul></div>{legend}"


def _tabbar(node_id: str, tabs: list, cur: str) -> str:
    out = []
    for t in tabs:
        status = _TAB_STATUS.get(t, "grey")
        on = " on" if t == cur else ""
        out.append(f"<a class='c2-tab{on}' href='/node?id={_e(node_id)}&tab={t}'>"
                   f"{_e(_TAB_LABEL[t])}<span class='dot {status}'></span></a>")
    return "<div class='c2-tabs'>" + "".join(out) + "</div>"


def _todo(wat: str) -> str:
    return f"<div class='todo'><b>Nog te bouwen.</b> {_e(wat)}</div>"


def _ai_chip(st: _Stores, t) -> str:
    pa = st.personas.get(t.agent)
    nm = pa.name if pa else t.agent
    skill = f" · {_e(t.wat)}" if t.wat else ""
    return f"<span class='aichip'>🤖 {_e(nm)}{skill}</span>"


def _suggest_for_acc(st: _Stores, role_id: str, acc_index: int, acc_text: str):
    """Welke (AI, skill) past bij deze accountability en is nog niet gekoppeld. Voedt het cadeautje.
    Matching loopt via ai_match (lexicaal + concept + optioneel gecachet LLM-oordeel)."""
    attached = {(t.agent, t.wat) for t in st.ai.for_acc(role_id, acc_index)}
    return ai_match.suggest(st.personas.all(), acc_text, attached, st.match)


def _acc_row(st: _Stores, rec, i: int, text: str, csrf_token: str) -> str:
    tasks = st.ai.for_acc(rec.id, i)
    url = f"/aitask?role={_e(rec.id)}&acc={i}"
    # Gekoppelde AI: geneste chip, klikbaar om te beheren (toevoegen/verwijderen).
    if csrf_token:
        sub = "".join(f"<div class='acc-sub'>↳ <a class='chiplink js-modal' href='{url}' "
                      f"data-href='{url}'>{_ai_chip(st, t)}</a></div>" for t in tasks)
    else:
        sub = "".join(f"<div class='acc-sub'>↳ {_ai_chip(st, t)}</div>" for t in tasks)
    # Discovery: enkel het cadeautje, en alleen als er een passende, nog niet gekoppelde AI-skill is.
    aff = ""
    if csrf_token and _suggest_for_acc(st, rec.id, i, text):
        aff = (f"<a class='ai-gift js-modal' href='{url}' data-href='{url}' "
               f"title='Er is een AI-skill die deze accountability autonoom kan uitvoeren'>🎁</a>")
    return (f"<div class='accrow'><div class='acc-text'>{_e(text)}</div>"
            f"<div class='acc-ai'>{aff}</div></div>{sub}")


def _overview_html(st: _Stores, rec, csrf_token: str = "") -> str:
    d = rec.definition
    is_c = org.is_circle(rec)
    parts = [f"<div class='c2-sec'><h3>Purpose</h3><div>{_e(d.purpose) or '<span class=muted>—</span>'}</div></div>"]
    if is_c:
        parts.append("<div class='c2-sec'><h3>Strategy / Core Values</h3>"
                     + _todo("Strategie en kernwaarden per cirkel (nu alleen op de anchor-cirkel).")
                     + "</div>")
    doms = d.domains or []
    parts.append("<div class='c2-sec'><h3>Domains</h3>"
                 + ("<ul class='clean'>" + "".join(f"<li>{_e(x)}</li>" for x in doms) + "</ul>"
                    if doms else "<span class='muted'>Geen domein.</span>") + "</div>")
    accs = d.accountabilities or []
    if not is_c:
        parts.append("<div class='c2-sec'><h3>Accountabilities</h3>"
                     + ("".join(_acc_row(st, rec, i, a, csrf_token) for i, a in enumerate(accs))
                        if accs else "<span class='muted'>Geen accountabilities.</span>") + "</div>")
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


def _avatar(label: str, is_ai: bool) -> str:
    if is_ai:
        return "<span class='av ai'>AI</span>"
    return f"<span class='av'>{_e(_initials(label))}</span>"


# Genderneutraal 'persoon + toevoegen'-icoon (silhouet + plus), kleurt mee met currentColor.
_ICON_ADD_PERSON = (
    "<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<circle cx='9' cy='8' r='3.2'/>"
    "<path d='M3.5 20c0-3.2 2.5-5.6 5.5-5.6s5.5 2.4 5.5 5.6'/>"
    "<path d='M18.5 8.5v5M16 11h5'/></svg>")


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


def _members_html(st: _Stores, rec) -> str:
    ppl = _members_of_circle(st, rec.id)
    if not ppl:
        return "<div class='c2-sec'><h3>Members</h3><span class='muted'>Geen mensen.</span></div>"
    cells = "".join(
        f"<div class='card'><span class='person'><span class='av'>{_e(_initials(p.name))}</span>"
        f"<a href='/person?id={_e(p.id)}'>{_e(p.name)}</a></span></div>" for p in ppl)
    return f"<div class='c2-sec'><h3>Members ({len(ppl)})</h3>{cells}</div>"


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


_PROJ_CHIP = {
    "running": ("⚡ Actief", "var(--green)", "#fff"),
    "queued": ("🌱 Wachtrij", "var(--cream-2)", "var(--gray)"),
    "future": ("🌱 Toekomst", "var(--cream-2)", "var(--gray)"),
    "blocked": ("⏳ Wacht", "var(--coral)", "#fff"),
    "draft": ("📝 Concept", "var(--sand)", "var(--gray)"),
    "done": ("✓ Done", "var(--green-dark)", "#fff"),
}


def _proj_chip(status: str) -> str:
    lbl, bg, fg = _PROJ_CHIP.get(status, (status, "var(--cream-2)", "var(--gray)"))
    return (f'<span style="display:inline-block;padding:.05rem .5rem;border-radius:var(--radius-pill);'
            f'background:{bg};color:{fg};font-size:.72rem;font-weight:700">{_e(lbl)}</span>')


def _person_name(st: _Stores, pid: str) -> str:
    p = st.people.get(pid)
    return p.name if p else (pid or "")


def _age(ts) -> str:
    if not ts:
        return ""
    import time as _t
    d = max(0, int((_t.time() - ts) / 86400))
    if d == 0:
        return "vandaag"
    if d < 31:
        return f"{d} d oud"
    if d < 365:
        return f"{d//30} mnd oud"
    return f"{d//365} jr oud"


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


_PROJ_COLS = [("Actief", "actief", ("running", "queued")), ("Wacht", "wacht", ("blocked",)),
              ("Toekomst", "toekomst", ("future",)), ("Done", "done", ("done",))]


_LABELS = {"groen": "#1F9D55", "geel": "#FFCE2E", "koraal": "#FF6B5B",
           "blauw": "#2B5BB5", "paars": "#7A5BD1", "": ""}


def _proj_progress(p: dict):
    items = p.get("checklist") or []
    if not items:
        return None
    done = sum(1 for it in items if it.get("done"))
    return done, len(items), round(100 * done / len(items))


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


def _modal_html() -> str:
    """Herbruikbare detail-overlay (modal): klik op een kaart → haalt het fragment op en toont het;
    formulieren erin posten via fetch en verversen alleen de overlay. Val-terug: zonder JS navigeert
    de kaart-link naar de volledige /project-pagina. Bedoeld als standaard-patroon (ook kenniskaartjes)."""
    return (
        "<div id='ovl' class='ovl' style='display:none'><div class='ovl-box'>"
        "<button type='button' class='ovl-x' aria-label='sluiten'>✕</button>"
        "<div id='ovl-body'></div></div></div>"
        "<script>(function(){"
        "var ov=document.getElementById('ovl'),bd=document.getElementById('ovl-body'),last=null,dirty=false;"
        "function frag(u){return u+(u.indexOf('?')>-1?'&':'?')+'fragment=1';}"
        "function openCard(u){last=u;"
        "fetch(frag(u)).then(function(r){return r.text();}).then(function(h){bd.innerHTML=h;ov.style.display='flex';wire();});}"
        "function reopen(){if(last)openCard(last);}"
        "function shut(){ov.style.display='none';bd.innerHTML='';if(dirty){dirty=false;location.reload();}}"
        "function wire(){bd.querySelectorAll('form').forEach(function(f){f.addEventListener('submit',function(e){"
        "e.preventDefault();dirty=true;var act=(e.submitter&&e.submitter.value)||'';"
        "var data=new URLSearchParams(new FormData(f));"
        "if(e.submitter&&e.submitter.name){data.set(e.submitter.name,e.submitter.value);}"
        "fetch('/action',{method:'POST',body:data}).then(function(){"
        "if(act==='proj_delete'||act==='proj_archive'||act==='proj_add'){shut();}else{reopen();}});});});}"
        "document.querySelectorAll('.pcard[data-href],a.js-modal[data-href]').forEach(function(c){"
        "c.addEventListener('click',function(e){if(window.__pdrag)return;e.preventDefault();"
        "openCard(c.getAttribute('data-href'));});});"
        "ov.addEventListener('click',function(e){if(e.target===ov)shut();});"
        "document.querySelector('.ovl-x').addEventListener('click',shut);"
        "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&ov.style.display!=='none')shut();});"
        "})();</script>")


def _group_meta(st: _Stores, p: dict, mode: str, node_owner: str):
    """(gid, sorteersleutel, label, add_owner, add_trekker) voor groeperen per persoon/rol."""
    owner = p.get("owner") or ""
    if mode == "rol":
        if owner.startswith(_II_PREFIX):
            return (("ii", owner), "zzz", "Individual Initiative", owner, "")
        orec = st.records.get(owner)
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
                    group: str = "persoon") -> str:
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
                  f"{_columns_html(st, g['items'], g['ao'], g['at'], csrf_token, back, quickadd=True)}"
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


def _add_project_fragment(st: _Stores, rec, csrf_token: str, back: str) -> str:
    """De inhoud van de Add-Project-modal: titel + rol + persoon + status. Op een cirkel kies je
    de rol (directe rollen + Individual Initiative); op een rol staat die vast."""
    if org.is_circle(rec):
        direct = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
        opts = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in direct)
        opts += f"<option value='{_II_PREFIX}{_e(rec.id)}'>Individual Initiative</option>"
        role_field = f"<label>Rol</label><select name='owner'>{opts}</select>"
    else:
        role_field = (f"<input type='hidden' name='owner' value='{_e(rec.id)}'>"
                      f"<label>Rol</label><div class='muted'>{_e(_name(rec))}</div>")
    return (
        "<h2 style='margin-top:0'>Project toevoegen</h2>"
        "<div class='pf'>"
        "<form method='post' action='/action'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"<input type='hidden' name='next' value='{_e(back)}'>"
        "<label>Te bereiken uitkomst</label>"
        "<input name='scope' placeholder='bijv. Productpagina met Product Passport live' autofocus>"
        f"{role_field}"
        f"<label>Trekker (persoon of AI-agent)</label><select name='trekker'>{_trekker_options(st)}</select>"
        "<label>Status</label><select name='col'>"
        "<option value='actief'>Actief</option><option value='wacht'>Wacht</option>"
        "<option value='toekomst'>Toekomst</option></select>"
        "<div style='margin-top:.6rem'>"
        "<button class='btn ok' type='submit' name='action' value='proj_add'>Opslaan</button> "
        "<button type='button' class='btn' onclick=\"document.querySelector('.ovl-x').click()\">"
        "Annuleren</button>"
        "</div></form></div>")


def _add_project_trigger(rec, csrf_token: str) -> str:
    """Subtiele '+ project'-trigger (tekstlabel) die de Add-Project-modal opent."""
    if not csrf_token:
        return ""
    url = f"/addproject?node={_e(rec.id)}"
    return f"<a class='js-modal addlink' href='{url}' data-href='{url}'>+ project</a>"


def _projects_tab_html(st: _Stores, rec, csrf_token: str, group: str = "") -> str:
    allp = st.projects.all()
    back_base = f"/node?id={rec.id}&tab=projects"

    addlink = _add_project_trigger(rec, csrf_token)

    if not org.is_circle(rec):
        # ROL: eigen projecten, gegroepeerd per persoon (de doener). Lege lanes tonen we niet.
        projs = [p for p in allp if p.get("owner") == rec.id and not p.get("archived")]
        archived = [p for p in allp if p.get("owner") == rec.id and p.get("archived")]
        board = _projects_board(st, projs, rec.id, csrf_token, back_base, "persoon")
        if not board:
            board = "<p class='muted'>Nog geen projecten. Voeg er een toe met + project.</p>"
        head = (f"<div style='margin-bottom:1rem'>"
                f"<h3 style='margin:0;display:inline'>Projecten ({len(projs)})</h3> &nbsp; {addlink}</div>")
        return f"<div class='c2-sec'>{head}{board}{_archived_html(st, archived, csrf_token, back_base)}</div>"

    # CIRKEL: doet zelf geen uitvoerend werk. Toont projecten van haar DIRECTE rollen +
    # Individual Initiative. Lege lanes tonen we niet; subcirkels = eigen bord (niet aggregeren).
    g = group if group in ("persoon", "rol") else "rol"
    direct = sorted(org.roles_of(st.records.all(), rec.id), key=lambda r: _name(r).lower())
    rids = {r.id for r in direct}
    ii = f"{_II_PREFIX}{rec.id}"
    projs = [p for p in allp if (p.get("owner") in rids or p.get("owner") == ii) and not p.get("archived")]
    back = f"{back_base}&group={g}"
    board = _projects_board(st, projs, rec.id, csrf_token, back, g)
    if not board:
        board = "<p class='muted'>Nog geen projecten. Voeg er een toe met + project.</p>"
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
    note = ("<p class='muted' style='font-size:.8rem;margin:-.6rem 0 .6rem'>Een cirkel doet zelf "
            "geen werk: projecten horen bij de rollen of bij Individual Initiative.</p>")
    return f"<div class='c2-sec'>{head}{note}{board}{sub_html}</div>"


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


def render_node(st: _Stores, node_id: str, tab: str, csrf_token: str = "", msg: str = "",
                group: str = "") -> str:
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
    elif tab == "roles":
        content = _roles_html(st, rec, csrf_token)
    elif tab == "members":
        content = _members_html(st, rec)
    elif tab == "notes":
        content = ("<div class='c2-sec'><h3>Notes</h3>"
                   + _att_html(st, rec, "note", "Nog geen notities op deze rol/cirkel.")
                   + "<p class='muted' style='font-size:.8rem'>Hierin vouwen we Nooch's "
                   "concurrenten-notities.</p></div>")
    elif tab == "metrics":
        content = ("<div class='c2-sec'><h3>Metrics</h3>"
                   + _att_html(st, rec, "metric", "Nog geen metrics.")
                   + "<p class='muted' style='font-size:.8rem'>Hierin vouwen we het "
                   "zoekwoord-volume.</p></div>")
    elif tab == "checklists":
        content = ("<div class='c2-sec'><h3>Checklists</h3>"
                   + _att_html(st, rec, "checklist", "Nog geen checklist-items.") + "</div>")
    elif tab == "projects":
        content = _projects_tab_html(st, rec, csrf_token, group=group)
    elif tab == "policies":
        content = _todo("Policies per cirkel (nu alleen harde policies op de anchor-cirkel).")
    else:  # history
        content = _todo("Wijzigingsgeschiedenis per rol/cirkel (records dragen al versies; de "
                        "weergave moet nog).")

    # Meetings zijn een CIRKEL-functie (een rol heeft geen governance/tactical meeting).
    meet = ("<div class='c2-meet'>"
            "<span class='btn grey' title='governance draait in cockpit 1'>▾ Governance meeting</span>"
            "<span class='btn grey' title='nog te bouwen'>▾ Tactical meeting</span></div>") if is_c else ""
    main = (f"<div class='c2-main'><div class='c2-bar'>{crumb}</div>"
            f"<h1>{_e(_name(rec))} {chip}</h1>{_banner(msg)}{meet}"
            f"{_tabbar(node_id, tabs, tab)}{content}</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, node_id)}</div>"
    modal = _modal_html() if (csrf_token and tab in ("projects", "roles", "overview")) else ""
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · GlassFrog-vorm (PoC) · "
             "<a href='/'>home</a></div>"
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
    main = (f"<div class='c2-main'><h1><span class='av' style='width:28px;height:28px'>"
            f"{_e(_initials(p.name))}</span> {_e(p.name)}</h1>"
            f"<div class='muted'>{_e(p.email) or 'geen e-mail'}</div>"
            f"<div class='c2-sec'><h3>Mijn rollen ({len(role_ids)})</h3>"
            + (f"<ul class='clean'>{rows}</ul>" if rows else "<span class='muted'>Geen rollen.</span>")
            + "</div>" + _person_projects_html(st, pid) + "</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, '')}</div>"
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · GlassFrog-vorm (PoC) · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}{rail}</div>")
    return _page(p.name, inner)


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

    # Checklist met voortgangsbalk
    items = p.get("checklist") or []
    pr = _proj_progress(p)
    bar = ""
    if pr:
        bar = (f"<div class='ck-prog'><div class='pbar' style='flex:1'><div style='width:{pr[2]}%'></div></div>"
               f"<span class='muted'>{pr[2]}% ({pr[0]}/{pr[1]})</span></div>")
    ck_rows = ""
    for it in items:
        done = it.get("done")
        chk = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
               f"<input type='hidden' name='item' value='{_e(it['id'])}'>"
               f"<button class='ck-box{' on' if done else ''}' type='submit' name='action' "
               f"value='check_toggle'>{'✓' if done else ''}</button></form>") if rw else (
               "☑" if done else "☐")
        rm = (f"<form method='post' action='/action' style='display:inline'>{hid()}"
              f"<input type='hidden' name='item' value='{_e(it['id'])}'>"
              f"<button class='dellink' type='submit' name='action' value='check_remove'>✕</button></form>") if rw else ""
        txt = f"<span class='{'ck-done' if done else ''}'>{_e(it['text'])}</span>"
        ck_rows += f"<li class='ck-item'>{chk} {txt} {rm}</li>"
    ck_add = (f"<form method='post' action='/action' class='qadd-form' style='margin-top:.3rem'>{hid()}"
              f"<input name='text' placeholder='item toevoegen…'>"
              f"<button class='btn' type='submit' name='action' value='check_add'>+</button></form>") if rw else ""
    checklist = (f"<div class='c2-sec'><h3>Checklist</h3>{bar}"
                 f"<ul class='clean ck-list'>{ck_rows or '<li class=muted>nog geen items</li>'}</ul>{ck_add}</div>")

    # Activiteiten/opmerkingen-feed
    feed = ""
    for m in (p.get("log") or []):
        who = "🤖 AI" if m.get("who") == "rol" else "🙋 jij"
        feed += (f"<div class='tg-dlg' style='border:1px solid var(--border);border-radius:var(--radius);"
                 f"padding:.4rem .6rem;margin:.3rem 0'><b>{who}</b> "
                 f"<span class='muted' style='font-size:.74rem'>· {_e(_age(m.get('at')))}</span>"
                 f"<div>{_e(m.get('text',''))}</div></div>")
    comment = (f"<form method='post' action='/action' class='pf' style='margin-top:.4rem'>{hid()}"
               f"<textarea name='comment' rows='2' placeholder='opmerking of voortgang…'></textarea>"
               f"<button class='btn ok' type='submit' name='action' value='proj_comment' "
               f"style='margin-top:.3rem'>plaatsen</button></form>") if rw else ""
    feedsec = f"<div class='c2-sec'><h3>Activiteit & opmerkingen</h3>{feed}{comment}</div>"

    # Bewerken (scope/omschrijving/trekker/label/zichtbaarheid) + archiveren/verwijderen
    edit = ""
    if rw:
        lopts = "".join(f"<option value='{k}'{' selected' if p.get('label')==k else ''}>"
                        f"{k or '— geen —'}</option>" for k in _LABELS)
        edit = (
            f"<details class='c2-sec'><summary style='font-weight:700'>✎ bewerken</summary>"
            f"<div class='pf'><form method='post' action='/action'>{hid()}"
            f"<label>Titel</label><input name='scope' value='{_e(_scope_text(p))}'>"
            f"<label>Omschrijving</label><textarea name='description' rows='3'>{_e(p.get('description',''))}</textarea>"
            f"<label>Trekker</label><select name='trekker'>{_trekker_options(st, p.get('person') or '', p.get('agent') or '')}</select>"
            f"<label>Kleurlabel (koppeling met doel, later)</label><select name='label'>{lopts}</select>"
            f"<label style='font-size:.85rem'><input type='checkbox' name='private' value='1'"
            f"{' checked' if p.get('private') else ''}> alleen zichtbaar voor de cirkel</label>"
            f"<button class='btn ok' type='submit' name='action' value='proj_edit' style='margin-top:.4rem'>opslaan</button>"
            f"</form>"
            f"<div style='margin-top:.5rem'>"
            f"<form method='post' action='/action' style='display:inline'>{hid()}"
            f"<input type='hidden' name='next' value='{_e(back)}'>"
            f"<button class='btn' type='submit' name='action' value='proj_archive'>🗄 archiveren</button></form> "
            f"<form method='post' action='/action' style='display:inline'>{hid()}"
            f"<input type='hidden' name='next' value='{_e(back)}'>"
            f"<button class='dellink' type='submit' name='action' value='proj_delete' "
            f"onclick=\"return confirm('Definitief verwijderen? Archiveren bewaart het project.')\">verwijderen</button>"
            f"</form></div></div></details>")

    labelbar = ""
    if _LABELS.get(p.get("label")):
        labelbar = f"<div class='clabel' style='background:{_LABELS[p['label']]};height:8px;border-radius:4px;margin-bottom:.4rem'></div>"

    # Status-schakelaar (in de modal kun je niet slepen): de vier kolommen als knoppen.
    status = p.get("status", "")
    switch = ""
    if rw:
        btns = ""
        for label, key, statuses in _PROJ_COLS:
            act = "proj_done" if key == "done" else "proj_status"
            to = "" if key == "done" else f"<input type='hidden' name='to' value='{key}'>"
            on = " on" if status in statuses else ""
            btns += (f"<form method='post' action='/action' style='display:inline'>{hid()}{to}"
                     f"<button class='sw{on}' type='submit' name='action' value='{act}'>{_e(label)}</button></form>")
        switch = f"<div class='swrow'>{btns}</div>"

    # Overzicht-grid: trekker, eigenaar, label, zichtbaarheid, voortgang, leeftijd.
    lab = "<span class='muted'>—</span>"
    if _LABELS.get(p.get("label")):
        lab = f"<span class='dot' style='background:{_LABELS[p['label']]}'></span>{_e(p.get('label'))}"
    vis = "Alleen deze cirkel" if p.get("private") else "Hele cirkel-boom"
    prog = f"{pr[2]}% ({pr[0]}/{pr[1]})" if pr else "<span class='muted'>—</span>"
    meta = ("<div class='pmeta'>"
            f"<div><span class='k'>Trekker</span><span>{_trekker_html(st, p)}</span></div>"
            f"<div><span class='k'>Rol / eigenaar</span><span>{owner_link}</span></div>"
            f"<div><span class='k'>Label</span><span>{lab}</span></div>"
            f"<div><span class='k'>Zichtbaarheid</span><span>{vis}</span></div>"
            f"<div><span class='k'>Voortgang</span><span>{prog}</span></div>"
            f"<div><span class='k'>Aangemaakt</span><span>{_e(_age(p.get('created_at')))}</span></div>"
            "</div>")

    desc = (f"<div class='c2-sec'><h3>Omschrijving</h3>"
            f"<div>{_e(p.get('description','')) or '<span class=muted>geen omschrijving</span>'}</div></div>")
    detail = (f"{labelbar}<h1 style='margin-top:0'>{_e(_scope_text(p))} {_proj_chip(status)}</h1>"
              f"{switch}{meta}{_banner(msg)}{desc}{checklist}{feedsec}{edit}")
    if fragment:
        return detail
    main = (f"<div class='c2-main' style='max-width:720px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{detail}</div>")
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · projectdetail · <a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}</div>")
    return _page(_scope_text(p), inner)


def render_addproject(st: _Stores, node_id: str, csrf_token: str = "", fragment: bool = False) -> str:
    rec = st.records.get(node_id)
    if rec is None:
        return ("<p class='muted'>Onbekende rol/cirkel.</p>" if fragment
                else _page("Niet gevonden", "<p>Onbekend.</p><p><a href='/'>← home</a></p>"))
    back = f"/node?id={rec.id}&tab=projects"
    frag = _add_project_fragment(st, rec, csrf_token, back)
    if fragment:
        return frag
    main = (f"<div class='c2-main' style='max-width:560px'>"
            f"<div class='c2-bar'><a href='{_e(back)}'>← terug</a></div>{frag}</div>")
    return _page("Project toevoegen",
                 f"<style>{_EXTRA_CSS}</style><div class='c2-wrap'>{main}</div>")


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


def _parse_trekker(val: str):
    """'person:<id>' of 'persona:<id>' → (person_id of '', agent_id of '')."""
    val = (val or "").strip()
    if val.startswith("person:"):
        return val[7:], ""
    if val.startswith("persona:"):
        return "", val[8:]
    return "", ""


def dispatch(data_dir: str, action: str, form: dict):
    """Verwerk een POST-actie. Geeft (redirect-URL, korte bevestiging) terug."""
    st = _Stores(data_dir)
    g = lambda k: (form.get(k) or [""])[0]
    nxt = g("next") or "/"
    if not nxt.startswith("/"):
        nxt = "/"
    pj = st.projects
    msg = ""
    if action == "proj_add":
        owner = g("owner")
        scope = g("scope").strip()
        person, agent = _parse_trekker(g("trekker"))
        col = g("col")
        create_status = "future" if col == "toekomst" else "queued"
        orec = st.records.get(owner)
        if orec is not None and org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: projecten horen bij een rol of Individual Initiative.
            return nxt, "✗ een cirkel kan geen project bevatten — kies een rol of Individual Initiative"
        if owner and scope:
            pid = pj.create(owner, scope[:200], "human", status=create_status,
                            person=person or None, agent=agent or None, private=(g("private") == "1"))
            if col == "wacht":
                pj.block(pid, "—")
            msg = "➕ project toegevoegd"
    elif action == "proj_status":
        to = g("to")
        if to == "actief":
            pj.start(g("pid"))
        elif to == "wacht":
            pj.block(g("pid"), "—")
        elif to == "toekomst":
            pj.to_future(g("pid"))
        msg = "✓ verplaatst"
    elif action == "proj_done":
        pj.complete(g("pid")); msg = "✓ afgerond"
    elif action == "proj_archive":
        pj.archive(g("pid")); msg = "🗄 gearchiveerd (blijft bestaan)"
    elif action == "proj_unarchive":
        pj.unarchive(g("pid")); msg = "↩ hersteld"
    elif action == "proj_delete":
        pj.remove(g("pid")); msg = "🗑 verwijderd"
    elif action == "proj_edit":
        person, agent = _parse_trekker(g("trekker"))
        pj.edit(g("pid"), scope=g("scope"), person=person, agent=agent,
                private=(g("private") == "1"), description=g("description"), label=g("label"))
        msg = "💾 opgeslagen"
    elif action == "proj_comment":
        if pj.add_comment(g("pid"), g("comment")):
            msg = "💬 geplaatst"
    elif action == "check_add":
        if pj.check_add(g("pid"), g("text")):
            msg = "✓ item toegevoegd"
    elif action == "check_toggle":
        pj.check_toggle(g("pid"), g("item"))
    elif action == "check_remove":
        pj.check_remove(g("pid"), g("item")); msg = "🗑 item verwijderd"
    elif action == "role_assign":
        person, agent = _parse_trekker(g("filler"))
        if person and st.assign.assign(g("role"), "person", person):
            msg = "✓ toegewezen"
        elif agent and st.assign.assign(g("role"), "persona", agent):
            msg = "🤖 AI toegewezen"
    elif action == "role_unassign":
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.unassign(g("role"), "person", person)
        elif agent:
            st.assign.unassign(g("role"), "persona", agent)
        msg = "✓ verwijderd"
    elif action == "role_focus":
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.set_focus(g("role"), "person", person, g("focus"))
        elif agent:
            st.assign.set_focus(g("role"), "persona", agent, g("focus"))
        msg = "✓ focus opgeslagen"
    elif action == "aitask_add":
        try:
            acc_i = int(g("acc"))
        except ValueError:
            acc_i = -1
        pick = g("pick")
        if "::" in pick:
            agent, skill = pick.split("::", 1)
        else:
            agent, skill = g("agent"), g("wat")   # fallback (legacy)
        if agent and acc_i >= 0 and st.ai.add(g("role"), acc_i, agent, skill):
            msg = "🤖 AI gekoppeld aan accountability"
    elif action == "aitask_remove":
        st.ai.remove(g("tid")); msg = "✓ verwijderd"
    elif action == "persona_skill_add":
        if st.personas.add_skill(g("agent"), g("skill")):
            msg = "✓ skill aan rugzak toegevoegd"
    return nxt, msg


def make_handler(data_dir: str, csrf_token: str):
    class H(BaseHTTPRequestHandler):
        def _send(self, body: str, code: int = 200):
            b = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            st = _Stores(data_dir)
            if path in ("/", "/index.html"):
                roots = org.roots(st.records.all())
                if roots:
                    self.send_response(302)
                    self.send_header("Location", f"/node?id={roots[0].id}")
                    self.end_headers()
                    return
                self._send(_page("Leeg", "<p>Nog geen organisatie geladen.</p>"))
                return
            if path == "/node":
                self._send(render_node(st, (qs.get("id") or [""])[0],
                                       (qs.get("tab") or ["overview"])[0], csrf_token=csrf_token,
                                       msg=(qs.get("msg") or [""])[0],
                                       group=(qs.get("group") or [""])[0]))
                return
            if path == "/project":
                self._send(render_project(st, (qs.get("pid") or [""])[0], csrf_token=csrf_token,
                                          msg=(qs.get("msg") or [""])[0],
                                          back=(qs.get("back") or ["/"])[0],
                                          fragment=(qs.get("fragment") or [""])[0] == "1"))
                return
            if path == "/addproject":
                self._send(render_addproject(st, (qs.get("node") or [""])[0], csrf_token=csrf_token,
                                             fragment=(qs.get("fragment") or [""])[0] == "1"))
                return
            if path == "/rolefillers":
                self._send(render_rolefillers(st, (qs.get("role") or [""])[0], csrf_token=csrf_token,
                                              fragment=(qs.get("fragment") or [""])[0] == "1"))
                return
            if path == "/aitask":
                try:
                    acc_i = int((qs.get("acc") or ["-1"])[0])
                except ValueError:
                    acc_i = -1
                self._send(render_aitask(st, (qs.get("role") or [""])[0], acc_i, csrf_token=csrf_token,
                                         fragment=(qs.get("fragment") or [""])[0] == "1"))
                return
            if path == "/person":
                self._send(render_person(st, (qs.get("id") or [""])[0]))
                return
            self._send("<p>404</p>", 404)

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/action":
                self._send("<p>404</p>", 404); return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            form = urllib.parse.parse_qs(raw)
            token = (form.get("csrf") or [""])[0]
            if not secrets.compare_digest(token, csrf_token):
                self._send("CSRF-token ongeldig", 403); return
            action = (form.get("action") or [""])[0]
            nxt, msg = dispatch(data_dir, action, form)
            if msg:
                sep = "&" if "?" in nxt else "?"
                nxt = f"{nxt}{sep}msg={urllib.parse.quote(msg)}"
            self.send_response(303); self.send_header("Location", nxt); self.end_headers()

        def log_message(self, *_):
            pass
    return H


def serve(host: str = "127.0.0.1", port: int = 8766, data_dir: str | None = None) -> None:
    if host not in _LOCAL_HOSTS:
        raise SystemExit(f"Cockpit 2 weigert niet-lokale host '{host}'.")
    dd = data_dir or _default_data_dir()
    _bootstrap(dd)
    csrf_token = secrets.token_urlsafe(32)
    httpd = ThreadingHTTPServer((host, port), make_handler(dd, csrf_token))
    httpd.daemon_threads = True
    print(f"Cockpit 2 (GlassFrog-vorm, PoC) op http://{host}:{port}  —  Ctrl-C om te stoppen")
    print(f"Dataset: {dd}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCockpit 2 gestopt.")
    finally:
        httpd.server_close()


def _match_ladder() -> str:
    """Eén werkende, lokaal beschikbare trede voor de matcher. Default Anthropic (Gemini vereist
    google-generativeai). Override via env LLM_MATCH_LADDER (bijv. 'mistral')."""
    return os.getenv("LLM_MATCH_LADDER", "anthropic")


def _load_env() -> None:
    """Laad project-.env in os.environ (idempotent, setdefault), zodat de losse cockpit2-CLI
    dezelfde LLM-keys ziet als de volledige village. Zoekt .env in cwd en repo-root."""
    import pathlib
    seen = set()
    for cand in (os.path.join(os.getcwd(), ".env"),
                 os.path.join(pathlib.Path(__file__).resolve().parent.parent, ".env")):
        if cand in seen or not os.path.exists(cand):
            continue
        seen.add(cand)
        for line in open(cand):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def refresh_matches(data_dir: str | None = None, ask=None, progress=None) -> int:
    """Achtergrond-pas: laat de LLM per (accountability, skill) oordelen en cache het, zodat het
    cadeautje semantisch matcht. Zonder key/`ask` is dit een no-op (fail-closed); de render valt
    dan terug op lexicaal + concept. `ask` is injecteerbaar voor tests."""
    dd = data_dir or _default_data_dir()
    _bootstrap(dd)
    st = _Stores(dd)
    if ask is None:
        try:
            from nooch_village import llm
        except Exception:
            return 0

        def ask(acc: str, skill: str):
            prompt = ("Ondersteunt de vaardigheid een verantwoordelijkheid? Antwoord met enkel "
                      f"'ja' of 'nee'.\nVerantwoordelijkheid: {acc}\nVaardigheid: {skill}")
            out = llm.reason(prompt, ladder=_match_ladder())
            if not out:
                return None
            o = out.strip().lower()
            if o.startswith("ja") or o.startswith("yes"):
                return True
            if o.startswith("nee") or o.startswith("no"):
                return False
            return None

    skills = sorted({s for p in st.personas.all() for s in (p.skills or [])})
    accs = sorted({a for r in st.records.all() if not org.is_circle(r)
                   for a in (r.definition.accountabilities or [])})
    pairs = [(a, s) for a in accs for s in skills]
    return ai_match.refresh_semantic(pairs, ask, st.match, skip_cached=True, progress=progress)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="nooch_village.cockpit2")
    ap.add_argument("cmd", nargs="?", default="serve", choices=["serve", "match"],
                    help="serve = cockpit; match = achtergrond semantische matcher vullen")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--data-dir", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "match":
        _load_env()   # zorg dat .env-keys beschikbaar zijn voor de losse CLI
        # Snelle key-check: zonder LLM-key heeft de achtergrond-pas niets te doen.
        try:
            from nooch_village import llm
            has_key = bool(llm.reason("antwoord met 'ok'", ladder=_match_ladder()))
        except Exception:
            has_key = False
        if not has_key:
            print("Geen werkende LLM-key gevonden. De matcher draait al op lexicaal + concept "
                  "(code ~ feature, bug ~ testscript); de semantische laag voegt pas iets toe "
                  "met een Anthropic- of Gemini-key in .env. Niets te doen.")
            return

        def progress(i, total, acc, skill):
            print(f"  [{i}/{total}] {acc[:40]} ↔ {skill[:30]}", flush=True)

        print("Semantische matcher: oordelen ophalen (al-gecachete paren worden overgeslagen)…",
              flush=True)
        n = refresh_matches(a.data_dir, progress=progress)
        print(f"Klaar: {n} nieuwe paren bepaald en gecachet.")
        return
    serve(host=a.host, port=a.port, data_dir=a.data_dir)


if __name__ == "__main__":
    main()
