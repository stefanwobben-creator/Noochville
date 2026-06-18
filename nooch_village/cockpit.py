"""Cockpit — read-only zicht op het draaiende dorp.

Drie stores, één pagina: records (roster), human_inbox, projects (proces).
GEEN schrijfpad. Bindt uitsluitend op 127.0.0.1. Dit is de mens-kant van de
auth-grens; muteren blijft op de CLI/inbox en altijd via de gate.
Zie docs/ONTWERP_cockpit_rol_skill_werkbank.md.

Draaien:
    python -m nooch_village.cockpit                 # http://127.0.0.1:8765
    python -m nooch_village.cockpit --port 9000
"""
from __future__ import annotations

import os
import html
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from nooch_village.governance import Records
from nooch_village.human_inbox import HumanInbox
from nooch_village.projects import ProjectLedger

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


def render_html(snap: dict) -> str:
    roster = snap["roster"]
    inbox = snap["inbox"]
    projects = snap["projects"]

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
        detail = ctx.get("description") or ctx.get("purpose") or ctx.get("tension") or ""
        irows.append(
            f'<tr class="st-{_e(i.get("status"))}">'
            f'<td>{_e(i.get("type"))}</td>'
            f'<td><b>{_e(i.get("subject"))}</b></td>'
            f'<td>{_e(i.get("status"))}</td>'
            f'<td>{_e(detail)}</td>'
            f'<td class="muted">{_e(_ts(i.get("created_at")))}</td>'
            f"</tr>"
        )
    inbox_tbl = (
        '<table><thead><tr><th>type</th><th>subject</th><th>status</th>'
        '<th>detail</th><th>aangemaakt</th></tr></thead>'
        f'<tbody>{"".join(irows) or "<tr><td colspan=5 class=muted>inbox leeg</td></tr>"}</tbody></table>'
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
</style></head><body>
<h1>NoochVille cockpit <span class="ro">read-only</span></h1>
<div class="bar">{_e(counts)} · gegenereerd {_e(_ts(snap.get("generated_at")))} · {_e(snap.get("data_dir"))}<br>
Read-only zicht. Muteren loopt via de CLI/inbox en altijd door de gate. Ververs met F5.</div>
<h2>Roster (records)</h2>{roster_tbl}
<h2>Inbox</h2>{inbox_tbl}
<h2>Proces (projecten)</h2>{proj_tbl}
</body></html>"""


# ── server (read-only, localhost) ────────────────────────────────────────────

def make_handler(data_dir: str | None):
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] not in ("/", "/index.html"):
                self.send_response(404)
                self.end_headers()
                return
            body = render_html(gather(data_dir)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # geen schrijfpad — expliciet dicht
            self.send_response(405)
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
    print(f"Cockpit (read-only) op http://{host}:{port}  —  Ctrl-C om te stoppen")
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
