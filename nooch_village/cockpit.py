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

    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Process Tension — {_e(item.get('subject'))}</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:1.5rem;max-width:760px;color:#1a1a1a}}
 a{{color:#36c}} .muted{{color:#999}}
 .tension{{background:#eef4fb;border-radius:6px;padding:.6rem .8rem;margin:.6rem 0 1.2rem}}
 details{{border:1px solid #e0e0e0;border-radius:6px;margin:.5rem 0;padding:.3rem .7rem}}
 details>summary{{cursor:pointer;font-weight:600;padding:.3rem 0}}
 .pf label{{display:block;margin:.5rem 0 .15rem;font-size:13px;color:#444}}
 .pf input{{width:100%;padding:.35rem;box-sizing:border-box}}
 .btn{{font:13px system-ui;border:1px solid #bbb;border-radius:4px;background:#f7f7f7;
   padding:.25rem .7rem;margin:.5rem .1rem 0;cursor:pointer;display:inline-block;text-decoration:none;color:#222}}
 .btn.ok{{border-color:#3a7;background:#eafaef}}
</style></head><body>
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
</body></html>"""


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
        _mode_badge = ' <span class="ro" style="color:#3a7">verwerk-modus</span>'
        _mode_note = ("Beslissingen lopen via het gevalideerde inbox-pad (zelfde als de CLI), "
                      "altijd door de gate. Lokaal oppervlak, CSRF-beveiligd.")
    else:
        _mode_badge = ' <span class="ro">read-only</span>'
        _mode_note = "Read-only zicht. Muteren loopt via de CLI/inbox en altijd door de gate. Ververs met F5."

    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NoochVille cockpit (read-only)</title>
<style>
 body{{font:14px/1.45 system-ui,sans-serif;margin:1.5rem;color:#1a1a1a}}
 h1{{font-size:1.1rem;margin:0}} h2{{font-size:.95rem;margin:1.6rem 0 .4rem}}
 .bar{{color:#555;margin:.2rem 0 1rem}} .ro{{color:#a00;font-weight:600}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th,td{{border:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}}
 th{{background:#f4f4f4}} tr.archived td{{opacity:.45}}
 .chip{{display:inline-block;background:#eef;border-radius:3px;padding:.05rem .35rem;margin:.05rem;font-size:12px}}
 .muted{{color:#999}}
 tr.st-pending td{{background:#fff7e6}} tr.st-blocked td{{background:#fdeaea}}
 tr.st-running td{{background:#eaf6ec}}
 .btn{{font:12px system-ui;border:1px solid #bbb;border-radius:4px;background:#f7f7f7;
   padding:.15rem .5rem;margin:.05rem;cursor:pointer}}
 .btn.ok{{border-color:#3a7;background:#eafaef}} .btn.no{{border-color:#c55;background:#fdeeee}}
</style></head><body>
<h1>NoochVille cockpit{_mode_badge}</h1>
<div class="bar">{_e(counts)} · gegenereerd {_e(_ts(snap.get("generated_at")))} · {_e(snap.get("data_dir"))}<br>
{_mode_note}</div>
<h2>Roster (records)</h2>{roster_tbl}
<h2>Inbox</h2>{inbox_tbl}
<h2>Proces (projecten)</h2>{proj_tbl}
</body></html>"""


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
