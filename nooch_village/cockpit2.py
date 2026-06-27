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
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nooch_village.cockpit import _e, _page              # zelfde design system
from nooch_village.governance import Records
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore
from nooch_village.personas import PersonaStore
from nooch_village.projects import ProjectLedger
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


def _overview_html(st: _Stores, rec) -> str:
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
    parts.append("<div class='c2-sec'><h3>Accountabilities</h3>"
                 + ("<ul class='clean'>" + "".join(f"<li>{_e(x)}</li>" for x in accs) + "</ul>"
                    if accs else "<span class='muted'>Geen accountabilities.</span>") + "</div>")
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


def _roles_html(st: _Stores, rec) -> str:
    recs = st.records.all()
    subs = sorted(org.subcircles_of(recs, rec.id), key=lambda r: _name(r).lower())
    roles = sorted(org.roles_of(recs, rec.id), key=lambda r: _name(r).lower())
    out = []
    if subs:
        out.append("<div class='c2-sec'><h3>Subcirkels</h3><ul class='clean'>"
                   + "".join(f"<li><a href='/node?id={_e(s.id)}'>{_e(_name(s))}</a> "
                             f"<span class='chip'>cirkel</span></li>" for s in subs) + "</ul></div>")
    out.append("<div class='c2-sec'><h3>Rollen</h3>"
               + ("<ul class='clean'>" + "".join(
                   f"<li><a href='/node?id={_e(r.id)}'>{_e(_name(r))}</a> "
                   f"<span class='muted'>{_e(_fillsummary(st, r))}</span></li>" for r in roles)
                  + "</ul>" if roles else "<span class='muted'>Geen rollen.</span>") + "</div>")
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


def _proj_li(st: _Stores, p: dict, show_owner: bool = False) -> str:
    scope = p.get("scope")
    if isinstance(scope, dict):
        scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
    person = p.get("person")
    who = (f' <span class="muted">· trekker: {_e(_person_name(st, person))}</span>' if person else "")
    owner = ""
    if show_owner and p.get("owner"):
        orec = st.records.get(p["owner"])
        owner = f' <span class="muted">· {_e(_name(orec) if orec else p["owner"])}</span>'
    return f'<li>{_proj_chip(p.get("status",""))} {_e(str(scope or "—"))}{who}{owner}</li>'


def _projects_tab_html(st: _Stores, rec, csrf_token: str) -> str:
    projs = [p for p in st.projects.all() if p.get("owner") == rec.id]
    projs.sort(key=lambda p: (p.get("status") == "done", -(p.get("created_at") or 0)))
    lst = ("<ul class='clean'>" + "".join(_proj_li(st, p) for p in projs) + "</ul>"
           if projs else "<p class='muted'>Nog geen projecten op deze rol/cirkel.</p>")
    form = ""
    if csrf_token:
        opts = "<option value=''>— geen trekker —</option>" + "".join(
            f"<option value='{_e(p.id)}'>{_e(p.name)}</option>" for p in st.people.all())
        form = (
            "<div class='pf' style='margin-top:.8rem;max-width:520px'>"
            "<form method='post' action='/action'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='owner' value='{_e(rec.id)}'>"
            f"<input type='hidden' name='next' value='/node?id={_e(rec.id)}&tab=projects'>"
            "<label>Nieuw project — wat lever je op?</label>"
            "<input name='scope' placeholder='bijv. Productpagina met Product Passport live'>"
            "<label>Trekker (optioneel)</label>"
            f"<select name='person'>{opts}</select>"
            "<button class='btn ok' type='submit' name='action' value='proj_add' "
            "style='margin-top:.5rem'>➕ project toevoegen</button>"
            "</form></div>")
    return f"<div class='c2-sec'><h3>Projecten ({len(projs)})</h3>{lst}{form}</div>"


def _person_projects_html(st: _Stores, pid: str) -> str:
    role_ids = set(st.assign.roles_of("person", pid))
    projs = [p for p in st.projects.all()
             if p.get("person") == pid or p.get("owner") in role_ids]
    projs.sort(key=lambda p: (p.get("status") == "done", -(p.get("created_at") or 0)))
    if not projs:
        return ""
    lst = "<ul class='clean'>" + "".join(_proj_li(st, p, show_owner=True) for p in projs) + "</ul>"
    return f"<div class='c2-sec'><h3>Projecten ({len(projs)})</h3>{lst}</div>"


def render_node(st: _Stores, node_id: str, tab: str, csrf_token: str = "") -> str:
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
        content = _overview_html(st, rec)
    elif tab == "roles":
        content = _roles_html(st, rec)
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
        content = _projects_tab_html(st, rec, csrf_token)
    elif tab == "policies":
        content = _todo("Policies per cirkel (nu alleen harde policies op de anchor-cirkel).")
    else:  # history
        content = _todo("Wijzigingsgeschiedenis per rol/cirkel (records dragen al versies; de "
                        "weergave moet nog).")

    meet = ("<div class='c2-meet'>"
            "<span class='btn grey' title='governance draait in cockpit 1'>▾ Governance meeting</span>"
            "<span class='btn grey' title='nog te bouwen'>▾ Tactical meeting</span></div>")
    main = (f"<div class='c2-main'><div class='c2-bar'>{crumb}</div>"
            f"<h1>{_e(_name(rec))} {chip}</h1>{meet}"
            f"{_tabbar(node_id, tabs, tab)}{content}</div>")
    rail = f"<div class='c2-rail'>{_tree_html(st, node_id)}</div>"
    inner = (f"<style>{_EXTRA_CSS}</style>"
             "<div class='bar'>cockpit 2 · GlassFrog-vorm (PoC, read-only) · "
             "<a href='/'>home</a></div>"
             f"<div class='c2-wrap'>{main}{rail}</div>")
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


def dispatch(data_dir: str, action: str, form: dict) -> str:
    """Verwerk een POST-actie en geef de redirect-URL terug. Nu: een project toevoegen."""
    st = _Stores(data_dir)
    nxt = (form.get("next") or ["/"])[0]
    if not nxt.startswith("/"):
        nxt = "/"
    if action == "proj_add":
        owner = (form.get("owner") or [""])[0]
        scope = (form.get("scope") or [""])[0].strip()
        person = (form.get("person") or [""])[0].strip() or None
        if owner and scope:
            st.projects.create(owner, scope[:200], "human", status="queued", person=person)
    return nxt


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
                                       (qs.get("tab") or ["overview"])[0], csrf_token=csrf_token))
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
            nxt = dispatch(data_dir, action, form)
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


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="nooch_village.cockpit2")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--data-dir", default=None)
    a = ap.parse_args(argv)
    serve(host=a.host, port=a.port, data_dir=a.data_dir)


if __name__ == "__main__":
    main()
