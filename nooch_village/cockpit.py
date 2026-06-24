"""Cockpit — mens-oppervlak over het draaiende dorp (lezen + veilig verwerken).

Drie stores, één pagina: records (roster), human_inbox, projects (proces).
Schrijven kan voor de veilige, niet-interactieve inbox-acties (keyword approve/reject,
defer, confirm) en loopt UITSLUITEND via het gedeelde gevalideerde pad (inbox_actions),
nooit direct naar een store. Bindt uitsluitend op 127.0.0.1, POST is CSRF-beveiligd.
Dit is de mens-kant van de auth-grens; de rijkere rails (project/governance/rol-vragen)
volgen in een latere stap. Zie docs/ONTWERP_cockpit_rol_skill_werkbank.md.

Draaien:
    python -m nooch_village.cockpit                 # http://127.0.0.1:8765
    python -m nooch_village.cockpit --port 9000
"""
from __future__ import annotations

import os
import html
import time
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from nooch_village.governance import Records
from nooch_village.human_inbox import HumanInbox
from nooch_village.projects import ProjectLedger
from nooch_village.library import Library
from nooch_village.notes_store import NotesStore
from nooch_village.inbox_actions import (
    decide_keyword, defer_item, confirm_item, mark_done, add_reference)

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _default_data_dir() -> str:
    # nooch_village/cockpit.py -> project root is één niveau omhoog
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def gather(data_dir: str | None = None) -> dict:
    """Lees de drie stores read-only. Pure functie: geen Village, geen netwerk.

    Ontbrekende bestanden leveren lege lijsten (fail-safe, niet fail-hard).
    """
    dd = data_dir or _default_data_dir()
    records = Records(os.path.join(dd, "governance_records.json"))
    inbox = HumanInbox(os.path.join(dd, "human_inbox.json"))
    projects = ProjectLedger(os.path.join(dd, "projects.json"))

    roster = []
    for rec in sorted(records.all(), key=lambda r: (r.archived, r.type.value, r.id)):
        d = rec.definition
        roster.append({
            "id": rec.id,
            "type": rec.type.value,
            "parent": rec.parent,
            "version": rec.version,
            "archived": rec.archived,
            "source": rec.source,
            "purpose": d.purpose,
            "accountabilities": list(d.accountabilities),
            "domains": list(d.domains),
            "skills": list(d.skills),
            "policies": list(d.policies),
            "members": list(rec.members),
        })

    inbox_items = sorted(
        inbox.all(),
        key=lambda i: (i.get("status") != "pending", -(i.get("created_at") or 0)),
    )
    proj = sorted(projects.all(), key=lambda p: -(p.get("updated_at") or 0))

    return {
        "roster": roster,
        "inbox": inbox_items,
        "projects": proj,
        "generated_at": time.time(),
        "data_dir": dd,
    }


# ── render (puur, geen I/O) ──────────────────────────────────────────────────

_SOURCE_MARK = {"sensed": "✱ sensed", "demo": "⚙ demo", "seed": "seed"}


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _chips(items: list[str]) -> str:
    if not items:
        return '<span class="muted">—</span>'
    return " ".join(f'<span class="chip">{_e(i)}</span>' for i in items)


def _ts(ts) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


# ── Nooch design system (tokens uit nooch-shop/assets/design-tokens.css) ──────

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Bricolage+Grotesque:wght@600;800&family=DM+Sans:wght@400;500;700&display=swap">'
)

