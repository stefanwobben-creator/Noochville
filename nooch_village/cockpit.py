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
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

from nooch_village.governance import Records
from nooch_village.human_inbox import HumanInbox
from nooch_village.projects import ProjectLedger
from nooch_village.library import Library, classify_function
from nooch_village.trend_analysis import trend_state_label
from nooch_village.notes_store import NotesStore
from nooch_village.inbox_actions import (
    decide_keyword, defer_item, confirm_item, mark_done, resolve_tension, add_reference,
    route_to_project, route_to_governance, remove_note, override_library_term,
    decide_competitor_candidate, decide_link_target, set_word_function, decide_opportunity,
    decide_target)
from nooch_village.competitor_brands import CompetitorBrands
from nooch_village.link_targets import LinkTargets

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _default_data_dir() -> str:
    # nooch_village/cockpit.py -> project root is één niveau omhoog
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def _config_competitor_brands(dd: str) -> list[str]:
    """De vaste concurrent-set uit config/settings.ini ([DEFAULT] competitor_brands), naast data/.
    Zelfde bron die de scout gebruikt, zodat 'Gemonitord' de echte monitor-set toont (config + bevestigd)."""
    import configparser
    path = os.path.join(dd, "..", "config", "settings.ini")
    try:
        cp = configparser.ConfigParser()
        cp.read(path)
        raw = cp["DEFAULT"].get("competitor_brands", "")
    except Exception:
        return []
    return [b.strip() for b in raw.split(",") if b.strip()]


def _north_star(dd: str) -> dict:
    """De noordster uit config/strategy.json (naast data/). Leeg bij ontbreken."""
    import json as _json
    path = os.path.join(dd, "..", "config", "strategy.json")
    try:
        return (_json.load(open(path)) or {}).get("north_star", {}) or {}
    except Exception:
        return {}


def _monitored_brands(config_brands: list[str], confirmed: list[str]) -> list[str]:
    """Volledige monitor-set, dedup met behoud van volgorde (config eerst, dan bevestigd).
    Spiegelt ConcurrentScout._monitored_brands."""
    return list(dict.fromkeys(list(config_brands) + list(confirmed)))


_PRIO_ORDER = {"hoog": 0, "midden": 1, "laag": 2, "onbekend": 3}


def _within(date_str: str | None, now: float, days: int = 7) -> bool:
    """True als een 'YYYY-MM-DD'-datum binnen de afgelopen `days` dagen valt (incl. vandaag)."""
    if not date_str:
        return False
    try:
        t = time.mktime(time.strptime(str(date_str)[:10], "%Y-%m-%d"))
    except Exception:
        return False
    return 0 <= (now - t) <= (days + 1) * 86400


def compute_digest(library_all: dict, link_cands: list, comp_cands: list,
                   comp_monitored: list, now: float, days: int = 7) -> dict:
    """Pure weekrapport-berekening over een venster van `days` dagen. Geen I/O.

    Vat samen wat er nieuw is: goedgekeurde woorden (met vraag-signaal), linkbuilding-
    doelwitten (op prioriteit) en marktinteresse (nieuw gespotte + de volledige monitor-set:
    de vaste config-concurrenten + de door jou bevestigde kandidaten).
    """
    def _word_row(w, e):
        ev = e.get("evidence") or {}
        fn = e.get("function")
        if fn not in ("volg", "doelwit"):
            fn = classify_function(w, ev)
        return {"word": w,
                "function": fn,
                "volume": ev.get("volume"),
                "competition": ev.get("competition"),
                "opportunity": ev.get("opportunity"),
                "gsc_seen": ev.get("gsc_seen"),
                "gsc_position": ev.get("gsc_position"),
                "gsc_clicks": ev.get("gsc_clicks"),
                "gsc_impressions": ev.get("gsc_impressions"),
                "interest": ev.get("interest"),
                "locale": e.get("locale") or "",
                "date": e.get("date", "")}
    fresh = [_word_row(w, e) for w, e in (library_all or {}).items()
             if isinstance(e, dict) and e.get("status") == "approved"
             and _within(e.get("date"), now, days)]
    # Doelwit-woorden: op kans (waar we op willen ranken). Volg-woorden: op volume (seeds).
    new_targets = sorted(
        (x for x in fresh if x["function"] == "doelwit"),
        key=lambda x: (-((x["opportunity"] if x["opportunity"] is not None else -1)),
                       -((x["volume"] or 0)), -((x["interest"] or 0)), x["word"]))
    new_seeds = sorted(
        (x for x in fresh if x["function"] == "volg"),
        key=lambda x: (-((x["volume"] or 0)), x["word"]))
    new_links = sorted(
        ({"title": t.get("title", ""), "source": t.get("source", ""),
          "priority": t.get("priority", "onbekend"), "link": t.get("link", "")}
         for t in (link_cands or []) if _within(t.get("first_seen"), now, days)),
        key=lambda x: (_PRIO_ORDER.get(x["priority"], 9), x["title"]),
    )
    new_competitors = [c.get("brand") for c in (comp_cands or [])
                       if _within(c.get("first_seen"), now, days)]
    return {
        "window_days": days,
        "new_targets": new_targets,
        "new_seeds": new_seeds,
        "new_links": new_links,
        "new_competitors": new_competitors,
        "monitored_competitors": list(comp_monitored or []),
    }


