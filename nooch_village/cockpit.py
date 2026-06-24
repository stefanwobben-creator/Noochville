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
from nooch_village.inbox_actions import decide_keyword, defer_item, confirm_item

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
    return " ".join(parts)


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

def _dispatch_action(data_dir: str | None, action: str, iid: str, reason: str) -> dict:
    """Voer één inbox-actie uit via het gedeelde, gevalideerde pad. Geen directe
    store-write buiten inbox_actions. Onbekende actie → fout (geen stille no-op)."""
    dd = data_dir or _default_data_dir()
    inbox = HumanInbox(os.path.join(dd, "human_inbox.json"))
    if action in ("approve", "reject"):
        library = Library(os.path.join(dd, "library.json"))
        return decide_keyword(inbox, library, iid, action, reason=reason)
    if action == "defer":
        return defer_item(inbox, iid, reason=reason)
    if action == "confirm":
        return confirm_item(inbox, iid)
    return {"ok": False, "error": f"onbekende actie '{action}'"}


def make_handler(data_dir: str | None):
    csrf_token = secrets.token_urlsafe(16)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] not in ("/", "/index.html"):
                self.send_response(404)
                self.end_headers()
                return
            body = render_html(gather(data_dir), csrf_token=csrf_token).encode("utf-8")
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
            _dispatch_action(data_dir, action, iid, reason)
            # 303 → de browser doet een verse GET, zo zie je meteen de nieuwe staat.
            self.send_response(303)
            self.send_header("Location", "/")
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