_CSS = """
:root{
 --ink:#1B1B1B;--gray:#4A4A4A;--subtle:#7A7A7A;--muted:#9A9483;
 --green:#1F9D55;--green-dark:#14713C;--green-tint:#D3EFDD;
 --cream:#FCFAF4;--cream-2:#FBF6EA;--cream-3:#FFF7E8;--sand:#F1ECDF;--surface:#fff;
 --yellow:#FFCE2E;--yellow-light:#FFF1B8;--coral:#FF6B5B;--border:#DDD4C0;
 --font-display:'Bricolage Grotesque',system-ui,sans-serif;
 --font-body:'DM Sans',system-ui,sans-serif;
 --radius:9px;--radius-pill:999px;
 --shadow:0 1px 2px rgba(27,27,27,.06),0 2px 8px rgba(27,27,27,.04);
}
*{box-sizing:border-box}
body{font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--ink);
 background:var(--cream);margin:0;padding:1.6rem 2rem;max-width:1180px}
h1{font-family:var(--font-display);font-weight:800;font-size:1.5rem;margin:0}
h2{font-family:var(--font-display);font-weight:800;font-size:.95rem;text-transform:uppercase;
 letter-spacing:.03em;margin:1.8rem 0 .5rem;color:var(--green-dark)}
a{color:var(--green-dark)}
.bar{color:var(--gray);margin:.4rem 0 1.2rem;font-size:13px}
.badge{font-size:.66rem;text-transform:uppercase;letter-spacing:.05em;font-weight:700;
 padding:.18rem .55rem;border-radius:var(--radius-pill);vertical-align:middle;margin-left:.4rem}
.badge.ro{background:var(--sand);color:var(--gray)}
.badge.rw{background:var(--green-tint);color:var(--green-dark)}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--surface);
 border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
th,td{border-bottom:1px solid var(--border);padding:.5rem .6rem;text-align:left;vertical-align:top}
th{background:var(--cream-2);font-family:var(--font-display);font-weight:700;
 text-transform:uppercase;font-size:11px;letter-spacing:.03em;color:var(--gray)}
tr:last-child td{border-bottom:none}
tr.archived td{opacity:.45}
tr.st-pending td{background:var(--yellow-light)}
tr.st-blocked td{background:#FDEAEA}
tr.st-running td{background:var(--green-tint)}
.chip{display:inline-block;background:var(--green-tint);color:var(--green-dark);
 border-radius:var(--radius-pill);padding:.1rem .55rem;margin:.06rem;font-size:12px}
.muted{color:var(--muted)}
.btn{font-family:var(--font-body);font-weight:600;font-size:12px;border:1px solid rgba(27,27,27,.14);
 border-radius:var(--radius-pill);background:transparent;color:var(--ink);
 padding:.3rem .85rem;margin:.12rem;cursor:pointer;display:inline-block;text-decoration:none}
.btn:hover{background:rgba(27,27,27,.05)}
.btn.ok{background:var(--green);border-color:var(--green);color:#fff}
.btn.ok:hover{background:var(--green-dark);border-color:var(--green-dark)}
.btn.no{background:#fff;border-color:var(--coral);color:var(--coral)}
.tension{background:var(--cream-3);border:1px solid var(--border);border-radius:var(--radius);
 padding:.7rem .9rem;margin:.6rem 0 1.4rem}
details{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
 margin:.5rem 0;padding:.3rem .9rem;box-shadow:var(--shadow)}
details[open]{padding-bottom:.8rem}
details>summary{cursor:pointer;font-family:var(--font-display);font-weight:700;padding:.45rem 0}
.pf label{display:block;margin:.6rem 0 .2rem;font-size:13px;color:var(--gray)}
.pf input,.pf select{width:100%;padding:.45rem;border:1px solid var(--border);
 border-radius:var(--radius);font:inherit;background:#fff}
"""


def _page(title: str, inner: str) -> str:
    return (f'<!doctype html><html lang="nl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)}</title>{_FONTS}<style>{_CSS}</style></head>'
            f'<body>{inner}</body></html>')


def _btn(iid: str, action: str, label: str, token: str, cls: str = "") -> str:
    """Een mini-formulier-knop die via POST /action de gevalideerde inbox-actie aantrapt."""
    return (
        f'<form method="post" action="/action" style="display:inline">'
        f'<input type="hidden" name="csrf" value="{_e(token)}">'
        f'<input type="hidden" name="iid" value="{_e(iid)}">'
        f'<input type="hidden" name="action" value="{_e(action)}">'
        f'<button class="btn {cls}" type="submit">{_e(label)}</button></form>'
    )