def gather(data_dir: str | None = None) -> dict:
    """Lees de drie stores read-only. Pure functie: geen Village, geen netwerk.

    Ontbrekende bestanden leveren lege lijsten (fail-safe, niet fail-hard).
    """
    dd = data_dir or _default_data_dir()
    records = Records(os.path.join(dd, "governance_records.json"))
    inbox = HumanInbox(os.path.join(dd, "human_inbox.json"))
    projects = ProjectLedger(os.path.join(dd, "projects.json"))
    library = Library(os.path.join(dd, "library.json"))
    notes = NotesStore(os.path.join(dd, "notes.json"))
    brands = CompetitorBrands(os.path.join(dd, "competitor_brands.json"))
    links = LinkTargets(os.path.join(dd, "linkbuilding_targets.json"))
    from nooch_village.competitor_news_store import CompetitorNews
    comp_news = CompetitorNews(os.path.join(dd, "competitor_news.json")).all()
    noochie_daily = {}
    _nd_path = os.path.join(dd, "noochie_daily.json")
    if os.path.exists(_nd_path):
        try:
            import json as _json
            noochie_daily = _json.load(open(_nd_path))
        except Exception:
            noochie_daily = {}

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

    # Seed-oplevingen (door enrich gesignaleerd, door de scout geduid): term → verklaring.
    _surges = {}
    _surge_path = os.path.join(dd, "seed_surges.json")
    if os.path.exists(_surge_path):
        try:
            import json as _json
            _surges = _json.load(open(_surge_path))
        except Exception:
            _surges = {}

    # Per (seed-)woord het sterkste duiding-kaartje van Harry (academische grounding op de term).
    _duiding: dict = {}
    for _n in notes.all():
        _wn = (_n.word or "").lower()
        if _wn and (_wn not in _duiding or _n.grounding_count > _duiding[_wn]["gc"]):
            _duiding[_wn] = {"id": _n.id, "claim": _n.claim, "gc": _n.grounding_count}

    # Woordenschat: woord + status (approved/forbidden/avoid/escalated), beslist eerst.
    _ws_order = {"approved": 0, "escalated": 1, "avoid": 2, "forbidden": 3}

    def _lib_row(w, e):
        ev = e.get("evidence") or {}
        surge = _surges.get(w) or {}
        fn = e.get("function") if e.get("function") in ("volg", "doelwit") \
            else classify_function(w, ev)
        return {"word": w, "status": e.get("status", "?"), "by": e.get("by", ""),
                "rationale": e.get("rationale", ""), "date": e.get("date", ""),
                "function": fn,
                "volume": ev.get("volume"), "opportunity": ev.get("opportunity"),
                "competition": ev.get("competition"), "trend_pct": ev.get("trend_pct"),
                "trend_state": ev.get("trend_state"), "trend_series": ev.get("trend_series"),
                "recent_surge": ev.get("recent_surge"),
                "recent_move": ev.get("recent_move"),
                "surge_explanation": surge.get("explanation"),
                "duiding": _duiding.get(w.lower()),
                "gsc_seen": ev.get("gsc_seen"), "gsc_position": ev.get("gsc_position"),
                "gsc_clicks": ev.get("gsc_clicks")}
    lib = sorted((_lib_row(w, e) for w, e in (library.all() or {}).items()),
                 key=lambda x: (_ws_order.get(x["status"], 9), x["word"]))

    # Inzichten: claim + status + hoe vaak gegrond (geëmergeerd eerst). Synthese-kaartjes
    # (creatieve links tussen kaartjes) zijn herkenbaar via de tag en hun ouders.
    insights = sorted(
        ({"id": n.id, "claim": n.claim, "status": str(getattr(n.status, "value", n.status)),
          "grounding_count": n.grounding_count, "word": n.word or "",
          "synthese": ("synthese" in (n.tags or [])), "links": len(n.links_to or [])}
         for n in notes.all()),
        key=lambda x: (-int(x["synthese"]), -x["grounding_count"]),
    )
    from nooch_village.card_synthesis import graph_density
    graph = graph_density([{"id": n.id, "text": (n.claim or "") + " " + (n.grounds or ""),
                            "links_to": list(n.links_to or [])} for n in notes.all()])

    # Kansen-backlog: alle onderbouwde voorstellen/projecten (met business-case), op waarde.
    from nooch_village.business_case import business_value
    backlog = []
    for it in inbox_items:
        if it.get("status") != "pending":
            continue
        ctx = it.get("context") or {}
        if it.get("type") == "opportunity":            # kans → wacht op jouw akkoord
            bc = ctx.get("business_case")
            backlog.append({
                "title": ctx.get("title") or it.get("subject"), "kind": "kans",
                "by": ctx.get("by", ""),
                "wat": ctx.get("wat", "") or ctx.get("hypothesis", ""),  # back-compat
                "waarom": ctx.get("waarom", ""),
                "business_case": bc, "value": business_value(bc),
                "iid": it.get("id"), "approvable": True})
            continue
        prop = ctx.get("proposal") or {}
        bc = prop.get("business_case") or ctx.get("business_case")
        if bc:
            backlog.append({
                "title": it.get("subject") or prop.get("proposer_role") or "voorstel",
                "kind": "voorstel", "by": prop.get("proposer_role", ""),
                "hypothesis": prop.get("hypothesis", "") or ctx.get("hypothesis", ""),
                "business_case": bc, "value": business_value(bc)})
    for p in proj:
        bc = p.get("business_case")
        if bc and p.get("status") not in ("future", "done"):   # geparkeerd/klaar telt niet mee
            backlog.append({"title": p.get("scope") or p.get("owner") or p.get("id"),
                            "kind": "project (loopt)", "by": p.get("owner", ""),
                            "hypothesis": p.get("hypothesis", ""),
                            "business_case": bc, "value": business_value(bc)})
    backlog.sort(key=lambda x: -x["value"])

    _now = time.time()
    return {
        "roster": roster,
        "inbox": inbox_items,
        "projects": proj,
        "backlog": backlog,
        "north_star": _north_star(dd),
        "library": lib,
        "insights": insights,
        "knowledge_graph": graph,
        "competitor_candidates": brands.candidates(),
        "competitor_confirmed": brands.confirmed(),
        "competitor_news": comp_news,
        "noochie_daily": noochie_daily,
        "link_candidates": links.candidates(),
        "link_pursued": links.pursued(),
        "competitor_config": _config_competitor_brands(dd),
        "digest": compute_digest(
            library.all() or {}, links.candidates(), brands.candidates(),
            _monitored_brands(_config_competitor_brands(dd), brands.confirmed()), _now),
        "generated_at": _now,
        "data_dir": dd,
    }


# ── render (puur, geen I/O) ──────────────────────────────────────────────────

_SOURCE_MARK = {"sensed": "✱ sensed", "demo": "⚙ demo", "seed": "seed"}


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _fmt_int(v) -> str:
    """Heel getal met punt-duizendtallen (NL): 1220000 → 1.220.000."""
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return _e(v)


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
tr.st-future td{opacity:.55}
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
.flash{background:var(--green-tint);border:1px solid var(--green);color:var(--green-dark);
 border-radius:var(--radius);padding:.5rem .8rem;margin:.4rem 0 1rem;font-weight:600}
