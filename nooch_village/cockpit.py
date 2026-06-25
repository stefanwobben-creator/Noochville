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
import re
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
    decide_target, ask_role, pick_governance_target, formulate_project)
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
    from nooch_village.constraints import Constraints
    house_rules = Constraints(os.path.join(dd, "constraints.json")).all()
    from nooch_village.roloverleg import Agenda
    agenda_open = Agenda(os.path.join(dd, "roloverleg_agenda.json")).open()
    noochie_daily = {}
    _nd_path = os.path.join(dd, "noochie_daily.json")
    if os.path.exists(_nd_path):
        try:
            import json as _json
            noochie_daily = _json.load(open(_nd_path))
        except Exception:
            noochie_daily = {}
    shopify = {}
    _shop_path = os.path.join(dd, "shopify_metrics.json")
    if os.path.exists(_shop_path):
        try:
            import json as _json
            shopify = _json.load(open(_shop_path))
        except Exception:
            shopify = {}
    # Laatste 7-daagse bezoekerscijfer (door de GrowthAnalyst per puls weggeschreven), voor conversie.
    visitors_7d = None
    _ph_path = os.path.join(dd, "pulse_history.jsonl")
    if os.path.exists(_ph_path):
        try:
            import json as _json
            for _line in open(_ph_path):
                _line = _line.strip()
                if not _line:
                    continue
                _v = _json.loads(_line).get("visitors_7d")
                if _v is not None:
                    visitors_7d = _v          # laatste niet-lege wint
        except Exception:
            visitors_7d = None

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
            dlg = ctx.get("dialogue") or []
            backlog.append({
                "title": ctx.get("title") or it.get("subject"), "kind": "kans",
                "by": ctx.get("by", ""),
                "wat": ctx.get("wat", "") or ctx.get("hypothesis", ""),  # back-compat
                "waarom": ctx.get("waarom", ""),
                "business_case": bc, "value": business_value(bc),
                "dialogue": dlg, "awaiting": any(not d.get("answered") for d in dlg),
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
    # NB: lopende projecten staan NIET in de backlog — die is een triage-wachtrij (dingen die
    # jouw beslissing vragen). Zodra je een kans afrondt, verdwijnt hij hier; het werk leeft
    # verder op het projectbord (Proces). Zo blijft de backlog schoon.
    backlog.sort(key=lambda x: -x["value"])
    project_drafts = [p for p in proj if p.get("status") == "draft"]

    _now = time.time()
    return {
        "roster": roster,
        "inbox": inbox_items,
        "projects": proj,
        "project_drafts": project_drafts,
        "backlog": backlog,
        "north_star": _north_star(dd),
        "library": lib,
        "insights": insights,
        "knowledge_graph": graph,
        "competitor_candidates": brands.candidates(),
        "competitor_confirmed": brands.confirmed(),
        "competitor_news": comp_news,
        "house_rules": house_rules,
        "agenda_open": agenda_open,
        "noochie_daily": noochie_daily,
        "shopify": shopify,
        "visitors_7d": visitors_7d,
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


_TRIAGE_CSS = """
.tg-wrap{max-width:680px;margin:0 auto}
.tg-prog{height:8px;background:var(--sand);border-radius:99px;overflow:hidden;margin:.4rem 0 1.2rem}
.tg-prog>span{display:block;height:100%;background:var(--green)}
.tg-card{background:var(--cream-3);border:1px solid var(--border);border-radius:var(--radius);
  padding:1.1rem 1.3rem;box-shadow:var(--shadow);margin-bottom:1.2rem}
.tg-card h2{margin:.1rem 0 .5rem;font-size:1.25rem;color:var(--ink)}
.tg-meta{font-size:.85rem;color:var(--gray);margin-bottom:.5rem}
.tg-q{font-family:var(--font-display);font-weight:800;font-size:1.05rem;margin:.2rem 0 .8rem}
.tstep{display:none}.tstep.on{display:block}
.tg-opts{display:flex;flex-direction:column;gap:.6rem}
.bigbtn{font-family:var(--font-body);font-weight:700;font-size:1rem;text-align:left;
  border:1.5px solid var(--border);background:var(--surface);border-radius:14px;
  padding:.85rem 1.1rem;cursor:pointer;transition:.12s;width:100%}
.bigbtn:hover{border-color:var(--green);background:var(--green-tint)}
.bigbtn small{display:block;font-weight:500;font-size:.8rem;color:var(--gray);margin-top:.15rem}
.bigbtn.go{background:var(--green);border-color:var(--green);color:#fff}
.bigbtn.go:hover{background:var(--green-dark)}
.bigbtn.warn{border-color:var(--coral);color:var(--coral)}
.tg-back{background:none;border:none;color:var(--gray);cursor:pointer;font-size:.85rem;
  padding:.3rem 0;margin-top:.6rem}
.tg-in{width:100%;box-sizing:border-box;padding:.6rem .7rem;border:1px solid var(--border);
  border-radius:10px;font-size:.95rem;margin:.3rem 0 .6rem;font-family:var(--font-body)}
.tg-dlg{border-left:3px solid var(--green);padding-left:.7rem;margin:.6rem 0;font-size:.9rem}
.tg-skip{text-align:center;margin-top:1rem}
.tg-list{display:flex;flex-direction:column;gap:.5rem}
.tg-item{display:flex;align-items:center;gap:.7rem;text-decoration:none;color:var(--ink);
  background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:.7rem .9rem;
  transition:.12s}
.tg-item:hover,.tg-item.sel{border-color:var(--green);background:var(--green-tint)}
.tg-item.sel{box-shadow:0 0 0 2px var(--green)}
.tg-hint{font-size:.78rem;color:var(--gray);margin-top:.8rem}
.tg-hint kbd{background:var(--surface);border:1px solid var(--border);border-radius:4px;
  padding:0 .3rem;font-family:var(--font-body);font-size:.72rem}
.tg-item-n{flex:0 0 auto;width:1.6rem;height:1.6rem;border-radius:50%;background:var(--sand);
  display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:700}
.tg-item-body{flex:1 1 auto;min-width:0;display:flex;flex-direction:column}
.tg-item-body small{color:var(--gray);font-size:.78rem}
.tg-go{flex:0 0 auto;color:var(--green-dark);font-weight:700;font-size:.85rem}
.tg-wacht{background:var(--cream-3);border:1px solid var(--border);border-radius:6px;
  padding:0 .3rem;font-size:.7rem;font-weight:600}
"""


def render_triage_overview(queue: list, token: str, msg=None) -> str:
    """Overzicht van álle openstaande spanningen: kies er zelf één om te verwerken. Na het
    verwerken kom je hier terug (de afgehandelde is dan weg). Geen gedwongen volgorde, geen
    'terug naar de eerste'."""
    from nooch_village.business_case import format_business_case
    head = ('<div class="tg-wrap"><p><a href="/">← cockpit</a></p>'
            '<h1>🎯 Spanningen verwerken</h1>')
    if not queue:
        body = ('<div class="tg-card"><h2>Alles verwerkt 🎉</h2>'
                '<p class="muted">Geen openstaande spanningen meer. Mooi opgeruimd.</p>'
                '<p><a class="btn ok" href="/">← terug naar de cockpit</a></p></div>')
        return _page("Spanningen verwerken",
                     f'{head}{_banner(msg)}{body}</div><style>{_TRIAGE_CSS}</style>')
    rows = []
    for i, x in enumerate(queue, 1):
        bc = format_business_case(x.get("business_case")) if x.get("business_case") else ""
        wacht = (' <span class="tg-wacht">⏳ wacht op antwoord</span>'
                 if x.get("awaiting") else "")
        meta = " · ".join(p for p in [
            (f'door {_e(x["by"])}' if x.get("by") else ""), _e(bc),
            (f'waarde {_e(x.get("value"))}' if x.get("value") is not None else "")] if p)
        rows.append(
            f'<a class="tg-item" href="/triage?iid={_e(x["iid"])}">'
            f'<span class="tg-item-n">{i}</span>'
            f'<span class="tg-item-body"><b>{_e(x["title"])}</b>{wacht}'
            f'<small>{meta}</small></span><span class="tg-go">verwerk →</span></a>')
    hint = ('<p class="tg-hint">Toetsenbord: <kbd>↑</kbd><kbd>↓</kbd> kiezen · '
            '<kbd>Enter</kbd> openen</p>')
    body = (f'<p class="tg-meta">{len(queue)} openstaande spanning(en) — kies er één om te '
            f'verwerken. Je komt hier daarna vanzelf terug.</p>'
            f'<div class="tg-list">{"".join(rows)}</div>{hint}')
    js = ("<script>(function(){var it=[].slice.call(document.querySelectorAll('.tg-item'));"
          "var i=-1;function sel(n){if(!it.length)return;i=(n+it.length)%it.length;"
          "it.forEach(function(e){e.classList.remove('sel')});it[i].classList.add('sel');"
          "it[i].scrollIntoView({block:'nearest'});}"
          "document.addEventListener('keydown',function(e){"
          "if(e.key==='ArrowDown'||e.key==='j'){e.preventDefault();sel(i+1);}"
          "else if(e.key==='ArrowUp'||e.key==='k'){e.preventDefault();sel(i-1);}"
          "else if(e.key==='Enter'&&i>=0){window.location=it[i].getAttribute('href');}});"
          "if(it.length)sel(0);})();</script>")
    return _page("Spanningen verwerken",
                 f'{head}{_banner(msg)}{body}</div>{js}<style>{_TRIAGE_CSS}</style>')


def render_triage(x: dict | None, pos: int, total: int, roles: list,
                  token: str, msg=None) -> str:
    """Focusmodus: één spanning per scherm, één keuze per stap (Duolingo-stijl). Na een keuze
    kom je terug op het overzicht; de afgehandelde spanning is dan weg."""
    from nooch_village.business_case import format_business_case
    head = ('<div class="tg-wrap"><p><a href="/triage">← overzicht</a> · '
            '<a href="/">cockpit</a></p><h1>🎯 Spanning verwerken</h1>')
    if not x:
        body = ('<div class="tg-card"><h2>Alles verwerkt 🎉</h2>'
                '<p class="muted">Geen openstaande spanningen meer.</p>'
                '<p><a class="btn ok" href="/triage">← naar het overzicht</a></p></div>')
        return _page("Spanningen verwerken", f'{head}{_banner(msg)}{body}</div>'
                     + f'<style>{_TRIAGE_CSS}</style>')

    iid = x["iid"]
    nog = max(total - 1, 0)
    prog = (f'<div class="tg-meta">Nog {nog} andere spanning(en) op het overzicht</div>'
            if total else "")
    # de kaart: waar gaat het over
    bc = format_business_case(x.get("business_case")) if x.get("business_case") else ""
    meta = " · ".join(p for p in [
        (f'door {_e(x["by"])}' if x.get("by") else ""),
        _e(bc), (f'waarde {_e(x.get("value"))}' if x.get("value") is not None else "")] if p)
    dlg = ""
    for d in (x.get("dialogue") or []):
        a = (f'<div>💬 <b>{_e(d.get("by") or "rol")}:</b> {_e(d.get("a"))}</div>'
             if d.get("answered")
             else '<div class="muted">⏳ <i>wachten op antwoord (volgende puls)</i></div>')
        dlg += f'<div class="tg-dlg">🙋 <b>jij:</b> {_e(d.get("q"))}{a}</div>'
    card = (f'<div class="tg-card">{prog}<h2>{_e(x["title"])}</h2>'
            f'<div class="tg-meta">{meta}</div>'
            f'{("<div>" + _e(x.get("wat")) + "</div>") if x.get("wat") else ""}'
            f'{("<div class=muted><b>Waarom:</b> " + _e(x.get("waarom")) + "</div>") if x.get("waarom") else ""}'
            f'{dlg}</div>')

    def f_open(action, fields_html, *, nxt):
        """Een POST-form naar /action met csrf+iid+next en de eigen velden."""
        return (f'<form method="post" action="/action">'
                f'<input type="hidden" name="csrf" value="{_e(token)}">'
                f'<input type="hidden" name="iid" value="{_e(iid)}">'
                f'<input type="hidden" name="next" value="{_e(nxt)}">'
                f'<input type="hidden" name="action" value="{_e(action)}">'
                f'{fields_html}</form>')

    stay = f'/triage?iid={iid}'      # uitkomst toevoegen → blijf op deze kaart (stapelen)
    nextc = '/triage'               # afronden / vraag → volgende kaart
    owner_opts = "".join(f'<option value="{_e(r)}">{_e(r)}</option>' for r in roles)
    gov_opts = ('<option value="__auto__">🤖 laat AI kiezen (nieuw of uitbreiden)</option>'
                + owner_opts + '<option value="__new__">➕ nieuwe rol</option>')

    # ── stap 0: hoe pak je dit op? ──
    step0 = (
        '<div class="tstep on" id="t-start"><div class="tg-q">Hoe pak je dit op?</div>'
        '<div class="tg-opts">'
        '<button class="bigbtn" type="button" onclick="tg(\'t-tac\')">⚙️ Tactical'
        '<small>werk binnen de bestaande structuur: een project of informatie</small></button>'
        '<button class="bigbtn" type="button" onclick="tg(\'t-gov\')">🏛️ Governance'
        '<small>de structuur moet veranderen: een rol erbij of uitbreiden</small></button>'
        '<button class="bigbtn go" type="button" onclick="tg(\'t-oordeel\')">✓ Afronden / oordeel'
        '<small>sluiten met een oordeel dat het dorp traint (leuk idee, nee, nu niet, ...)</small>'
        '</button>'
        '</div></div>')
    # ── stap tactical ──
    step_tac = (
        '<div class="tstep" id="t-tac"><div class="tg-q">Wat wil je doen?</div>'
        '<div class="tg-opts">'
        '<button class="bigbtn" type="button" onclick="tg(\'t-proj\')">📋 Project voor een rol'
        '<small>concrete uitkomst; je ziet \'m als concept en keurt \'m daarna goed</small></button>'
        '<button class="bigbtn" type="button" onclick="tg(\'t-give\')">📚 Informatie geven'
        '<small>iets meegeven aan de kennisbank van het dorp</small></button>'
        '<button class="bigbtn" type="button" onclick="tg(\'t-ask\')">❓ Informatie vragen'
        '<small>stel de rol een vraag; antwoord komt in de volgende puls</small></button>'
        '</div><button class="tg-back" type="button" onclick="tg(\'t-start\')">← terug</button></div>')
    # ── leafs ──
    step_proj = (
        '<div class="tstep" id="t-proj"><div class="tg-q">Project — welke rol pakt het op?</div>'
        + f_open("tac_project",
                 f'<select name="owner" class="tg-in">{owner_opts}</select>'
                 '<button class="bigbtn go" type="submit">📋 Maak concept-project</button>',
                 nxt=stay)
        + '<button class="tg-back" type="button" onclick="tg(\'t-tac\')">← terug</button></div>')
    step_give = (
        '<div class="tstep" id="t-give"><div class="tg-q">Wat wil je het dorp meegeven?</div>'
        + f_open("tac_info_give",
                 '<textarea name="info" class="tg-in" rows="3" '
                 'placeholder="jouw kennis / context"></textarea>'
                 '<button class="bigbtn go" type="submit">📚 Voeg toe aan kennisbank</button>',
                 nxt=stay)
        + '<button class="tg-back" type="button" onclick="tg(\'t-tac\')">← terug</button></div>')
    step_ask = (
        '<div class="tstep" id="t-ask"><div class="tg-q">Wat wil je de rol vragen?</div>'
        + f_open("tac_info_ask",
                 '<textarea name="question" class="tg-in" rows="3" '
                 'placeholder="bijv. ik snap dit voorstel niet, wat bedoel je?"></textarea>'
                 '<button class="bigbtn go" type="submit">❓ Vraag de rol (volgende)</button>',
                 nxt=nextc)
        + '<button class="tg-back" type="button" onclick="tg(\'t-tac\')">← terug</button></div>')
    step_gov = (
        '<div class="tstep" id="t-gov"><div class="tg-q">Voorstel — nieuwe rol of uitbreiden?</div>'
        + f_open("gov_proposal",
                 f'<select name="owner" class="tg-in">{gov_opts}</select>'
                 '<button class="bigbtn go" type="submit">🏛️ Maak voorstel</button>',
                 nxt=stay)
        + '<button class="tg-back" type="button" onclick="tg(\'t-start\')">← terug</button></div>')
    # ── oordeel-paneel: sluit de spanning mét een trainingssignaal ──
    # Eén form, gedeelde reden + huis-regel-vinkje, meerdere verdict-knoppen. Elke knop sluit
    # het item en stuurt terug naar het overzicht (nxt). Alleen 'niet in de visie' wordt een
    # harde huis-regel (als het vinkje aanstaat); de rest zijn zachte trainingssignalen.
    step_oordeel = (
        '<div class="tstep" id="t-oordeel"><div class="tg-q">Afronden — wat is je oordeel?</div>'
        f'<form method="post" action="/action">'
        f'<input type="hidden" name="csrf" value="{_e(token)}">'
        f'<input type="hidden" name="iid" value="{_e(iid)}">'
        f'<input type="hidden" name="next" value="{_e(nextc)}">'
        '<input type="text" name="reason" class="tg-in" placeholder="reden / opmerking (optioneel)">'
        '<div class="tg-opts">'
        '<button class="bigbtn go" type="submit" name="action" value="opp_praise">'
        '👍 Leuk idee<small>geen actie, wél een positief signaal: meer van dit denken</small></button>'
        '<button class="bigbtn" type="submit" name="action" value="tension_done">'
        '✓ Klaar — niets nodig<small>afgehandeld, geen verdere actie</small></button>'
        '<button class="bigbtn" type="submit" name="action" value="opp_soft_reject">'
        '🙂 Nee, maar geen regel<small>zachte afwijzing; mag opnieuw bij andere situatie</small></button>'
        '<button class="bigbtn" type="submit" name="action" value="opp_not_now">'
        '⏳ Nu niet handig<small>goed idee, verkeerde timing</small></button>'
        '<button class="bigbtn" type="submit" name="action" value="opp_elsewhere">'
        '🌍 Buiten NoochVille<small>een andere rol/partij buiten het dorp pakt dit op</small></button>'
        '<button class="bigbtn warn" type="submit" name="action" value="vision_drop">'
        '✗ Past niet binnen de visie<small>de enige die een harde huis-regel wordt</small></button>'
        '</div>'
        '<label style="display:block;font-size:.8rem;margin:.5rem 0">'
        '<input type="checkbox" name="remember" value="1" checked> onthoud als huis-regel '
        '(alleen bij ‘past niet binnen de visie’)</label>'
        '</form>'
        '<button class="tg-back" type="button" onclick="tg(\'t-start\')">← terug</button></div>')

    skip = ('<div class="tg-skip"><a class="muted" href="/triage">'
            '← terug naar het overzicht</a></div>'
            '<p class="tg-hint" style="text-align:center">Toetsenbord: '
            '<kbd>1</kbd> Tactical · <kbd>2</kbd> Governance · <kbd>3</kbd> afronden · '
            '<kbd>←</kbd> terug · <kbd>Esc</kbd> overzicht</p>')
    js = ("<script>function tg(id){document.querySelectorAll('.tstep')"
          ".forEach(function(e){e.classList.remove('on')});"
          "document.getElementById(id).classList.add('on');}"
          "(function(){function typing(){var a=document.activeElement;"
          "return a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);}"
          "function startOn(){return document.getElementById('t-start').classList.contains('on');}"
          "document.addEventListener('keydown',function(e){"
          "if(e.key==='Escape'){window.location='/triage';return;}"
          "if(typing())return;"
          "if(e.key==='ArrowLeft'){e.preventDefault();"
          "if(startOn()){window.location='/triage';}else{tg('t-start');}}"
          "else if(startOn()&&e.key==='1'){tg('t-tac');}"
          "else if(startOn()&&e.key==='2'){tg('t-gov');}"
          "else if(startOn()&&e.key==='3'){tg('t-oordeel');}});})();</script>")
    inner = (f'{head}{_banner(msg)}{card}'
             f'{step0}{step_tac}{step_proj}{step_give}{step_ask}{step_gov}{step_oordeel}'
             f'{skip}</div>{js}<style>{_TRIAGE_CSS}</style>')
    return _page("Spanningen verwerken", inner)


def render_roloverleg_overview(items: list, agenda_all: list, roles: list,
                               token: str, msg=None) -> str:
    """Roloverleg-agenda: de voorstellen die op behandeling wachten. Behandel er één, voeg er een
    toe, of sluit het overleg (de aangenomen voorstellen worden dan doorgevoerd)."""
    head = ('<div class="tg-wrap"><p><a href="/">← cockpit</a></p>'
            '<h1>🏛️ Roloverleg</h1>')
    n_consent = sum(1 for i in agenda_all if i.get("status") == "consented")
    role_opts = "".join(f'<option value="{_e(r)}">{_e(r)}</option>' for r in roles)
    add_form = (
        '<details><summary style="cursor:pointer;font-weight:700;margin:.6rem 0">'
        '➕ Zelf een voorstel toevoegen</summary>'
        f'<form method="post" action="/action" style="padding:.4rem 0">'
        f'<input type="hidden" name="csrf" value="{_e(token)}">'
        f'<input type="hidden" name="next" value="/roloverleg">'
        f'<div class="tg-meta">Voor welke rol?</div>'
        f'<select name="owner" class="tg-in">{role_opts}'
        f'<option value="__new__">➕ nieuwe rol</option></select>'
        '<textarea name="info" class="tg-in" rows="2" '
        'placeholder="de accountability (begint met de -en-vorm), of purpose bij een nieuwe rol">'
        '</textarea>'
        '<input type="text" name="reason" class="tg-in" placeholder="reden / aanleiding">'
        '<button class="bigbtn go" type="submit" name="action" value="rov_add">'
        '➕ Op de agenda zetten</button></form></details>')
    end_form = (
        f'<form method="post" action="/action" style="margin-top:.6rem">'
        f'<input type="hidden" name="csrf" value="{_e(token)}">'
        f'<input type="hidden" name="next" value="/roloverleg">'
        f'<button class="bigbtn go" type="submit" name="action" value="rov_end">'
        f'✓ Einde roloverleg — {n_consent} aangenomen voorstel(len) doorvoeren</button></form>')
    if not items:
        body = ('<div class="tg-card"><h2>Lege agenda 🎉</h2>'
                '<p class="muted">Geen voorstellen om te behandelen. Governance-keuzes uit de '
                'triage komen hier terecht.</p></div>' + add_form)
        return _page("Roloverleg",
                     f'{head}{_banner(msg)}{body}</div><style>{_TRIAGE_CSS}</style>')
    rows = []
    for i, it in enumerate(items, 1):
        kind = "nieuwe rol" if it["kind"] == "add_role" else f"rol '{it['role_id']}' uitbreiden"
        badge = (' <span class="tg-wacht">⚠ vorige keer schadelijk</span>'
                 if it["status"] == "objected" else
                 (' <span class="tg-wacht">✓ aangenomen</span>'
                  if it["status"] == "consented" else ""))
        rows.append(
            f'<a class="tg-item" href="/roloverleg?iid={_e(it["id"])}">'
            f'<span class="tg-item-n">{i}</span>'
            f'<span class="tg-item-body"><b>{_e(it["title"])}</b>{badge}'
            f'<small>{_e(kind)} · door {_e(it.get("by",""))}</small></span>'
            f'<span class="tg-go">behandel →</span></a>')
    body = (f'<p class="tg-meta">{len(items)} voorstel(len) op de agenda. Behandel er één, '
            f'of sluit het overleg.</p><div class="tg-list">{"".join(rows)}</div>'
            f'{end_form}{add_form}')
    return _page("Roloverleg",
                 f'{head}{_banner(msg)}{body}</div><style>{_TRIAGE_CSS}</style>')


def render_roloverleg(item: dict, role_snapshot: dict | None, issues: list,
                      token: str, msg=None) -> str:
    """Eén voorstel behandelen: huidige rol + voorgestelde wijziging + reden, de Secretaris-check,
    je reactie (→ AI past aan), en consent of schadelijk."""
    head = ('<div class="tg-wrap"><p><a href="/roloverleg">← agenda</a> · '
            '<a href="/">cockpit</a></p><h1>🏛️ Voorstel behandelen</h1>')
    ch = item.get("change", {})
    accs = ch.get("add_accountabilities", [])
    if item["kind"] == "add_role":
        wijziging = (f'<b>Nieuwe rol:</b> {_e(item["role_id"])}<br>'
                     f'<b>Purpose:</b> {_e(ch.get("purpose",""))}'
                     + (f'<br><b>Eerste accountability:</b> {_e(accs[0])}' if accs else ""))
        huidig = '<p class="muted">Deze rol bestaat nog niet — dit is een voorstel voor een nieuwe rol.</p>'
    else:
        wijziging = ('<b>Rol uitbreiden:</b> ' + _e(item["role_id"]) + '<br>'
                     + '<b>Toe te voegen accountability:</b> '
                     + "; ".join(_e(a) for a in accs))
        if role_snapshot:
            al = "".join(f"<li>{_e(a)}</li>" for a in role_snapshot.get("accountabilities", [])) \
                 or "<li class=muted>nog geen</li>"
            huidig = (f'<b>{_e(item["role_id"])}</b> — {_e(role_snapshot.get("purpose",""))}'
                      f'<ul style="margin:.3rem 0">{al}</ul>')
        else:
            huidig = '<p class="muted">Rol niet gevonden in de records.</p>'
    # Secretaris-check
    if not issues:
        sec = '<div class="tg-dlg">📋 <b>Secretaris:</b> in orde — volledig, geen botsing.</div>'
    else:
        lis = "".join(
            f'<li>{"🔴" if i["level"]=="blok" else "🟡"} {_e(i["msg"])}</li>' for i in issues)
        sec = ('<div class="tg-dlg">📋 <b>Secretaris ziet aandachtspunten:</b>'
               f'<ul style="margin:.3rem 0">{lis}</ul></div>')
    react_log = ""
    for r in item.get("reactions", []):
        react_log += f'<div class="tg-dlg">🙋 <b>jij:</b> {_e(r.get("text",""))}</div>'
    common = (f'<input type="hidden" name="csrf" value="{_e(token)}">'
              f'<input type="hidden" name="iid" value="{_e(item["id"])}">')
    react_form = (
        f'<form method="post" action="/action">{common}'
        f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
        '<div class="tg-q">Vraag of reactie?</div>'
        '<textarea name="reason" class="tg-in" rows="2" '
        'placeholder="bijv. te breed, of: voeg X toe"></textarea>'
        '<button class="bigbtn" type="submit" name="action" value="rov_react">'
        '🤖 AI past voorstel aan</button></form>')
    decide = (
        f'<form method="post" action="/action" style="margin-top:.5rem">{common}'
        f'<input type="hidden" name="next" value="/roloverleg">'
        '<div class="tg-opts">'
        '<button class="bigbtn go" type="submit" name="action" value="rov_consent">'
        '✓ Consent<small>geen bezwaar — wordt aangenomen en bij einde overleg doorgevoerd</small>'
        '</button>'
        '<button class="bigbtn warn" type="submit" name="action" value="rov_object">'
        '⚠ Schadelijk<small>blijft staan, lossen we de volgende keer op</small></button>'
        '</div></form>')
    card = (f'<div class="tg-card"><div class="tg-meta">Voorstel · door {_e(item.get("by",""))} · '
            f'status {_e(item.get("status",""))}</div>'
            f'<h2>{_e(item["title"])}</h2>'
            f'<div style="margin:.3rem 0"><b>Huidige situatie</b><br>{huidig}</div>'
            f'<div style="margin:.3rem 0">{wijziging}</div>'
            f'<div class="muted"><b>Reden:</b> {_e(item.get("reason",""))}</div>'
            f'{sec}{react_log}</div>')
    inner = (f'{head}{_banner(msg)}{card}{react_form}{decide}'
             '<div class="tg-skip"><a class="muted" href="/roloverleg">← terug naar de agenda</a>'
             '</div></div><style>' + _TRIAGE_CSS + '</style>')
    return _page("Voorstel behandelen", inner)


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


def _render_house_rules(rules: list) -> str:
    """Huis-regels (constraints uit triage): de vaste feiten/eisen die het dorp respecteert."""
    if not rules:
        return ('<p class="muted">Nog geen huis-regels. Wijs een kans af met "onthoud als '
                'huis-regel" en het dorp leert de constraint.</p>')
    items = "".join(f'<li>{_e(r.get("text", ""))} <span class="muted">'
                    f'({_e(r.get("source", ""))})</span></li>' for r in rules)
    return f'<details open><summary>📏 Huis-regels ({len(rules)})</summary><ul>{items}</ul></details>'


def _render_backlog(backlog: list, north_star: dict, token: str | None = None,
                    roles: list | None = None) -> str:
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
        def _dialogue(x):
            """Toon de vraag-antwoord-dialoog met de rol (mens vraagt, rol antwoordt in de puls)."""
            dlg = x.get("dialogue") or []
            if not dlg:
                return ""
            rows = []
            for d in dlg:
                q = f'<div style="margin-top:.3rem">🙋 <b>jij:</b> {_e(d.get("q",""))}</div>'
                if d.get("answered"):
                    a = (f'<div>💬 <b>{_e(d.get("by") or "rol")}:</b> {_e(d.get("a",""))}</div>')
                else:
                    a = ('<div class="muted">⏳ <i>wachten op antwoord (komt in de volgende puls)</i></div>')
                rows.append(q + a)
            return (f'<div style="border-left:3px solid var(--border);padding-left:.6rem;'
                    f'margin:.4rem 0;font-size:.85rem">{"".join(rows)}</div>')

        def _kans_cell(x):
            kl = _kind_label.get(x["kind"], x["kind"])
            wacht = (' <span class="badge" style="background:var(--cream-3);'
                     'border:1px solid var(--border);border-radius:6px;padding:0 .3rem;'
                     'font-size:.7rem">⏳ wachten op antwoord</span>') if x.get("awaiting") else ""
            head = (f'<b>{_e(x["title"])}</b> <span class="muted">{kl}'
                    f'{(" · door " + _e(x["by"])) if x.get("by") else ""}</span>{wacht}')
            wat = f'<div style="margin:.2rem 0">{_e(x.get("wat", ""))}</div>' if x.get("wat") else ""
            waarom = (f'<div class="muted"><b>Waarom:</b> {_e(x["waarom"])}</div>'
                      if x.get("waarom") else "")
            return head + wat + waarom + _dialogue(x)

        _roles = roles or []

        def _acts(x):
            """Triage volgens Holacracy: kies Tactical (project / informatie) of Governance
            (voorstel — AI bepaalt nieuwe rol vs. uitbreiden). 'Klaar' sluit het item. Het
            enige 'weg' is jouw source-oordeel: past niet binnen de visie (wordt huis-regel)."""
            if not (x.get("approvable") and token):
                return '<span class="muted">—</span>'
            by = x.get("by", "")
            inp = 'padding:.25rem .4rem;border:1px solid var(--border);border-radius:6px'
            iid = _e(x["iid"])
            common = (f'<input type="hidden" name="csrf" value="{_e(token)}">'
                      f'<input type="hidden" name="iid" value="{iid}">'
                      f'<input type="hidden" name="anchor" value="kans-{iid}">')
            owner_opts = "".join(
                f'<option value="{_e(r)}"{" selected" if r == by else ""}>{_e(r)}</option>'
                for r in _roles) or f'<option value="{_e(by)}">{_e(by)}</option>'
            gov_opts = ('<option value="__auto__">🤖 laat AI kiezen (nieuw of uitbreiden)</option>'
                        + owner_opts + '<option value="__new__">➕ nieuwe rol</option>')
            ta = (f'width:100%;box-sizing:border-box;margin:.2rem 0;{inp}')
            # ── Tactical: project (voor een rol) óf informatie (geven / vragen) ──
            tactical = (
                f'<details><summary style="cursor:pointer">⚙️ Tactical</summary>'
                f'<div style="padding:.3rem 0 .2rem">'
                # project
                f'<form method="post" action="/action" style="margin-bottom:.4rem">{common}'
                f'<div style="font-size:.8rem;margin-bottom:.15rem"><b>Project</b> voor rol '
                f'(AI formuleert de uitkomst):</div>'
                f'<select name="owner" style="{inp}">{owner_opts}</select> '
                f'<button class="btn ok" type="submit" name="action" value="tac_project">'
                f'+ project</button></form>'
                # informatie geven
                f'<form method="post" action="/action" style="margin-bottom:.4rem">{common}'
                f'<div style="font-size:.8rem;margin-bottom:.15rem"><b>Informatie geven</b> '
                f'(landt in de kennisbank):</div>'
                f'<textarea name="info" rows="2" placeholder="wat wil je het dorp meegeven?" '
                f'style="{ta}"></textarea>'
                f'<button class="btn" type="submit" name="action" value="tac_info_give">'
                f'+ 📚 kennis</button></form>'
                # informatie vragen
                f'<form method="post" action="/action">{common}'
                f'<div style="font-size:.8rem;margin-bottom:.15rem"><b>Informatie vragen</b> '
                f'(de rol antwoordt in de puls):</div>'
                f'<textarea name="question" rows="2" placeholder="bijv. ik snap dit voorstel niet, wat bedoel je?" '
                f'style="{ta}"></textarea>'
                f'<button class="btn" type="submit" name="action" value="tac_info_ask">'
                f'❓ vraag de rol</button></form>'
                f'</div></details>')
            # ── Governance: een voorstel (AI bepaalt nieuw vs. uitbreiden) ──
            governance = (
                f'<details><summary style="cursor:pointer">🏛️ Governance</summary>'
                f'<div style="padding:.3rem 0 .2rem">'
                f'<form method="post" action="/action">{common}'
                f'<div style="font-size:.8rem;margin-bottom:.15rem"><b>Voorstel</b> — '
                f'nieuwe rol of een bestaande uitbreiden:</div>'
                f'<select name="owner" style="{inp}">{gov_opts}</select> '
                f'<button class="btn" type="submit" name="action" value="gov_proposal">'
                f'🏛️ maak voorstel</button></form>'
                f'</div></details>')
            # ── Klaar + (enige weg) past niet binnen de visie ──
            klaar = (
                f'<form method="post" action="/action" style="display:inline">{common}'
                f'<button class="btn ok" type="submit" name="action" value="tension_done">'
                f'✓ klaar</button></form>')
            visie = (
                f'<details style="margin-top:.3rem"><summary style="cursor:pointer;'
                f'font-size:.8rem;color:var(--gray)">past niet binnen de visie</summary>'
                f'<form method="post" action="/action" style="padding-top:.2rem">{common}'
                f'<input type="text" name="reason" placeholder="waarom past dit niet?" '
                f'style="width:100%;box-sizing:border-box;margin-bottom:.2rem;{inp}">'
                f'<label style="font-size:.8rem;display:block;margin-bottom:.3rem">'
                f'<input type="checkbox" name="remember" value="1"> onthoud als huis-regel</label>'
                f'<button class="btn danger" type="submit" name="action" value="vision_drop">'
                f'✗ verwijderen</button></form></details>')
            return (f'{tactical}{governance}'
                    f'<div style="margin-top:.4rem">{klaar}</div>{visie}')

        def _row(x):
            anchor = f' id="kans-{_e(x["iid"])}"' if x.get("iid") else ""
            return (f'<tr{anchor}><td>{_kans_cell(x)}</td>'
                    f'<td>{_e(format_business_case(x.get("business_case")))}</td>'
                    f'<td><b>{_e(x.get("value"))}</b></td>'
                    f'<td style="min-width:240px">{_acts(x)}</td></tr>')
        rows = "".join(_row(x) for x in backlog)
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


def _render_watcher_dashboard(shop: dict, visitors_7d=None) -> str:
    """Website Watcher-dashboard: verkoopindicatoren uit Shopify (paren verkocht, orders, omzet,
    AOV, top landen/producten) + conversie (orders 7d ÷ bezoekers 7d uit Plausible). Leeg → hint."""
    if not shop or not shop.get("ok"):
        return ('<h2>📊 Website Watcher — verkoop</h2>'
                '<p class="muted">Nog geen Shopify-data. Draai <code>village shopify</code> '
                '(vereist SHOPIFY_STORE + Client ID/secret in .env) of <code>./refresh.sh</code>.</p>')
    cur = _e(shop.get("currency", ""))
    wd = shop.get("window_days", 0)
    periode = "hele historie" if not wd else f"laatste {wd} dagen"
    base = [
        ("👟", _fmt_int(shop.get("pairs_sold", 0)), "paren verkocht"),
        ("🧾", _fmt_int(shop.get("orders", 0)), "orders"),
        ("💶", f'{_fmt_int(round(shop.get("revenue", 0)))} {cur}'.strip(), "omzet"),
        ("📦", f'{shop.get("aov", 0)} {cur}'.strip(), "gem. orderwaarde"),
    ]
    # Gemiddelden per maand — vooral nuttig bij 'hele historie' (rustig beeld i.p.v. een venster).
    if shop.get("avg_pairs_month"):
        base.append(("📅", _fmt_int(round(shop["avg_pairs_month"])), "gem. paren/maand"))
        if shop.get("avg_revenue_month"):
            base.append(("📈", f'{_fmt_int(round(shop["avg_revenue_month"]))} {cur}'.strip(),
                         "gem. omzet/maand"))
    # Conversie: orders (laatste 7 dagen) ÷ bezoekers (laatste 7 dagen, Plausible).
    if visitors_7d:
        base.append(("👣", _fmt_int(visitors_7d), "bezoekers (7d)"))
        o7 = shop.get("orders_7d")
        if o7 is not None:
            conv = round(100 * o7 / visitors_7d, 2) if visitors_7d else 0.0
            base.append(("🎯", f"{conv}%", "conversie (7d)"))
    tiles = "".join(
        f'<div class="kpi"><div class="kpi-n">{ico} {val}</div>'
        f'<div class="kpi-l">{_e(label)}</div></div>'
        for ico, val, label in base)
    def _pairs(rows, lbl):
        if not rows:
            return ""
        lis = "".join(f"<li>{_e(k)} <span class=muted>· {_e(v)}</span></li>" for k, v in rows)
        return f'<div><b>{lbl}</b><ul style="margin:.2rem 0">{lis}</ul></div>'
    land = _pairs(shop.get("by_country", []), "Orders per land")
    prod = _pairs(shop.get("top_products", []), "Topproducten (paren)")
    pages = _pairs(shop.get("top_landing_pages", []), "Via landingspagina → paren")
    chan = _pairs(shop.get("channels", []), "Kanaal → orders")
    kw = _pairs(shop.get("top_keywords", []), "UTM-term (campagne) → paren")
    cols = (f'<div style="display:flex;gap:1.4rem;flex-wrap:wrap;font-size:.85rem">'
            f'{land}{prod}{chan}{pages}{kw}</div>' if (land or prod or pages or chan) else "")
    sinds = (f' <span class="muted">· sinds {_e(shop.get("first_order_date"))}</span>'
             if not wd and shop.get("first_order_date") else "")
    return (f'<h2>📊 Website Watcher — verkoop ({periode}){sinds}</h2>'
            f'<div class="kpis">{tiles}</div>{cols}')


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
    # done = klaar, future = geparkeerd, draft = wacht nog op je akkoord: uit het actieve bord.
    _parked = ("done", "future", "draft")
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

    # Concept-projecten: door triage aangemaakt, wachten op jouw akkoord vóór ze op het
    # bord van de rol komen. Je ziet eerst de (AI-)formulering en keurt goed / past aan / gooit weg.
    from nooch_village.business_case import format_business_case as _fbc
    drafts = snap.get("project_drafts", [])
    drows = []
    for p in drafts:
        pid = p.get("id")
        acts = ('<span class="muted">—</span>' if not writable else
                f'<form method="post" action="/action" style="display:inline">'
                f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
                f'<input type="hidden" name="iid" value="{_e(pid)}">'
                f'<button class="btn ok" type="submit" name="action" value="proj_approve">'
                f'✓ goedkeuren</button></form> '
                f'<a class="btn" href="/project?pid={_e(pid)}">✎ aanpassen</a> '
                f'<form method="post" action="/action" style="display:inline">'
                f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
                f'<input type="hidden" name="iid" value="{_e(pid)}">'
                f'<button class="btn danger" type="submit" name="action" value="proj_discard">'
                f'✗ weggooien</button></form>')
        drows.append(
            f'<tr><td><b>{_e(p.get("owner"))}</b></td>'
            f'<td>{_e(_scope(p))}</td>'
            f'<td>{_e(_fbc(p.get("business_case")))}</td>'
            f'<td>{acts}</td></tr>')
    drafts_block = ("" if not drows else
                    '<h2>📝 Concept-projecten — wacht op jouw akkoord</h2>'
                    '<p class="muted" style="font-size:.85rem;margin:.2rem 0">Door triage '
                    'voorgesteld (AI-geformuleerd). Goedkeuren zet het op het bord van de rol.</p>'
                    '<table><thead><tr><th>owner</th><th>uitkomst</th><th>business-case</th>'
                    f'<th>jouw oordeel</th></tr></thead><tbody>{"".join(drows)}</tbody></table>')

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
    _n_agenda = len(snap.get("agenda_open", []))
    _focus = (f' <a class="btn ok" href="/triage" style="margin-left:.4rem">▶ Verwerk in focus</a>'
              if _n_kansen else "")
    _rov = (f' <a class="btn" href="/roloverleg" style="margin-left:.4rem">🏛️ Roloverleg ({_n_agenda})</a>'
            if _n_agenda else "")
    if _n_agenda:
        _parts.append(f'{_n_agenda} op de roloverleg-agenda')
    _aan_jou = (f'<div class="aanjou"><b>📥 Aan jou:</b> {" · ".join(_parts)}{_focus}{_rov}</div>'
                if _parts else '<div class="aanjou">📥 <b>Aan jou:</b> niks openstaand 🎉</div>')

    inner = (
        f'<h1>NoochVille cockpit {badge}</h1>'
        f'<div class="bar">{_e(counts)} · gegenereerd {_e(_ts(snap.get("generated_at")))} · {hist}</div>'
        f'<style>.aanjou{{background:var(--yellow-light);border:1px solid var(--border);'
        f'border-radius:var(--radius);padding:.5rem .9rem;margin:.3rem 0 1rem;font-size:.95rem}}</style>'
        f'{_aan_jou}'
        f'{_banner(msg)}'
        f'{_render_digest(snap.get("digest", {}), snap.get("noochie_daily", {}))}'
        f'{_render_watcher_dashboard(snap.get("shopify", {}), snap.get("visitors_7d"))}'
        f'{_render_backlog(snap.get("backlog", []), snap.get("north_star", {}), csrf_token, [r["id"] for r in roster if not r["archived"]])}'
        f'<h2>Inbox</h2>{inbox_tbl}'
        f'{drafts_block}'
        f'<h2>Proces (projecten)</h2>{proj_tbl}'
        f'<h2>Kennis</h2>'
        f'{_render_house_rules(snap.get("house_rules", []))}'
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
        if st == "blocked_question":
            return "⏳ " + result.get("error", "")
        if st in ("escalated", "invalid"):
            return f"✗ Governance {st}: {result.get('reason', '')}"
        return "✗ " + (result.get("error") or result.get("reason") or "actie mislukt")
    _rov = {"reacted": "🤖 Voorstel aangepast op basis van je reactie.",
            "consented": "✓ Consent — wordt doorgevoerd bij einde roloverleg.",
            "objected": "⚠ Als schadelijk gemarkeerd — blijft staan voor de volgende keer.",
            "added": "➕ Voorstel op de agenda gezet."}
    if result.get("rov") in _rov:
        return _rov[result["rov"]]
    if result.get("rov") == "ended":
        return (f"🏛️ Roloverleg afgerond — {result.get('adopted', 0)} doorgevoerd, "
                f"{result.get('escalated', 0)} bleef staan.")
    if result.get("status") == "waiting":
        return ("⏳ Vraag geparkeerd — de rol beantwoordt 'm in de volgende puls "
                "(item blijft open).")
    if result.get("status") == "added":
        d = result.get("destination")
        tail = " — item blijft open, klik ✓ klaar als je tevreden bent."
        if d == "governance":
            gs = result.get("gov_status")
            if gs == "agendeerd":
                return ("🏛️ Op de roloverleg-agenda gezet en uit je triage gehaald — "
                        "behandel 'm in het roloverleg.")
            if gs == "adopted":
                return "➕ Governance: rol aangemaakt/uitgebreid (zie Roster)." + tail
            return f"➕ Governance: poort vraagt jouw oordeel ({result.get('gov_reason', '')})." + tail
        if d == "knowledge":
            return "➕ Toegevoegd aan de kennisbank (zie Inzichten)." + tail
        if result.get("draft"):
            return (f"📝 Concept-project voor {result.get('owner') or 'het dorp'} klaargezet — "
                    f"keur het goed bij 'Concept-projecten' om het op het bord te zetten." + tail)
        return f"➕ Project toegevoegd voor {result.get('owner') or 'het dorp'} (zie Proces)." + tail
    if result.get("status") == "done":
        return "✓ Spanning klaar — uit je inbox."
    _verdict_flash = {
        "praise": "👍 Genoteerd als goed denkwerk — het dorp leert: meer van dit.",
        "soft_reject": "🙂 Afgewezen (geen harde regel) — meegenomen als richting.",
        "not_now": "⏳ Nu niet — genoteerd als timing-signaal.",
        "elsewhere": "🌍 Buiten NoochVille belegd — uit je inbox, het dorp leert ervan."}
    if result.get("status") in _verdict_flash:
        return _verdict_flash[result["status"]]
    if result.get("status") == "rejected" and "title" in result:
        extra = " + onthouden als huis-regel" if result.get("constraint_learned") else ""
        return f"✗ Past niet binnen de visie — weg{extra} (het dorp leert van je reden)."
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
    # ── Triage volgens Holacracy: tactical (project/info) | governance | klaar | visie-weg ──
    if action == "tac_info_ask":
        # Vraag parkeren; de puls beantwoordt 'm gebundeld (geen LLM hier).
        return ask_role(inbox, iid, extra.get("question", ""))
    # Zachte oordeel-verdicts (trainingssignaal): leuk idee / zachte nee / nu niet / elders.
    if action in ("opp_praise", "opp_soft_reject", "opp_not_now", "opp_elsewhere"):
        from nooch_village.feedback import Feedback
        verdict = {"opp_praise": "praise", "opp_soft_reject": "soft_reject",
                   "opp_not_now": "not_now", "opp_elsewhere": "elsewhere"}[action]
        return decide_opportunity(inbox, iid, verdict, reason=reason,
                                  feedback=Feedback(os.path.join(dd, "feedback.json")))
    if action in ("tac_project", "tac_info_give", "gov_proposal",
                  "tension_done", "vision_drop"):
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        notes = NotesStore(os.path.join(dd, "notes.json"))
        from nooch_village.constraints import Constraints
        from nooch_village.feedback import Feedback
        constraints = Constraints(os.path.join(dd, "constraints.json"))
        records = Records(os.path.join(dd, "governance_records.json"))
        if action == "tension_done":
            return decide_opportunity(inbox, iid, "done", reason=reason)
        if action == "vision_drop":
            return decide_opportunity(
                inbox, iid, "reject", reason=reason,
                remember_constraint=bool(extra.get("remember")), constraints=constraints,
                feedback=Feedback(os.path.join(dd, "feedback.json")))
        if action == "tac_info_give":
            return decide_opportunity(inbox, iid, "add", destination="knowledge",
                                      info=extra.get("info", ""), notes=notes)
        if action == "gov_proposal":
            from nooch_village.governance_examples import GovernanceExamples, few_shot_block
            from nooch_village.roloverleg import Agenda
            ge = GovernanceExamples(os.path.join(dd, "governance_examples.json"))
            item = inbox.get(iid) or {}
            c = item.get("context") or {}
            query = (c.get("title") or item.get("subject", "")) + " " + c.get("wat", "")
            block = few_shot_block(ge, query, k=3)          # vertrouwelijke referentie (lokaal)
            owner = extra.get("owner", "")
            if owner == "__auto__":                         # AI bepaalt nieuw vs. uitbreiden
                owner = pick_governance_target(
                    [r.id for r in records.all()],
                    c.get("title") or item.get("subject", ""), c.get("wat", ""),
                    examples_block=block)
            # Governance gaat naar de roloverleg-AGENDA (niet direct doorvoeren).
            agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
            res = decide_opportunity(inbox, iid, "add", destination="governance",
                                     owner=owner, records=records, examples_block=block,
                                     agenda=agenda)
            # Doorgestuurd naar het roloverleg = uit je triage (geen openblijvend item).
            if res.get("gov_status") == "agendeerd":
                inbox.resolve(iid, "resolved", reason="doorgestuurd naar het roloverleg")
            return res
        # tac_project: AI formuleert de project-uitkomst (Holacracy), fail-closed → titel.
        # Het project wordt een CONCEPT (draft): je ziet 'm eerst en keurt 'm goed vóór hij
        # op het bord van de rol komt.
        item = inbox.get(iid) or {}
        c = item.get("context") or {}
        scope = formulate_project(c.get("title") or item.get("subject", ""),
                                  c.get("wat", ""), extra.get("owner", ""))
        return decide_opportunity(inbox, iid, "add", destination="project",
                                  owner=extra.get("owner", ""), scope_override=scope,
                                  project_status="draft", projects=projects)
    if action in ("rov_react", "rov_consent", "rov_object", "rov_add", "rov_end"):
        from nooch_village.roloverleg import (Agenda, amend_with_reaction, apply_consented,
                                              secretary_check)
        agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
        records = Records(os.path.join(dd, "governance_records.json"))
        if action == "rov_end":
            res = apply_consented(agenda, records)
            n_ok = sum(1 for r in res if r["status"] == "adopted")
            return {"ok": True, "rov": "ended", "adopted": n_ok,
                    "escalated": len(res) - n_ok}
        if action == "rov_add":
            owner = extra.get("owner", "")
            acc = (extra.get("info") or "").strip()
            new_role = owner in ("", "__new__")
            if not acc:
                return {"ok": False, "error": "geef de accountability of purpose op"}
            import re as _re2
            if new_role:
                rid = _re2.sub(r"\W+", "_", acc.lower())[:40].strip("_") or "nieuwe_rol"
                change = {"purpose": acc[:140], "add_accountabilities": [], "new_role_parent": "noochville"}
            else:
                rid, change = owner, {"add_accountabilities": [acc[:140]]}
            agenda.add(role_id=rid, kind="add_role" if new_role else "amend_role",
                       change=change, reason=reason, by="founder", title=acc[:60])
            return {"ok": True, "rov": "added"}
        # de overige acties werken op één item
        if action == "rov_consent":
            return {"ok": agenda.set_status(iid, "consented"), "rov": "consented"}
        if action == "rov_object":
            return {"ok": agenda.set_status(iid, "objected"), "rov": "objected"}
        # rov_react: reactie loggen + AI past voorstel aan (gegrond in de bank)
        from nooch_village.governance_examples import GovernanceExamples, few_shot_block
        item = agenda.get(iid)
        if item is None:
            return {"ok": False, "error": "voorstel niet gevonden"}
        agenda.react(iid, reason)
        ge = GovernanceExamples(os.path.join(dd, "governance_examples.json"))
        block = few_shot_block(ge, item.get("title", "") + " " + item.get("reason", ""), k=3)
        agenda.update_change(iid, amend_with_reaction(item, reason, examples_block=block))
        return {"ok": True, "rov": "reacted"}
    if action in ("proj_approve", "proj_discard"):
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        if action == "proj_approve":
            ok = projects.approve(iid)
            return {"ok": ok, "proj_status": "queued"} if ok \
                else {"ok": False, "error": "kon concept niet goedkeuren"}
        ok = projects.discard(iid)
        return {"ok": ok, "removed": iid} if ok \
            else {"ok": False, "error": "kon concept niet weggooien"}
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
            elif path == "/triage":
                snap = gather(data_dir)
                queue = [b for b in snap["backlog"] if b.get("approvable") and b.get("iid")]
                want = (qs.get("iid") or [""])[0]
                cur = next((b for b in queue if b["iid"] == want), None) if want else None
                if cur is None:
                    # Geen (geldig/openstaand) item gekozen → toon het overzicht van alle spanningen.
                    body = render_triage_overview(queue, csrf_token, msg=msg).encode("utf-8")
                else:
                    roles = [r["id"] for r in snap["roster"]
                             if not r["archived"] and r["type"] == "role"]
                    body = render_triage(cur, 1, len(queue), roles,
                                         csrf_token, msg=msg).encode("utf-8")
            elif path == "/roloverleg":
                dd = data_dir or _default_data_dir()
                from nooch_village.roloverleg import Agenda, secretary_check
                agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
                recs = Records(os.path.join(dd, "governance_records.json"))
                roles = [r.id for r in recs.all()
                         if not r.archived and r.type.value == "role"]
                want = (qs.get("iid") or [""])[0]
                item = agenda.get(want) if want else None
                if item is None:
                    body = render_roloverleg_overview(
                        agenda.open(), agenda.all(), roles, csrf_token, msg=msg).encode("utf-8")
                else:
                    rec = recs.get(item["role_id"])
                    snap = ({"purpose": rec.definition.purpose,
                             "accountabilities": list(rec.definition.accountabilities),
                             "domains": list(rec.definition.domains)} if rec else None)
                    body = render_roloverleg(
                        item, snap, secretary_check(item, recs), csrf_token, msg=msg).encode("utf-8")
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
                     "decision": (form.get("decision") or [""])[0],
                     "question": (form.get("question") or [""])[0],
                     "info": (form.get("info") or [""])[0],
                     "remember": (form.get("remember") or [""])[0]}
            result = _dispatch_action(data_dir, action, iid, reason, extra=extra)
            # 303 → verse GET. Rails keren terug naar de spanning (next), sluiten gaat home.
            # De uitkomst gaat als korte flash-banner mee in de query; een anchor brengt je
            # terug naar exact het item waar je was (geen sprong naar boven na een actie).
            nxt = (form.get("next") or ["/"])[0]
            if not nxt.startswith("/"):
                nxt = "/"
            anchor = (form.get("anchor") or [""])[0]
            sep = "&" if "?" in nxt else "?"
            nxt = f"{nxt}{sep}msg={urllib.parse.quote(_flash(result))}"
            if anchor and re.fullmatch(r"[A-Za-z0-9_\-]+", anchor):
                nxt = f"{nxt}#{anchor}"          # fragment ná de query (juiste URL-volgorde)
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