def _item_actions(i: dict, token: str) -> str:
    """De knoppen voor één inbox-item. Alleen pending items krijgen acties; alleen de
    veilige, niet-interactieve acties zitten in deze stap (keyword-beslissing, defer,
    confirm). De rijkere rails (project/governance/rol-vragen) komen in een volgende stap."""
    if i.get("status") != "pending":
        return '<span class="muted">—</span>'
    iid = i.get("id")
    parts = []
    if i.get("type") == "keyword":
        parts.append(_btn(iid, "approve", "Approve", token, "ok"))
        parts.append(_btn(iid, "reject", "Reject", token, "no"))
    if i.get("proposed_resolution"):
        parts.append(_btn(iid, "confirm", "Confirm", token, "ok"))
    parts.append(_btn(iid, "defer", "Defer", token))
    parts.append(f'<a class="btn" href="/process?iid={_e(iid)}">Process…</a>')
    return " ".join(parts)


def render_process(item: dict, roster: list, csrf_token: str) -> str:
    """De GlassFrog 'Process Tension'-flow voor één spanning. Live rails: Add Reference
    (info vastleggen), Add Project (uitkomst voor een rol) en Niets-nodig/Defer. De
    overige rails (governance, rol-vragen) volgen als structuur."""
    iid = item["id"]
    ctx = item.get("context", {}) or {}
    detail = (ctx.get("description") or ctx.get("reason") or ctx.get("purpose")
              or ctx.get("tension") or "")
    t = csrf_token

    # Rails laten de spanning OPEN (één spanning kan meerdere uitkomsten hebben) en
    # keren terug naar deze pagina; sluiten is de aparte Done/Defer-stap (→ home).
    stay = f"/process?iid={iid}"

    def _hidden(action: str, next_url: str = "/") -> str:
        return (f'<input type="hidden" name="csrf" value="{_e(t)}">'
                f'<input type="hidden" name="iid" value="{_e(iid)}">'
                f'<input type="hidden" name="action" value="{action}">'
                f'<input type="hidden" name="next" value="{_e(next_url)}">')

    ref_form = (
        '<form method="post" action="/action" class="pf">'
        + _hidden("add_reference", stay)
        + '<label>Claim (Engels, één feit):</label>'
        f'<input name="claim" value="{_e(detail[:140])}">'
        + '<label>Grounds (het bewijs of de redenering erachter):</label>'
        '<input name="grounds" placeholder="Grounded in: …">'
        + '<button class="btn ok" type="submit">Add Reference</button>'
        '</form>'
    )

    owner_opts = "".join(
        f'<option value="{_e(r["id"])}">{_e(r["id"])}</option>'
        for r in roster if not r.get("archived"))
    proj_form = (
        '<form method="post" action="/action" class="pf">'
        + _hidden("add_project", stay)
        + '<label>Owner (welke rol pakt de uitkomst op):</label>'
        f'<select name="owner">{owner_opts}</select>'
        + '<label>Scope / uitkomst:</label>'
        f'<input name="scope" value="{_e(detail[:140])}">'
        + '<button class="btn ok" type="submit">Add Project</button>'
        '</form>'
    )

    done_form = (
        '<form method="post" action="/action" style="display:inline">'
        + _hidden("done", "/")
        + '<button class="btn" type="submit">Klaar — sluit deze spanning</button></form>'
        ' '
        '<form method="post" action="/action" style="display:inline">'
        + _hidden("defer", "/")
        + '<button class="btn" type="submit">Defer (later)</button></form>'
    )

    soon = '<span class="muted">(volgende stap)</span>'

    inner = f"""
<p><a href="/">← terug naar de cockpit</a></p>
<h1>Process Tension</h1>
<div class="tension"><b>{_e(item.get('subject'))}</b> <span class="muted">({_e(item.get('type'))})</span><br>{_e(detail)}</div>
<h2>Wat heb je nodig?</h2>

<details open><summary>Ik wil info delen, ophalen of vastleggen</summary>
<p class="muted">Leg een feit vast als kennis-kaart (Engels, één claim, met grounds). Loopt door de curator-poort.</p>
{ref_form}
</details>

<details><summary>Ik wil zelf iets doen</summary>
<p class="muted">Maak er een project van (een uitkomst die een rol nastreeft). Bring to Governance (rol/skill wijzigen) {soon}.</p>
{proj_form}
</details>

<details><summary>Ik wil dat iemand anders iets doet</summary>
<p>Een rol vragen een accountability op te pakken (regel 5) {soon} · Bring to Governance {soon}</p>
</details>

<details><summary>Klaar of niets nodig</summary>
<p class="muted">Eén spanning kan meerdere uitkomsten opleveren. Voeg hierboven toe wat nodig is en sluit 'm hier pas als je klaar bent.</p>
<p>{done_form}</p>
</details>
"""
    return _page(f"Process Tension — {item.get('subject')}", inner)