.flash.err{background:#FDEAEA;border-color:var(--coral);color:#A8322A}
"""


def _banner(msg) -> str:
    if not msg:
        return ""
    cls = "flash err" if str(msg).lstrip().startswith("✗") else "flash"
    return f'<div class="{cls}">{_e(msg)}</div>'


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


def _lib_btn(word: str, decision: str, label: str, token: str, cls: str = "") -> str:
    """Override-knop voor een bibliotheekterm (escalated afromen): POST /action lib_override."""
    return _word_btn("lib_override", word, decision, label, token, cls)


def _func_btn(word: str, function: str, label: str, token: str, cls: str = "") -> str:
    """Flip-knop voor de functie van een woord (volg↔doelwit): POST /action lib_function."""
    return _word_btn("lib_function", word, function, label, token, cls)


def _brand_btn(brand: str, decision: str, label: str, token: str, cls: str = "") -> str:
    """Bevestig/negeer-knop voor een gespotte concurrent: POST /action brand_decide."""
    return _word_btn("brand_decide", brand, decision, label, token, cls)


def _link_btn(link: str, decision: str, label: str, token: str, cls: str = "") -> str:
    """Pitchen/negeer-knop voor een linkbuilding-doelwit: POST /action link_decide."""
    return _word_btn("link_decide", link, decision, label, token, cls)


def _word_btn(action: str, word: str, decision: str, label: str, token: str, cls: str = "") -> str:
    return (
        f'<form method="post" action="/action" style="display:inline">'
        f'<input type="hidden" name="csrf" value="{_e(token)}">'
        f'<input type="hidden" name="action" value="{_e(action)}">'
        f'<input type="hidden" name="word" value="{_e(word)}">'
        f'<input type="hidden" name="decision" value="{_e(decision)}">'
        f'<button class="btn {cls}" type="submit">{_e(label)}</button></form>'
    )


_TYPE_LABELS = {
    "means_gap": "Middelen-gat", "keyword": "Zoekwoord",
    "escalation": "Governance-voorstel", "suggestion": "Suggestie",
    "activation": "Rol-activatie", "verband": "Verband",
    "content_suggestion": "Content-kans", "content_draft": "Content-draft",
    "keyword_batch": "Keyword-batch", "voorstel": "Voorstel van Noochie",
}


def _type_label(t: str) -> str:
    return _TYPE_LABELS.get(t, t or "?")


def _item_title(i: dict) -> str:
    """De menselijke titel van een spanning: de echte zin, niet de machine-slug."""
    ctx = i.get("context", {}) or {}
    t = i.get("type")
    if t in ("means_gap", "suggestion"):
        return ctx.get("description") or i.get("subject")
    if t == "voorstel":
        return ctx.get("voorstel") or i.get("subject")
    if t == "keyword":
        return ctx.get("word") or i.get("subject")
    if t == "escalation":
        return ctx.get("tension") or i.get("subject")
    if t == "activation":
        return ctx.get("purpose") or i.get("subject")
    return i.get("subject")


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


def _tension_meta(item: dict) -> str:
    """Gestructureerde kop per spanning: wie senste het, wat is de spanning, en (waar
    aanwezig) welk concreet voorstel. Per type uit de juiste context-velden."""
    ctx = item.get("context", {}) or {}
    t = item.get("type")
    rows = []

    def row(label, val):
        if val:
            rows.append(f'<div><span class="muted">{_e(label)}:</span> {_e(val)}</div>')

    if t == "means_gap":
        row("Gesensed door", ctx.get("sensed_by") or "—")
        row("Betreft rol", ctx.get("role_id"))
        row("De spanning", ctx.get("description"))
        rows.append('<div class="muted">Voorstel: een means-gap draagt geen vast voorstel — '
                    'kies hieronder de oplossing (skill, project of vastleggen).</div>')
    elif t == "escalation":
        row("Voorgesteld door", ctx.get("proposer_role"))
        row("De spanning", ctx.get("tension"))
        change = f'{ctx.get("change_kind") or ""} {ctx.get("role_id") or ""}'.strip()
        extra = (ctx.get("add_accountabilities") or []) + (ctx.get("add_domains") or [])
        if extra:
            change += " + " + ", ".join(extra)
        row("Voorgestelde oplossing", change)
        row("Rationale", ctx.get("rationale"))
        if ctx.get("gate"):
            row("Gate", f'{ctx.get("gate")} — {ctx.get("gate_reason", "")}')
    elif t == "voorstel":
        row("Uitgewerkt door", ctx.get("by") or "noochie")
        row("Over spanning", ctx.get("origin"))
        row("Voorstel", ctx.get("voorstel"))
    elif t == "keyword":
        d = ctx.get("demand", {}) or {}
        row("Woord", ctx.get("word"))
        row("Bron / signaal", f'{d.get("source", "?")} / {d.get("signal", "?")}')
        row("Reden (Librarian)", ctx.get("reason"))
    else:
        row("Onderwerp", item.get("subject"))
        row("Detail", ctx.get("description") or ctx.get("reason"))
    return "".join(rows)


def render_process(item: dict, roster: list, csrf_token: str, msg=None) -> str:
    """De GlassFrog 'Process Tension'-flow voor één spanning. Live rails: Add Reference
    (info vastleggen), Add Project (uitkomst voor een rol), Bring to Governance (rol een
    skill geven) en Niets-nodig/Defer. Rol-vragen volgt nog als structuur."""
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

    # Alleen echte rollen als owner/skill-ontvanger; een cirkel delegeert, die doet niks zelf.
    owner_opts = "".join(
        f'<option value="{_e(r["id"])}">{_e(r["id"])}</option>'
        for r in roster if not r.get("archived") and r.get("type") == "role")
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

    gov_form = (
        '<form method="post" action="/action" class="pf">'
        + _hidden("add_governance", stay)
        + '<label>Rol die de skill krijgt:</label>'
        f'<select name="role">{owner_opts}</select>'
        + '<label>Skill (bestaande capability-naam):</label>'
        '<input name="skill" placeholder="bijv. serpapi_trends">'
        + '<label>Reden (min. 10 tekens, gaat door de gate):</label>'
        '<input name="rationale" placeholder="waarom deze rol deze skill krijgt">'
        + '<button class="btn ok" type="submit">Bring to Governance</button>'
        '</form>'
    )

    done_form = (
        '<form method="post" action="/action" style="display:inline">'
        + _hidden("resolve", "/")
        + '<button class="btn ok" type="submit">Klaar — afgehandeld</button></form>'
        ' '
        '<form method="post" action="/action" style="display:inline">'
        + _hidden("done", "/")
        + '<button class="btn" type="submit">Niets nodig / nevermind</button></form>'
        ' '
        '<form method="post" action="/action" style="display:inline">'
        + _hidden("defer", "/")
        + '<button class="btn" type="submit">Defer (later)</button></form>'
    )

    soon = '<span class="muted">(volgende stap)</span>'

    inner = f"""
<p><a href="/">← terug naar de cockpit</a></p>
<h1>Process Tension</h1>
{_banner(msg)}
<div class="tension"><b>{_e(item.get('subject'))}</b> <span class="muted">({_e(_type_label(item.get('type')))})</span>{_tension_meta(item)}</div>
<h2>Wat heb je nodig?</h2>

<details open><summary>Ik wil info delen, ophalen of vastleggen</summary>
<p class="muted">Leg een feit vast als kennis-kaart (Engels, één claim, met grounds). Loopt door de curator-poort.</p>
{ref_form}
</details>

<details><summary>Ik wil zelf iets doen</summary>
<p class="muted">Maak er een project van (een uitkomst die een rol nastreeft), of geef een rol een bestaande skill via governance.</p>
{proj_form}
<hr style="border:none;border-top:1px solid var(--border);margin:1rem 0">
{gov_form}
</details>

<details><summary>Ik wil dat iemand anders iets doet</summary>
<p class="muted">Laat Noochie (de brug naar The Source, met LLM) deze spanning uitwerken tot
een concreet voorstel dat jij daarna beoordeelt. Een rol vragen via regel 5 {soon}.</p>
<form method="post" action="/action" style="display:inline">{_hidden("delegate_noochie", stay)}
<button class="btn ok" type="submit">Laat Noochie dit uitwerken</button></form>
</details>

<details><summary>Klaar of niets nodig</summary>
<p class="muted">Eén spanning kan meerdere uitkomsten opleveren. Voeg hierboven toe wat nodig is en sluit 'm hier pas als je klaar bent.</p>
<p>{done_form}</p>
</details>
"""
    return _page(f"Process Tension — {item.get('subject')}", inner)


def _proj_actions(p: dict, token: str) -> str:
    """Statusknoppen per project: actief / waiting / toekomst / done. Done is terminal
    (verdwijnt uit de actieve weergave). Alleen niet-terminale projecten krijgen knoppen."""
    if p.get("status") == "done":
        return '<span class="muted">—</span>'
    pid = p.get("id")
    return " ".join([
        _btn(pid, "proj_active", "Actief", token, "ok"),
        _btn(pid, "proj_waiting", "Waiting", token),
        _btn(pid, "proj_future", "Toekomst", token),
        _btn(pid, "proj_done", "Done", token),
        f'<a class="btn" href="/project?pid={_e(pid)}">Edit…</a>',
    ])


def render_card(card: dict, neighbors: list, csrf_token: str) -> str:
    """Detailpagina van één kennis-kaartje: de claim + grounds, en de verbonden kaartjes
    (de kennisgraaf) als doorklikbare links. Plus een verwijder-knop."""
    cid = card["id"]
    nb = "".join(
        f'<li><a href="/card?id={_e(n["id"])}">{_e(n["claim"][:90])}</a> '
        f'<span class="muted">({_e(n["status"])}, {_e(n["grounding_count"])}×)</span></li>'
        for n in neighbors)
    nb_block = (f'<ul>{nb}</ul>' if neighbors
                else '<p class="muted">Nog geen verbonden kaartjes.</p>')
    remove_form = (
        '<form method="post" action="/action" style="display:inline">'
        f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
        f'<input type="hidden" name="iid" value="{_e(cid)}">'
        '<input type="hidden" name="action" value="note_remove">'
        '<input type="hidden" name="next" value="/">'
        '<button class="btn no" type="submit">Verwijder dit kaartje</button></form>'
    )
    inner = (
        '<p><a href="/">← terug naar de cockpit</a></p>'
        '<h1>Kennis-kaartje</h1>'
        f'<div class="tension"><b>{_e(card["claim"])}</b><br>'
        f'<span class="muted">{_e(card["status"])} · {_e(card["grounding_count"])}× gegrond'
        f'{" · " + _e(card["word"]) if card.get("word") else ""}</span></div>'
        f'<h2>Grounds</h2><p>{_e(card.get("grounds") or "—")}</p>'
        f'<h2>Verbonden kaartjes ({len(neighbors)})</h2>{nb_block}'
        f'<p style="margin-top:1.4rem">{remove_form}</p>'
    )
    return _page("Kennis-kaartje", inner)


def render_project_edit(p: dict, roster: list, csrf_token: str) -> str:
    """Kleine editpagina voor een project: owner + scope aanpassen (status apart)."""
    pid = p["id"]
    scope = p.get("scope")
    if isinstance(scope, dict):
        scope = " · ".join(f"{k}: {v}" for k, v in scope.items())
    owner_opts = "".join(
        f'<option value="{_e(r["id"])}"{" selected" if r["id"] == p.get("owner") else ""}>'
        f'{_e(r["id"])}</option>'
        for r in roster if not r.get("archived") and r.get("type") == "role")
    form = (
        '<form method="post" action="/action" class="pf">'
        f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
        f'<input type="hidden" name="iid" value="{_e(pid)}">'
        '<input type="hidden" name="action" value="proj_edit">'
        '<input type="hidden" name="next" value="/">'
        '<label>Owner (rol die het oppakt):</label>'
        f'<select name="owner">{owner_opts}</select>'
        '<label>Scope / uitkomst:</label>'
        f'<input name="scope" value="{_e(scope)}">'
        '<button class="btn ok" type="submit">Opslaan</button></form>'
    )
    inner = (
        '<p><a href="/">← terug naar de cockpit</a></p>'
        '<h1>Project bewerken</h1>'
        f'<div class="tension"><b>{_e(p.get("owner"))}</b> '
        f'<span class="muted">· status {_e(p.get("status"))}</span></div>'
        f'{form}'
    )
    return _page("Project bewerken", inner)


def _word_metrics(x: dict) -> str:
    """Compacte kerncijfers per zoekwoord: zoekvolume · concurrentie · kans · onze GSC-stand.
    Toont alleen wat bekend is; valt terug op trends-interesse en anders een hint om te verrijken."""
    parts = []
    if x.get("volume") is not None:
        parts.append(f'vol {x["volume"]}/mnd')
    if x.get("opportunity") is not None:
        parts.append(f'<b>kans {x["opportunity"]}</b>')
    if x.get("competition") is not None:
        parts.append(f'ad-concurrentie {round(float(x["competition"]) * 100)}%')
    # Onze huidige Google-stand voor exact deze term (uit GSC)
    if x.get("gsc_seen") is True:
        pos = x.get("gsc_position")
        clicks = x.get("gsc_clicks") or 0
        parts.append(f'positie {pos} ({clicks} klikken)')
    elif x.get("gsc_seen") is False:
        parts.append('nog niet in Google top-resultaten')
    if not parts:
        if x.get("interest") is not None:
            parts.append(f'interesse {x["interest"]}')
        else:
            return ('<span class="muted">— nog niet gemeten '
                    '(draai <code>enrich_volumes</code>)</span>')
    sep = ' <span class="muted">·</span> '
    return f'<span class="muted">{sep.join(parts)}</span>'


def _sparkline(values, width: int = 90, height: int = 22) -> str:
    """Mini-lijngrafiek (inline SVG) van een interesse-reeks, zodat je het trend-label
    tegen de echte curve kunt leggen. Lege string bij te weinig data."""
    vals = [float(v) for v in (values or []) if isinstance(v, (int, float))]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = " ".join(
        f"{i / (n - 1) * width:.1f},{height - (v - lo) / rng * height:.1f}"
        for i, v in enumerate(vals))
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'preserveAspectRatio="none" style="vertical-align:middle;margin-right:.3rem">'
            f'<polyline points="{pts}" fill="none" stroke="var(--green-dark)" '
            f'stroke-width="1.5"/></svg>')


def _render_backlog(backlog: list, north_star: dict, token: str | None = None) -> str:
    """Geprioriteerde kansen-backlog: onderbouwde voorstellen/projecten, op verwachte waarde.
    Kansen (door rollen gesensd) wachten op jouw akkoord: goedkeuren → project, negeer → weg."""
    from nooch_village.business_case import format_business_case
    ns = ""
    if north_star.get("target"):
        ns = (f' <span class="muted">— noordster: {_fmt_int(north_star["target"])} '
              f'{_e(north_star.get("unit", ""))} {_e(north_star.get("horizon", ""))}</span>')
    if not backlog:
        body = ('<p class="muted">Nog geen onderbouwde kansen. Zodra rollen voorstellen doen '
                'mét business-case (opportunity-reflex), verschijnen ze hier, op waarde gerangschikt.</p>')
    else:
        _kind_label = {"kans": "📋 project", "voorstel": "🏛️ governance",
                       "project (loopt)": "📋 project (loopt)"}
        def _kans_cell(x):
            kl = _kind_label.get(x["kind"], x["kind"])
            head = (f'<b>{_e(x["title"])}</b> <span class="muted">{kl}'
                    f'{(" · door " + _e(x["by"])) if x.get("by") else ""}</span>')
            wat = f'<div style="margin:.2rem 0">{_e(x.get("wat", ""))}</div>' if x.get("wat") else ""
            waarom = (f'<div class="muted"><b>Waarom:</b> {_e(x["waarom"])}</div>'
                      if x.get("waarom") else "")
            return head + wat + waarom

        def _acts(x):
            if not (x.get("approvable") and token):
                return '<span class="muted">—</span>'
            # één formulier, gedeeld redenveld, twee knoppen (goedkeuren/negeer)
            return (
                f'<form method="post" action="/action">'
                f'<input type="hidden" name="csrf" value="{_e(token)}">'
                f'<input type="hidden" name="iid" value="{_e(x["iid"])}">'
                f'<input type="text" name="reason" placeholder="reden (optioneel, leert de rol)" '
                f'style="width:100%;margin-bottom:.3rem;padding:.25rem .4rem;'
                f'border:1px solid var(--border);border-radius:6px">'
                f'<button class="btn ok" type="submit" name="action" value="opp_approve">✓ goedkeuren</button> '
                f'<button class="btn danger" type="submit" name="action" value="opp_reject">✗ negeer</button>'
                f'</form>')
        rows = "".join(
            f'<tr><td>{_kans_cell(x)}</td>'
            f'<td>{_e(format_business_case(x.get("business_case")))}</td>'
            f'<td><b>{_e(x.get("value"))}</b></td>'
            f'<td style="min-width:220px">{_acts(x)}</td></tr>' for x in backlog)
        body = ('<table><thead><tr><th>kans</th><th>business-case</th><th>waarde</th>'
                '<th>jouw oordeel</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')
    return f'<h2>🎯 Kansen-backlog{ns}</h2>{body}'


def _render_digest(d: dict, noochie: dict | None = None) -> str:
    """Weekrapport: puur kwantitatief — hoeveel nieuw deze week — plus Noochie's dagverdict.
    De details staan in de eigen secties (Woordenschat, Concurrenten, Linkbuilding)."""
    days = d.get("window_days", 7)
    counts = [
        ("🎯", len(d.get("new_targets", [])), "nieuwe doelwit-woorden"),
        ("🌱", len(d.get("new_seeds", [])), "nieuwe volg-woorden (seeds)"),
        ("🔗", len(d.get("new_links", [])), "nieuwe linkbuilding-doelwitten"),
        ("👟", len(d.get("new_competitors", [])), "nieuw gespotte concurrenten"),
    ]
    tiles = "".join(
        f'<div class="kpi"><div class="kpi-n">{ico} {n}</div>'
        f'<div class="kpi-l">{_e(label)}</div></div>'
        for ico, n, label in counts)
    noochie_block = ""
    if noochie and (noochie.get("findings") or noochie.get("question")
                    or noochie.get("suggestion") or noochie.get("oordeel")):
        findings = noochie.get("findings") or []
        vraag = noochie.get("question") or noochie.get("suggestion") or ""   # back-compat
        head = (f'💬 <b>Noochie vandaag</b> '
                f'<span class="muted">({_e(noochie.get("date", ""))})</span>')
        if findings:
            body = '<ul>' + ''.join(f'<li>{_e(f)}</li>' for f in findings) + '</ul>'
        elif noochie.get("oordeel"):
            body = f' {_e(noochie.get("oordeel"))}'        # back-compat: oude losse beoordeling
        else:
            body = ''
        vr = (f'<div>💭 <b>Noochie vraagt:</b> {_e(vraag)}</div>' if vraag else '')
        noochie_block = f'<div class="noochie">{head}{body}{vr}</div>'
    style = ('<style>.kpis{display:flex;flex-wrap:wrap;gap:.7rem;margin:.3rem 0 .6rem}'
             '.kpi{background:var(--surface);border:1px solid var(--border);'
             'border-radius:var(--radius);padding:.6rem .9rem;flex:1 1 150px;min-width:0;'
             'box-shadow:var(--shadow)}'
             '.kpi-n{font-family:var(--font-display);font-weight:800;font-size:1.3rem;'
             'color:var(--green-dark)}.kpi-l{font-size:.78rem;color:var(--gray)}'
             '.noochie{background:var(--cream-3);border:1px solid var(--border);'
             'border-radius:var(--radius);padding:.55rem .9rem;margin:.2rem 0 1rem;font-size:.9rem}'
             '</style>')
    return (f'<h2>📊 Weekrapport — laatste {days} dagen</h2>{style}'
            f'<div class="kpis">{tiles}</div>{noochie_block}')


def render_html(snap: dict, csrf_token: str | None = None, msg=None,
                show_all: bool = False) -> str:
    roster = snap["roster"]
    inbox = snap["inbox"]
    projects = snap["projects"]
    writable = csrf_token is not None

    # Opschonen: standaard alleen actieve dingen. Grijs (gearchiveerd/gesloten/done)
    # verbergen; via 'toon geschiedenis' weer zichtbaar.
    show_roster = roster if show_all else [r for r in roster if not r["archived"]]
    # Kansen (opportunity) tonen we in de Kansen-backlog met volledige uitleg, niet dubbel hier.
    show_inbox = (inbox if show_all
                  else [i for i in inbox if i.get("status") == "pending"
                        and i.get("type") != "opportunity"])
    # done = klaar, future = geparkeerd: allebei uit het actieve zicht.
    _parked = ("done", "future")
    show_proj = projects if show_all else [p for p in projects if p.get("status") not in _parked]

    # Roster (ingeklapt)
    rrows = []
    for r in show_roster:
        cls = "archived" if r["archived"] else ""
        rrows.append(
            f'<tr class="{cls}">'
            f'<td><b>{_e(r["id"])}</b> <span class="muted">v{_e(r["version"])}</span></td>'
            f'<td>{_e(r["type"])}</td>'
            f'<td>{_e(_SOURCE_MARK.get(r["source"], r["source"]))}</td>'
            f'<td>{_e(r["purpose"])}</td>'
            f'<td>{_chips(r["accountabilities"])}</td>'
            f'<td>{_chips(r["skills"])}</td>'
            f"</tr>"
        )
    roster_tbl = (
        '<table><thead><tr><th>rol</th><th>type</th><th>source</th><th>purpose</th>'
        '<th>accountabilities</th><th>skills</th></tr></thead>'
        f'<tbody>{"".join(rrows) or "<tr><td colspan=6 class=muted>geen records</td></tr>"}</tbody></table>'
    )

    # Inbox (alleen actief tenzij geschiedenis) — semantisch: leesbare titel, slug klein
    irows = []
    for i in show_inbox:
        actions = _item_actions(i, csrf_token) if writable else '<span class="muted">—</span>'
        irows.append(
            f'<tr class="st-{_e(i.get("status"))}">'
            f'<td><span class="chip">{_e(_type_label(i.get("type")))}</span></td>'
            f'<td><b>{_e(_item_title(i))}</b><br>'
            f'<span class="muted" style="font-size:11px">{_e(i.get("subject"))}</span></td>'
            f'<td>{_e(i.get("status"))}</td>'
            f'<td>{actions}</td>'
            f"</tr>"
        )
    inbox_tbl = (
        '<table><thead><tr><th>soort</th><th>spanning</th><th>status</th>'
        '<th>acties</th></tr></thead>'
        f'<tbody>{"".join(irows) or "<tr><td colspan=4 class=muted>geen open items 🎉</td></tr>"}</tbody></table>'
    )

    # Projecten (met statusknoppen)
    def _scope(p):
        s = p.get("scope")
        if isinstance(s, dict):                      # oude machine-scope leesbaar maken
            return " · ".join(f"{k}: {v}" for k, v in s.items())
        return s
    prows = []
    for p in show_proj:
        pacts = _proj_actions(p, csrf_token) if writable else '<span class="muted">—</span>'
        prows.append(
            f'<tr class="st-{_e(p.get("status"))}">'
            f'<td><b>{_e(p.get("owner"))}</b></td>'
            f'<td>{_e(_scope(p))}</td>'
            f'<td>{_e(p.get("status"))}</td>'
            f'<td>{_e(p.get("blocked_on") or "—")}</td>'
            f'<td>{pacts}</td>'
            f"</tr>"
        )
    proj_tbl = (
        '<table><thead><tr><th>owner</th><th>scope</th><th>status</th>'
        '<th>wacht op</th><th>acties</th></tr></thead>'
        f'<tbody>{"".join(prows) or "<tr><td colspan=5 class=muted>geen open projecten</td></tr>"}</tbody></table>'
    )

    # Woordenschat (keyword-library): gesplitst in doelwit-woorden (rank: volume/kans/positie)
    # en volg-woorden (seed: 12-mnd trend). Alleen approved; geschiedenis toont alle statussen.
    lib = snap.get("library", [])
    approved_lib = [x for x in lib if x["status"] == "approved"]
    targets = [x for x in approved_lib if x.get("function") == "doelwit"]
    seeds = [x for x in approved_lib if x.get("function") == "volg"]

    def _flip(word, to, label):
        return _func_btn(word, to, label, csrf_token) if writable else ""

    def _pos_cell(x):
        if x.get("gsc_seen") is True:
            return f'positie {_e(x.get("gsc_position"))} ({_e(x.get("gsc_clicks") or 0)} klik)'
        if x.get("gsc_seen") is False:
            return '<span class="muted">nog niet in Google</span>'
        return '<span class="muted">—</span>'

    def _num(v, suffix=""):
        return f'{_fmt_int(v)}{suffix}' if v is not None else '<span class="muted">—</span>'

    def _target_acts(x):
        w = x["word"]
        if not writable:
            return '<span class="muted">—</span>'
        return (
            f'<form method="post" action="/action">'
            f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
            f'<input type="hidden" name="word" value="{_e(w)}">'
            f'<input type="text" name="reason" placeholder="reden (bij laten vallen)" '
            f'style="width:100%;margin-bottom:.3rem;padding:.25rem .4rem;'
            f'border:1px solid var(--border);border-radius:6px">'
            f'<button class="btn ok" type="submit" name="action" value="target_project">'
            f'✓ maak content-project</button> '
            f'<button class="btn danger" type="submit" name="action" value="target_drop">'
            f'✗ laat vallen</button></form>'
            f'<div style="margin-top:.3rem">{_flip(w, "volg", "→ 🌱 volg")}</div>')

    # Doelwit-woorden: waar we op willen ranken (sorteer op kans).
    trows = "".join(
        f'<tr><td><b>{_e(x["word"])}</b></td>'
        f'<td>{_num(x.get("volume"), "/mnd")}</td>'
        f'<td>{("<b>" + _fmt_int(x["opportunity"]) + "</b>") if x.get("opportunity") is not None else "<span class=muted>—</span>"}</td>'
        f'<td>{_pos_cell(x)}</td>'
        f'<td style="min-width:230px">{_target_acts(x)}</td></tr>'
        for x in sorted(targets, key=lambda x: -((x.get("opportunity") if x.get("opportunity") is not None else -1))))
    targets_tbl = (
        '<table><thead><tr><th>doelwit-woord</th><th>volume</th><th>kans</th>'
        '<th>onze Google-stand</th><th>jouw oordeel</th></tr></thead>'
        f'<tbody>{trows or "<tr><td colspan=5 class=muted>geen doelwit-woorden</td></tr>"}</tbody></table>')

    # Volg-woorden: seeds voor de radar; toon de meerjarige trend-toestand (5 jaar) + sparkline.
    def _surge_tag(x):
        move = x.get("recent_move") or ("stijgend" if x.get("recent_surge") else None)
        if move not in ("stijgend", "dalend"):
            return ""
        label = "▲ recent stijgend" if move == "stijgend" else "▼ recent dalend"
        color = "var(--coral)" if move == "stijgend" else "var(--green-dark)"
        out = f' <b style="color:{color}">{label}</b>'
        expl = x.get("surge_explanation") or {}
        if expl.get("title"):                              # scout: nieuws-aanleiding
            out += (f' <span class="muted">· 📰 <a href="{_e(expl.get("link", ""))}">'
                    f'{_e(expl["title"][:55])}</a></span>')
        d = x.get("duiding")                               # Harry: academische duiding (kaartje)
        if d:
            out += (f' <span class="muted">· 🔬 <a href="/card?id={_e(d["id"])}">'
                    f'{_e((d.get("claim") or "duiding")[:45])}</a></span>')
        return out

    def _trend_cell(x):
        st = x.get("trend_state")
        surge = _surge_tag(x)
        if st:
            spark = _sparkline(x.get("trend_series"))
            base = (f'{spark} {_e(trend_state_label(st))} <span class="muted">(5 jr)</span>'
                    if spark else f'{_e(trend_state_label(st))} <span class="muted">(5 jr)</span>')
            return base + surge
        tp = x.get("trend_pct")                            # fallback: 12-mnd % als er nog geen toestand is
        if tp is not None:
            arrow = "▲" if tp > 0 else ("▼" if tp < 0 else "▬")
            sign = "+" if tp > 0 else ""
            return f'{arrow} {sign}{_e(tp)}% <span class="muted">(12 mnd)</span>{surge}'
        return f'<span class="muted">— (draai enrich_volumes)</span>{surge}'
    srows = "".join(
        f'<tr><td><b>{_e(x["word"])}</b></td>'
        f'<td>{_num(x.get("volume"), "/mnd")}</td>'
        f'<td>{_trend_cell(x)}</td>'
        f'<td>{_flip(x["word"], "doelwit", "→ 🎯 doelwit")}</td></tr>'
        for x in sorted(seeds, key=lambda x: (
            {"opkomend": 0, "stabiel": 1, "piek-voorbij": 2, "dalend": 3}.get(x.get("trend_state"), 4),
            -((x.get("volume") or 0)))))
    seeds_tbl = (
        '<table><thead><tr><th>volg-woord (seed)</th><th>volume</th>'
        '<th>trend</th><th></th></tr></thead>'
        f'<tbody>{srows or "<tr><td colspan=4 class=muted>geen volg-woorden</td></tr>"}</tbody></table>')

    lib_tbl = (f'<h3 style="margin:.6rem 0 .2rem">🎯 Doelwit-woorden — waar we op willen ranken ({len(targets)})</h3>'
               f'{targets_tbl}'
               f'<h3 style="margin:1rem 0 .2rem">🌱 Volg-woorden — seeds voor de radar ({len(seeds)})</h3>'
               f'{seeds_tbl}')
    if show_all:                                          # geschiedenis: ook niet-approved woorden
        other = [x for x in lib if x["status"] != "approved"]
        orows = "".join(
            f'<tr><td><b>{_e(x["word"])}</b></td><td><span class="chip">{_e(x["status"])}</span></td>'
            f'<td class="muted">{_e(x.get("date", ""))}</td></tr>' for x in other)
        lib_tbl += ('<h3 style="margin:1rem 0 .2rem">Overige (geschiedenis)</h3>'
                    '<table><thead><tr><th>woord</th><th>status</th><th>datum</th></tr></thead>'
                    f'<tbody>{orows or "<tr><td colspan=3 class=muted>geen</td></tr>"}</tbody></table>')

    # Escalated-berg: termen die de Librarian naar de mens escaleerde. Afroombaar met
    # één klik (keur goed → approved / verbied → forbidden). Dit dweilt het kerkhof leeg.
    esc = [x for x in lib if x["status"] == "escalated"]
    erows = "".join(
        f'<tr><td><b>{_e(x["word"])}</b></td>'
        f'<td class="muted">{_e((x.get("rationale") or "")[:90])}</td>'
        f'<td>' + ((_lib_btn(x["word"], "approve", "✓ keur goed", csrf_token, "ok") + " "
                    + _lib_btn(x["word"], "reject", "✗ verbied", csrf_token, "danger"))
                   if writable else '<span class="muted">—</span>') + '</td></tr>'
        for x in esc)
    esc_tbl = ('<table><thead><tr><th>woord</th><th>waarom geëscaleerd</th><th>jouw oordeel</th></tr></thead>'
               f'<tbody>{erows}</tbody></table>')
    esc_block = (f'<details open><summary>⚖️ Wacht op jouw oordeel — geëscaleerd ({len(esc)})</summary>'
                 f'{esc_tbl}</details>') if esc else ''

    # Inzichten (kennislaag) — synthese-kaartjes (creatieve links) eerst, dan geëmergeerd
    ins = snap.get("insights", [])
    g = snap.get("knowledge_graph", {})
    g_line = (f'<p class="muted">Graaf: {g.get("cards", 0)} kaartjes · {g.get("links", 0)} links · '
              f'gem. gelijkenis {g.get("avg_similarity", 0)}</p>') if g else ''
    irows2 = "".join(
        f'<tr><td>{("🔗 " if x.get("synthese") else "")}'
        f'<a href="/card?id={_e(x["id"])}">{_e(x["claim"][:120])}</a>'
        f'{(" <span class=muted>(" + _e(x["links"]) + " links)</span>") if x.get("links") else ""}</td>'
        f'<td class="muted">{_e(x["status"])}</td>'
        f'<td>{_e(x["grounding_count"])}×</td></tr>' for x in ins)
    ins_tbl = (g_line + '<table><thead><tr><th>claim</th><th>status</th><th>gegrond</th></tr></thead>'
               f'<tbody>{irows2 or "<tr><td colspan=3 class=muted>geen inzichten</td></tr>"}</tbody></table>')

    # Concurrenten: gespotte (kandidaat) merken die op jouw oordeel wachten + de monitor-set.
    cands = snap.get("competitor_candidates", [])
    confirmed = snap.get("competitor_confirmed", [])
    config_brands = snap.get("competitor_config", [])
    monitored = _monitored_brands(config_brands, confirmed)
    crows = "".join(
        f'<tr><td><b>{_e(c["brand"])}</b></td>'
        f'<td class="muted"><a href="{_e(c.get("link", ""))}">{_e((c.get("article") or "")[:80])}</a></td>'
        f'<td>' + ((_brand_btn(c["brand"], "confirm", "✓ monitor", csrf_token, "ok") + " "
                    + _brand_btn(c["brand"], "reject", "✗ negeer", csrf_token, "danger"))
                   if writable else '<span class="muted">—</span>') + '</td></tr>'
        for c in cands)
    cand_tbl = ('<table><thead><tr><th>gespot merk</th><th>in artikel</th><th>jouw oordeel</th></tr></thead>'
                f'<tbody>{crows or "<tr><td colspan=3 class=muted>geen nieuwe merken gespot</td></tr>"}</tbody></table>')
    # Volledige monitor-lijst: élke gemonitorde concurrent + zijn laatste nieuwsfeit.
    news = snap.get("competitor_news", {}) or {}
    _conf_set = {b.lower() for b in confirmed}

    def _herkomst(b):
        return "door jou" if b.lower() in _conf_set else "vast"
    mrows = ""
    for b in monitored:
        n = news.get(b) or {}
        if n.get("title"):
            feit = (f'<a href="{_e(n.get("link", ""))}">{_e(n["title"][:90])}</a>'
                    f' <span class="muted">({_e(n.get("date", ""))})</span>')
        else:
            feit = '<span class="muted">geen recent nieuws opgehaald</span>'
        mrows += (f'<tr><td><b>{_e(b)}</b> <span class="muted">{_herkomst(b)}</span></td>'
                  f'<td>{feit}</td></tr>')
    monitor_tbl = (
        '<table><thead><tr><th>concurrent</th><th>laatste nieuwsfeit</th></tr></thead>'
        f'<tbody>{mrows or "<tr><td colspan=2 class=muted>geen concurrenten gemonitord</td></tr>"}</tbody></table>')
    comp_block = (f'<h2>Concurrenten</h2>'
                  f'<details open><summary>🔮 Nieuw gespot — wacht op jouw oordeel ({len(cands)})</summary>'
                  f'{cand_tbl}</details>'
                  f'<details open><summary>📡 Gemonitord — alle concurrenten ({len(monitored)})</summary>'
                  f'{monitor_tbl}</details>') if (cands or monitored) else ''

    # Linkbuilding: gidsen/lijstjes waar Nooch in vermeld wil worden (hoog = noemt
    # concurrenten maar niet Nooch → sterkste pitch).
    ltargets = snap.get("link_candidates", [])
    lpursued = snap.get("link_pursued", [])
    _prio_mark = {"hoog": "★ hoog", "midden": "midden", "laag": "laag", "onbekend": "?"}
    lrows3 = "".join(
        f'<tr class="{"st-future" if t.get("priority") in ("laag", "onbekend") else ""}">'
        f'<td>{_e(_prio_mark.get(t.get("priority"), "?"))}</td>'
        f'<td><a href="{_e(t.get("link", ""))}">{_e((t.get("title") or "")[:90])}</a>'
        f'{(" · noemt: " + _e(", ".join(t.get("mentions", [])))) if t.get("mentions") else ""}</td>'
        f'<td>' + ((_link_btn(t["link"], "pursue", "✓ pitchen", csrf_token, "ok") + " "
                    + _link_btn(t["link"], "ignore", "✗ negeer", csrf_token, "danger"))
                   if writable else '<span class="muted">—</span>') + '</td></tr>'
        for t in ltargets)
    ltbl = ('<table><thead><tr><th>prio</th><th>gids / lijstje</th><th>jouw oordeel</th></tr></thead>'
            f'<tbody>{lrows3 or "<tr><td colspan=3 class=muted>geen doelwitten gespot</td></tr>"}</tbody></table>')
    pursued_line = (f'<p class="muted">Te pitchen ({len(lpursued)}): '
                    + ", ".join(_e((p.get("source") or p.get("title") or "")[:40]) for p in lpursued)
                    + '</p>') if lpursued else ''
    link_block = (f'<h2>Linkbuilding</h2>'
                  f'<details open><summary>🔗 Doelwitten — wacht op jouw oordeel ({len(ltargets)})</summary>'
                  f'{ltbl}</details>{pursued_line}') if (ltargets or lpursued) else ''

    counts = (
        f'{sum(1 for r in roster if not r["archived"])} rollen · '
        f'{sum(1 for i in inbox if i.get("status") == "pending")} open inbox-items · '
        f'{sum(1 for p in projects if p.get("status") not in _parked)} open projecten · '
        f'{sum(1 for x in lib if x["status"] == "approved")} actieve woorden · {len(ins)} inzichten'
    )

    if writable:
        badge = '<span class="badge rw">verwerk-modus</span>'
    else:
        badge = '<span class="badge ro">read-only</span>'
    hist = ('<a href="/">← verberg geschiedenis</a>' if show_all
            else '<a href="/?history=1">toon geschiedenis (gesloten + gearchiveerd)</a>')

    # "Aan jou": alles wat nú een beslissing van de mens vraagt, op één plek geteld.
    _n_kansen = sum(1 for b in snap.get("backlog", []) if b.get("approvable"))
    _n_inbox = sum(1 for i in inbox if i.get("status") == "pending" and i.get("type") != "opportunity")
    _n_woorden = sum(1 for x in lib if x["status"] == "escalated")
    _n_conc = len(snap.get("competitor_candidates", []))
    _n_link = len(snap.get("link_candidates", []))
    _parts = []
    if _n_kansen:  _parts.append(f'{_n_kansen} kansen')
    if _n_inbox:   _parts.append(f'{_n_inbox} inbox-items')
    if _n_woorden: _parts.append(f'{_n_woorden} woorden te beoordelen')
    if _n_conc:    _parts.append(f'{_n_conc} nieuwe concurrenten')
    if _n_link:    _parts.append(f'{_n_link} linkbuilding-doelwitten')
    _aan_jou = (f'<div class="aanjou"><b>📥 Aan jou:</b> {" · ".join(_parts)}</div>'
                if _parts else '<div class="aanjou">📥 <b>Aan jou:</b> niks openstaand 🎉</div>')

    inner = (
        f'<h1>NoochVille cockpit {badge}</h1>'
        f'<div class="bar">{_e(counts)} · gegenereerd {_e(_ts(snap.get("generated_at")))} · {hist}</div>'
        f'<style>.aanjou{{background:var(--yellow-light);border:1px solid var(--border);'
        f'border-radius:var(--radius);padding:.5rem .9rem;margin:.3rem 0 1rem;font-size:.95rem}}</style>'
        f'{_aan_jou}'
        f'{_banner(msg)}'
        f'{_render_digest(snap.get("digest", {}), snap.get("noochie_daily", {}))}'
        f'{_render_backlog(snap.get("backlog", []), snap.get("north_star", {}), csrf_token)}'
        f'<h2>Inbox</h2>{inbox_tbl}'
        f'<h2>Proces (projecten)</h2>{proj_tbl}'
        f'<h2>Kennis</h2>'
        f'{esc_block}'
        f'<details open><summary>Woordenschat ({len(approved_lib)} actieve woorden)</summary>{lib_tbl}</details>'
        f'<details><summary>Inzichten — kennislaag ({len(ins)} kaartjes)</summary>{ins_tbl}</details>'
        f'<details><summary>Roster ({sum(1 for r in roster if not r["archived"])} actieve rollen)</summary>{roster_tbl}</details>'
        f'{comp_block}'
        f'{link_block}'
    )
    return _page("NoochVille cockpit", inner)


# ── server (read-only, localhost) ────────────────────────────────────────────

def _flash(result: dict) -> str:
    """Korte, leesbare terugkoppeling van een actie (getoond als banner na de redirect)."""
    if not result.get("ok"):
        st = result.get("status")
        if st in ("escalated", "invalid"):
            return f"✗ Governance {st}: {result.get('reason', '')}"
        return "✗ " + (result.get("error") or result.get("reason") or "actie mislukt")
    if result.get("status") == "approved" and "opp_kind" in result:
        return (f"✓ Kans goedgekeurd → project voor {result.get('owner') or 'het dorp'} "
                f"(zie Proces). De rol pakt 'm op; jij blijft de poort.")
    if result.get("status") == "rejected" and "title" in result:
        return "✓ Kans genegeerd — de rol leert van je reden en herhaalt 'm niet."
    if "proj_status" in result:
        return f"✓ Project-status → {result['proj_status']}"
    if "proj_edit" in result:
        return "✓ Project bijgewerkt"
    if "delegated" in result:
        return "✓ Noochie heeft een voorstel ingebracht — zie je inbox"
    if result.get("status") == "adopted":
        return f"✓ Skill '{result.get('skill')}' toegekend aan {result.get('role_id')}"
    if "removed" in result:
        return "✓ Kaartje verwijderd"
    if "card_id" in result:
        return f"✓ Kennis-kaart vastgelegd ({result['card_id']})"
    if "pid" in result:
        return f"✓ Project aangemaakt voor {result.get('owner')}"
    if "brand_status" in result:
        return f"✓ '{result['brand']}' → {result['brand_status']}"
    if "link_status" in result:
        return f"✓ doelwit → {result['link_status']}"
    if "word" in result:
        return f"✓ '{result['word']}' → {result.get('status')}"
    _labels = {"resolved": "✓ Spanning afgehandeld (resolved)",
               "withdrawn": "✓ Spanning ingetrokken (niets nodig)",
               "deferred": "✓ Spanning uitgesteld (defer)"}
    return _labels.get(result.get("status"), "✓ " + (result.get("status") or "klaar"))


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
    if action == "lib_override":
        library = Library(os.path.join(dd, "library.json"))
        return override_library_term(library, extra.get("word", ""),
                                     extra.get("decision", ""), reason=reason)
    if action in ("opp_approve", "opp_reject"):
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        decision = "approve" if action == "opp_approve" else "reject"
        return decide_opportunity(inbox, projects, iid, decision, reason=reason)
    if action in ("target_project", "target_drop"):
        library = Library(os.path.join(dd, "library.json"))
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        decision = "project" if action == "target_project" else "drop"
        return decide_target(library, projects, extra.get("word", ""), decision, reason=reason)
    if action == "lib_function":
        library = Library(os.path.join(dd, "library.json"))
        return set_word_function(library, extra.get("word", ""), extra.get("decision", ""))
    if action == "brand_decide":
        brands = CompetitorBrands(os.path.join(dd, "competitor_brands.json"))
        return decide_competitor_candidate(brands, extra.get("word", ""),
                                           extra.get("decision", ""))
    if action == "link_decide":
        targets = LinkTargets(os.path.join(dd, "linkbuilding_targets.json"))
        return decide_link_target(targets, extra.get("word", ""), extra.get("decision", ""))
    if action == "defer":
        return defer_item(inbox, iid, reason=reason)
    if action == "confirm":
        return confirm_item(inbox, iid)
    if action == "done":
        return mark_done(inbox, iid, reason=reason)
    if action == "resolve":
        return resolve_tension(inbox, iid, reason=reason)
    if action == "add_reference":
        notes = NotesStore(os.path.join(dd, "notes.json"))
        return add_reference(notes, claim=extra.get("claim", ""),
                             grounds=extra.get("grounds", ""))
    if action == "note_remove":
        notes = NotesStore(os.path.join(dd, "notes.json"))
        return remove_note(notes, iid)
    if action == "delegate_noochie":
        # Noochie werkt de spanning uit tot een concreet voorstel (LLM) en zet dat als
        # 'voorstel'-item in de inbox; de mens beoordeelt het daarna.
        from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
        item = inbox.get(iid)
        if item is None:
            return {"ok": False, "error": "spanning niet gevonden"}
        c = item.get("context", {}) or {}
        tension = (c.get("description") or c.get("tension") or c.get("reason")
                   or item.get("subject"))
        role = c.get("role_id") or c.get("sensed_by") or ""
        res = VoorstelSchrijvenSkill().run({"tension": tension, "role": role})
        if not res.get("ok"):
            return res
        inbox.add_voorstel(item.get("subject"), res["voorstel"], by="noochie",
                           origin=item.get("subject"))
        return {"ok": True, "delegated": True}
    if action == "add_project":
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        return route_to_project(projects, owner=extra.get("owner", ""),
                                scope=extra.get("scope", ""))
    if action in ("proj_active", "proj_waiting", "proj_future", "proj_done"):
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        if action == "proj_active":
            ok = projects.start(iid)
            return {"ok": ok, "proj_status": "running"}
        if action == "proj_waiting":
            ok = projects.block(iid, reason or "(wachtend)")
            return {"ok": ok, "proj_status": "blocked"}
        if action == "proj_future":
            ok = projects.to_future(iid)
            return {"ok": ok, "proj_status": "future"}
        ok = projects.complete(iid)
        return {"ok": ok, "proj_status": "done"}
    if action == "proj_edit":
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        ok = projects.edit(iid, scope=extra.get("scope", ""), owner=extra.get("owner", ""))
        return {"ok": ok, "proj_edit": True}
    if action == "add_governance":
        records = Records(os.path.join(dd, "governance_records.json"))
        return route_to_governance(records, extra.get("role", ""), extra.get("skill", ""),
                                   extra.get("rationale", ""), gap_key=iid)
    return {"ok": False, "error": f"onbekende actie '{action}'"}


def make_handler(data_dir: str | None):
    csrf_token = secrets.token_urlsafe(16)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            msg = (qs.get("msg") or [None])[0]
            if path == "/process":
                iid = (qs.get("iid") or [""])[0]
                snap = gather(data_dir)
                item = next((i for i in snap["inbox"] if i.get("id") == iid), None)
                if item is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Item niet gevonden")
                    return
                body = render_process(item, snap["roster"], csrf_token, msg=msg).encode("utf-8")
            elif path == "/project":
                pid = (qs.get("pid") or [""])[0]
                snap = gather(data_dir)
                proj = next((p for p in snap["projects"] if p.get("id") == pid), None)
                if proj is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Project niet gevonden")
                    return
                body = render_project_edit(proj, snap["roster"], csrf_token).encode("utf-8")
            elif path == "/card":
                cid = (qs.get("id") or [""])[0]
                dd = data_dir or _default_data_dir()
                notes = NotesStore(os.path.join(dd, "notes.json"))
                card = notes.get(cid)
                if card is None:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Kaartje niet gevonden")
                    return
                cdict = {"id": card.id, "claim": card.claim, "grounds": card.grounds,
                         "status": str(getattr(card.status, "value", card.status)),
                         "grounding_count": card.grounding_count, "word": card.word or ""}
                nbs = [{"id": n.id, "claim": n.claim,
                        "status": str(getattr(n.status, "value", n.status)),
                        "grounding_count": n.grounding_count} for n in notes.neighbors(cid)]
                body = render_card(cdict, nbs, csrf_token).encode("utf-8")
            elif path in ("/", "/index.html"):
                show_all = (qs.get("history") or ["0"])[0] in ("1", "true", "yes")
                body = render_html(gather(data_dir), csrf_token=csrf_token, msg=msg,
                                   show_all=show_all).encode("utf-8")
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
                     "scope": (form.get("scope") or [""])[0],
                     "role": (form.get("role") or [""])[0],
                     "skill": (form.get("skill") or [""])[0],
                     "rationale": (form.get("rationale") or [""])[0],
                     "word": (form.get("word") or [""])[0],
                     "decision": (form.get("decision") or [""])[0]}
            result = _dispatch_action(data_dir, action, iid, reason, extra=extra)
            # 303 → verse GET. Rails keren terug naar de spanning (next), sluiten gaat home.
            # De uitkomst gaat als korte flash-banner mee in de query.
            nxt = (form.get("next") or ["/"])[0]
            if not nxt.startswith("/"):
                nxt = "/"
            sep = "&" if "?" in nxt else "?"
            nxt = f"{nxt}{sep}msg={urllib.parse.quote(_flash(result))}"
            self.send_response(303)
            self.send_header("Location", nxt)
            self.end_headers()

        def log_message(self, *_):  # stil
            pass

    return _Handler


def _load_env() -> None:
    """Laad de project-.env (API-sleutels, model, throttle) in os.environ. De cockpit
    draait als eigen proces en zou anders géén LLM-sleutels hebben — dan faalt Noochie's
    draft met 'geen LLM beschikbaar' ook al staat er tegoed klaar. Best-effort."""
    try:
        from nooch_village.config import load_context
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        load_context(base)
    except Exception:
        pass


def serve(host: str = "127.0.0.1", port: int = 8765,
          data_dir: str | None = None) -> None:
    if host not in _LOCAL_HOSTS:
        raise SystemExit(
            f"Cockpit weigert niet-lokale host '{host}'. Read-only blijft op localhost."
        )
    _load_env()   # .env-sleutels in os.environ, anders heeft de cockpit geen LLM
    # ThreadingHTTPServer: elke browser-verbinding krijgt een eigen thread. Een single-threaded
    # server blijft hangen zodra de browser (Firefox) een tweede verbinding open houdt → reloads
    # leken vast te lopen. daemon_threads zodat Ctrl-C meteen afsluit.
    httpd = ThreadingHTTPServer((host, port), make_handler(data_dir))
    httpd.daemon_threads = True
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