def render_html(snap: dict, csrf_token: str | None = None) -> str:
    roster = snap["roster"]
    inbox = snap["inbox"]
    projects = snap["projects"]
    writable = csrf_token is not None

    # Roster
    rrows = []
    for r in roster:
        cls = "archived" if r["archived"] else ""
        rrows.append(
            f'<tr class="{cls}">'
            f'<td><b>{_e(r["id"])}</b> <span class="muted">v{_e(r["version"])}</span></td>'
            f'<td>{_e(r["type"])}</td>'
            f'<td>{_e(_SOURCE_MARK.get(r["source"], r["source"]))}</td>'
            f'<td>{_e(r["purpose"])}</td>'
            f'<td>{_chips(r["accountabilities"])}</td>'
            f'<td>{_chips(r["domains"])}</td>'
            f'<td>{_chips(r["skills"])}</td>'
            f"</tr>"
        )
    roster_tbl = (
        '<table><thead><tr><th>rol</th><th>type</th><th>source</th><th>purpose</th>'
        '<th>accountabilities</th><th>domeinen</th><th>skills</th></tr></thead>'
        f'<tbody>{"".join(rrows) or "<tr><td colspan=7 class=muted>geen records</td></tr>"}</tbody></table>'
    )

    # Inbox
    irows = []
    for i in inbox:
        ctx = i.get("context", {}) or {}
        detail = ctx.get("description") or ctx.get("purpose") or ctx.get("tension") \
            or ctx.get("reason") or ""
        actions = _item_actions(i, csrf_token) if writable else '<span class="muted">—</span>'
        irows.append(
            f'<tr class="st-{_e(i.get("status"))}">'
            f'<td>{_e(i.get("type"))}</td>'
            f'<td><b>{_e(i.get("subject"))}</b></td>'
            f'<td>{_e(i.get("status"))}</td>'
            f'<td>{_e(detail)}</td>'
            f'<td class="muted">{_e(_ts(i.get("created_at")))}</td>'
            f'<td>{actions}</td>'
            f"</tr>"
        )
    inbox_tbl = (
        '<table><thead><tr><th>type</th><th>subject</th><th>status</th>'
        '<th>detail</th><th>aangemaakt</th><th>acties</th></tr></thead>'
        f'<tbody>{"".join(irows) or "<tr><td colspan=6 class=muted>inbox leeg</td></tr>"}</tbody></table>'
    )

    # Projecten
    prows = []
    for p in projects:
        prows.append(
            f'<tr class="st-{_e(p.get("status"))}">'
            f'<td><b>{_e(p.get("owner"))}</b></td>'
            f'<td>{_e(p.get("scope"))}</td>'
            f'<td>{_e(p.get("trigger"))}</td>'
            f'<td>{_e(p.get("status"))}</td>'
            f'<td>{_e(p.get("blocked_on") or "—")}</td>'
            f'<td class="muted">{_e(_ts(p.get("updated_at")))}</td>'
            f"</tr>"
        )
    proj_tbl = (
        '<table><thead><tr><th>owner</th><th>scope</th><th>trigger</th>'
        '<th>status</th><th>blocked_on</th><th>bijgewerkt</th></tr></thead>'
        f'<tbody>{"".join(prows) or "<tr><td colspan=6 class=muted>geen projecten</td></tr>"}</tbody></table>'
    )

    counts = (
        f'{len(roster)} rollen · {sum(1 for i in inbox if i.get("status") == "pending")} '
        f'open inbox-items · {sum(1 for p in projects if p.get("status") != "done")} open projecten'
    )

    if writable:
        badge = '<span class="badge rw">verwerk-modus</span>'
        note = ("Beslissingen lopen via het gevalideerde inbox-pad (zelfde als de CLI), "
                "altijd door de gate. Lokaal oppervlak, CSRF-beveiligd.")
    else:
        badge = '<span class="badge ro">read-only</span>'
        note = ("Read-only zicht. Muteren loopt via de CLI/inbox en altijd door de gate. "
                "Ververs met F5.")

    inner = (
        f'<h1>NoochVille cockpit {badge}</h1>'
        f'<div class="bar">{_e(counts)} · gegenereerd {_e(_ts(snap.get("generated_at")))}<br>{note}</div>'
        f'<h2>Roster</h2>{roster_tbl}'
        f'<h2>Inbox</h2>{inbox_tbl}'
        f'<h2>Proces (projecten)</h2>{proj_tbl}'
    )
    return _page("NoochVille cockpit", inner)


# ── server (read-only, localhost) ────────────────────────────────────────────

def _dispatch_action(data_dir: str | None, action: str, iid: str, reason: str,
                     extra: dict | None = None) -> dict:
    """Voer één inbox-actie uit via het gedeelde, gevalideerde pad. Geen directe
    store-write buiten inbox_actions. Onbekende actie → fout (geen stille no-op)."""
    extra = extra or {}
    dd = data_dir or _default_data_dir()
    inbox = HumanInbox(os.path.join(dd, "human_inbox.json"))
    if action in ("approve", "reject"):
        library = Library(os.path.join(dd, "library.json"))
        return decide_keyword(inbox, library, iid, action, reason=reason)
    if action == "defer":
        return defer_item(inbox, iid, reason=reason)
    if action == "confirm":
        return confirm_item(inbox, iid)
    if action == "done":
        return mark_done(inbox, iid, reason=reason)
    if action == "add_reference":
        notes = NotesStore(os.path.join(dd, "notes.json"))
        return add_reference(notes, claim=extra.get("claim", ""),
                             grounds=extra.get("grounds", ""))
    if action == "add_project":
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        return route_to_project(projects, owner=extra.get("owner", ""),
                                scope=extra.get("scope", ""))
    return {"ok": False, "error": f"onbekende actie '{action}'"}


def make_handler(data_dir: str | None):
    csrf_token = secrets.token_urlsafe(16)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/process":
                qs = urllib.parse.parse_qs(query)
                iid = (qs.get("iid") or [""])[0]
                snap = gather(data_dir)
                item = next((i for i in snap["inbox"] if i.get("id") == iid), None)
                if item is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Item niet gevonden")
                    return
                body = render_process(item, snap["roster"], csrf_token).encode("utf-8")
            elif path in ("/", "/index.html"):
                body = render_html(gather(data_dir), csrf_token=csrf_token).encode("utf-8")
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/action":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            form = urllib.parse.parse_qs(raw)
            token = (form.get("csrf") or [""])[0]
            # CSRF: een cross-origin pagina kan de token niet lezen, dus niet vervalsen.
            if not secrets.compare_digest(token, csrf_token):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"CSRF-token ongeldig")
                return
            action = (form.get("action") or [""])[0]
            iid = (form.get("iid") or [""])[0]
            reason = (form.get("reason") or [""])[0]
            extra = {"claim": (form.get("claim") or [""])[0],
                     "grounds": (form.get("grounds") or [""])[0],
                     "owner": (form.get("owner") or [""])[0],
                     "scope": (form.get("scope") or [""])[0]}
            _dispatch_action(data_dir, action, iid, reason, extra=extra)
            # 303 → verse GET. Rails keren terug naar de spanning (next), sluiten gaat home.
            nxt = (form.get("next") or ["/"])[0]
            if not nxt.startswith("/"):
                nxt = "/"
            self.send_response(303)
            self.send_header("Location", nxt)
            self.end_headers()

        def log_message(self, *_):  # stil
            pass

    return _Handler


def serve(host: str = "127.0.0.1", port: int = 8765,
          data_dir: str | None = None) -> None:
    if host not in _LOCAL_HOSTS:
        raise SystemExit(
            f"Cockpit weigert niet-lokale host '{host}'. Read-only blijft op localhost."
        )
    httpd = HTTPServer((host, port), make_handler(data_dir))
    print(f"Cockpit (verwerk-modus, lokaal) op http://{host}:{port}  —  Ctrl-C om te stoppen")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCockpit gestopt.")
    finally:
        httpd.server_close()


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="nooch_village.cockpit")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args(argv)
    serve(args.host, args.port, args.data_dir)


if __name__ == "__main__":
    main()
