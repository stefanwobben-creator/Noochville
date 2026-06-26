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
from nooch_village.news_distill import NewsProposals as _NewsProposals
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
    from nooch_village.roloverleg import Agenda, formalize_ripe_experiments
    _agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
    # Stollen: experimenten die ≥3x zijn uitgevoerd dragen zichzelf voor als accountability.
    formalize_ripe_experiments(projects, _agenda)
    agenda_open = _agenda.open()
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
            "name": getattr(d, "name", "") or rec.id,   # weergavenaam (na hernoemen) of het id
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

    # Attributie terugkoppelen: paren verkocht via een landingspagina toewijzen aan het doelwit-
    # woord dat bij die pagina hoort. Zo zie je per doelwit hoeveel verkoop het opleverde.
    _pages = shopify.get("top_landing_pages") or []
    if _pages:
        from nooch_village.attribution import attribute_keywords
        _doelwit = [r["word"] for r in lib if r.get("function") == "doelwit"]
        _kw_sales = attribute_keywords(_pages, _doelwit)
        for r in lib:
            if r.get("function") == "doelwit":
                r["sales_pairs"] = _kw_sales.get(r["word"], 0)

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
        "news_proposals": _NewsProposals(os.path.join(dd, "news_proposals.json")).pending(),
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
        f'<form method="post" action="/action" id="rovadd" style="padding:.4rem 0">'
        f'<input type="hidden" name="csrf" value="{_e(token)}">'
        f'<input type="hidden" name="next" value="/roloverleg">'
        f'<div class="tg-meta">Bestaande rol uitbreiden, of een nieuwe rol?</div>'
        f'<select name="owner" id="rovowner" class="tg-in">{role_opts}'
        f'<option value="__new__">➕ nieuwe rol</option></select>'
        # Velden alleen relevant bij een nieuwe rol (worden bij een bestaande rol genegeerd).
        '<div id="rovnew">'
        '<input name="rolnaam" class="tg-in" placeholder="naam van de nieuwe rol (bijv. Copywriter)">'
        '<input name="purpose" class="tg-in" placeholder="purpose — reden van bestaan (geen -en-vorm)">'
        '<input name="domein" class="tg-in" placeholder="domein (optioneel: waar deze rol exclusief over gaat)">'
        '</div>'
        '<div class="tg-meta" style="margin-top:.3rem">Accountabilities (één per regel, -en-vorm)</div>'
        '<textarea name="accs" id="rovaccs" class="tg-in" rows="3" '
        'placeholder="bijv. Schrijven van blogcopy voor de pillar-pagina&#10;Bewaken van de tone of voice"></textarea>'
        '<button type="button" class="bigbtn" onclick="rovSuggest()">🤖 AI: stel accountabilities voor</button>'
        '<div class="tg-meta" style="margin-top:.3rem">Welke spanning lost dit op? '
        '(Holacracy: een voorstel is altijd tension-driven)</div>'
        '<input type="text" name="reason" class="tg-in" placeholder="bijv. ik moet steeds zelf social posts schrijven en dat blijft liggen">'
        '<textarea name="voorbeeld" class="tg-in" rows="2" '
        'placeholder="concreet voorbeeld: laatst bleef de TikTok 3 weken stil omdat niemand de rol had"></textarea>'
        '<div class="tg-meta" style="margin-top:.3rem">Pas je een ÁNDERE rol aan? Zeg dan hoe '
        'aannemen jóuw eigen rol helpt (anders is de spanning ongeldig — Holacracy: from your role)</div>'
        '<input type="text" name="benefit" class="tg-in" '
        'placeholder="bijv. zonder deze accountability bij scout blijf ik als analist op data wachten">'
        '<button class="bigbtn go" type="submit" name="action" value="rov_add">'
        '➕ Op de agenda zetten</button></form></details>'
        '<script>function rovSuggest(){'
        "var own=document.getElementById('rovowner').value;"
        "var naam=document.querySelector('#rovadd [name=rolnaam]').value;"
        "var pur=document.querySelector('#rovadd [name=purpose]').value;"
        "var role=(own==='__new__')?(naam||'nieuwe rol'):own;"
        "var ta=document.getElementById('rovaccs');var prev=ta.value;ta.value='\\u23f3 AI denkt na...';"
        "fetch('/suggest_accountabilities?role='+encodeURIComponent(role)+'&purpose='+encodeURIComponent(pur))"
        ".then(function(r){return r.text();}).then(function(t){ta.value=(prev?prev+'\\n':'')+(t.trim()||'(geen suggestie)');})"
        ".catch(function(){ta.value=prev;alert('Suggestie mislukt (geen LLM?)');});}</script>")
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
    # Groepeer per voorstel (group): één regel per voorstel, ook als het meerdere rollen raakt.
    groups: dict[str, list] = {}
    for it in items:
        groups.setdefault(it.get("group") or it["id"], []).append(it)
    rows = []
    for i, (gid, gm) in enumerate(groups.items(), 1):
        head_it = gm[0]
        if len(gm) > 1:
            kind = f"{len(gm)} rollen: " + ", ".join(_e(m.get("role_id", "")) for m in gm)
            titel = _e(head_it.get("title", "")) + f' <span class="muted">(+{len(gm)-1} rol)</span>'
        else:
            kind = ("nieuwe rol" if head_it["kind"] == "add_role"
                    else ("🗑 rol verwijderen" if head_it["kind"] == "remove_role"
                          else f"rol '{head_it['role_id']}' uitbreiden"))
            titel = _e(head_it["title"])
        badge = (' <span class="tg-wacht">⚠ vorige keer schadelijk</span>'
                 if any(m["status"] == "objected" for m in gm) else
                 (' <span class="tg-wacht">✓ aangenomen</span>'
                  if all(m["status"] == "consented" for m in gm) else ""))
        rows.append(
            f'<a class="tg-item" href="/roloverleg?iid={_e(head_it["id"])}">'
            f'<span class="tg-item-n">{i}</span>'
            f'<span class="tg-item-body"><b>{titel}</b>{badge}'
            f'<small>{kind} · door {_e(head_it.get("by",""))}</small></span>'
            f'<span class="tg-go">behandel →</span></a>')
    body = (f'<p class="tg-meta">{len(groups)} voorstel(len) op de agenda. Behandel er één, '
            f'of sluit het overleg.</p><div class="tg-list">{"".join(rows)}</div>'
            f'{end_form}{add_form}')
    return _page("Roloverleg",
                 f'{head}{_banner(msg)}{body}</div><style>{_TRIAGE_CSS}</style>')


def render_roloverleg(item: dict, role_snapshot: dict | None, issues: list,
                      token: str, msg=None, group_members=None, roles=None) -> str:
    """Eén voorstel behandelen: huidige rol + voorgestelde wijziging + reden, de Secretaris-check,
    je reactie (→ AI past aan), en consent of schadelijk. `group_members` = alle rol-onderdelen van
    hetzelfde voorstel (GlassFrog: één voorstel kan meerdere rollen raken)."""
    head = ('<div class="tg-wrap"><p><a href="/roloverleg">← agenda</a> · '
            '<a href="/">cockpit</a></p><h1>🏛️ Voorstel behandelen</h1>')
    from nooch_village.roloverleg import tension_validity
    valid, invalid_reason = tension_validity(item)
    common = (f'<input type="hidden" name="csrf" value="{_e(token)}">'
              f'<input type="hidden" name="iid" value="{_e(item["id"])}">')
    # Verwijder-voorstel: aparte, sobere weergave (geen editor/diff). De Secretaris-check (Gate G3)
    # staat eronder; consent voert het bij einde overleg door, of escaleert als er kinderen/werk hangt.
    if item.get("kind") == "remove_role":
        if not issues:
            sec = ('<div class="tg-dlg">📋 <b>Secretaris:</b> geen blokkade gezien — bij einde '
                   'overleg wordt de rol gearchiveerd.</div>')
        else:
            lis = "".join(f'<li>{"🔴" if i["level"]=="blok" else "🟡"} {_e(i["msg"])}</li>' for i in issues)
            sec = ('<div class="tg-dlg">📋 <b>Secretaris ziet aandachtspunten:</b>'
                   f'<ul style="margin:.3rem 0">{lis}</ul></div>')
        rmcard = (f'<div class="tg-card" style="border-left:3px solid #c0392b">'
                  f'<div class="tg-meta">Voorstel · door {_e(item.get("by",""))} · '
                  f'status {_e(item.get("status",""))}</div>'
                  f'<h2>🗑 Rol verwijderen: {_e(item.get("title") or item.get("role_id"))}</h2>'
                  f'<div class="muted" style="margin-top:.2rem"><b>Lost deze spanning op:</b> '
                  f'{_e(item.get("reason","")) or "—"}</div>'
                  '<p class="muted" style="margin-top:.3rem">De rol wordt bij einde overleg '
                  'gearchiveerd en uit de ouder-cirkel gehaald. Heeft de rol nog werk of '
                  'onderliggende rollen, dan escaleert de Gate (G3) naar jou.</p></div>')
        decide = (
            f'<form method="post" action="/action" style="margin-top:.5rem">{common}'
            f'<input type="hidden" name="next" value="/roloverleg">'
            '<div class="tg-opts">'
            '<button class="bigbtn warn" type="submit" name="action" value="rov_consent">'
            '🗑 Consent — rol verwijderen<small>bij einde overleg doorgevoerd (Gate G3 bewaakt)</small>'
            '</button>'
            f'<button class="bigbtn" type="submit" name="action" value="rov_keep_role">'
            '↩ Toch niet verwijderen<small>terug naar een gewoon wijzig-voorstel</small></button>'
            '</div></form>')
        inner = (f'{head}{_banner(msg)}{rmcard}{sec}{decide}'
                 '<div class="tg-skip"><a class="muted" href="/roloverleg">← terug naar de agenda</a>'
                 '</div></div><style>' + _TRIAGE_CSS + '</style>')
        return _page("Rol verwijderen", inner)
    ch = item.get("change", {})
    accs = ch.get("add_accountabilities", [])
    accs_rm = ch.get("remove_accountabilities", [])
    doms_new = ch.get("add_domains", [])
    pur_new = ch.get("purpose")
    is_add = item["kind"] == "add_role"
    is_purpose = bool(pur_new) and not accs and not is_add
    snap = role_snapshot or {}
    cur_pur, cur_accs, cur_doms = snap.get("purpose", ""), snap.get("accountabilities", []), snap.get("domains", [])
    _GR = "background:var(--green-tint);color:var(--green-dark);border-radius:4px;padding:0 .25rem"
    _ST = "text-decoration:line-through;color:var(--gray)"
    _UL = 'list-style:none;padding:0;margin:.2rem 0;font-size:.86rem'
    _H = 'font-family:var(--font-display);font-weight:700;font-size:.8rem;color:var(--green-dark);margin-bottom:.2rem'

    def _accs_ul(keep, added, removed=()):
        items_ = "".join(
            (f'<li style="padding:.1rem 0;{_ST}">✗ {_e(a)}</li>' if a in removed
             else f'<li style="padding:.1rem 0">{_e(a)}</li>') for a in keep)
        items_ += "".join(f'<li style="padding:.1rem 0;{_GR}">✚ {_e(a)}</li>' for a in added)
        return f'<ul style="{_UL}">{items_ or "<li class=muted>geen</li>"}</ul>'

    # Huidige rol (links)
    if is_add:
        cur_html = '<p class="muted">Deze rol bestaat nog niet.</p>'
    else:
        cur_dom = (f'<div class="muted" style="margin-top:.2rem">Domeinen: {", ".join(_e(d) for d in cur_doms)}</div>'
                   if cur_doms else "")
        cur_html = (f'<div><b>Purpose:</b> {_e(cur_pur) or "<span class=muted>—</span>"}</div>'
                    f'<div style="margin-top:.2rem"><b>Accountabilities</b>{_accs_ul(cur_accs, [])}</div>{cur_dom}')

    # Na dit voorstel (rechts) — toevoegingen groen, gewijzigde purpose oud→nieuw
    dom_add = (f'<div style="margin-top:.2rem"><b>Domein:</b> <span style="{_GR}">✚ '
               f'{_e(", ".join(doms_new))}</span></div>' if doms_new else "")
    if is_add:
        after_html = (f'<div><b>Nieuwe rol:</b> {_e(item["role_id"])}</div>'
                      f'<div><b>Purpose:</b> <span style="{_GR}">{_e(pur_new or "")}</span></div>'
                      f'<div style="margin-top:.2rem"><b>Accountabilities</b>{_accs_ul([], accs)}</div>{dom_add}')
    elif is_purpose:
        after_html = (f'<div><b>Purpose:</b> <span style="{_ST}">{_e(cur_pur)}</span> '
                      f'→ <span style="{_GR}">{_e(pur_new)}</span></div>'
                      f'<div class="muted" style="margin-top:.2rem">Accountabilities ongewijzigd '
                      f'({len(cur_accs)})</div>')
    else:
        pur_line = (f'<div><b>Purpose:</b> <span style="{_ST}">{_e(cur_pur)}</span> → '
                    f'<span style="{_GR}">{_e(pur_new)}</span></div>' if pur_new and pur_new != cur_pur
                    else f'<div><b>Purpose:</b> {_e(cur_pur) or "<span class=muted>—</span>"}</div>')
        after_html = (f'{pur_line}'
                      f'<div style="margin-top:.2rem"><b>Accountabilities</b>'
                      f'{_accs_ul(cur_accs, accs, removed=accs_rm)}</div>{dom_add}')

    diff = ('<div style="display:flex;gap:1rem;flex-wrap:wrap;margin:.3rem 0">'
            f'<div style="flex:1 1 280px;min-width:0"><div style="{_H}">Huidige rol</div>{cur_html}</div>'
            f'<div style="flex:1 1 280px;min-width:0"><div style="{_H}">Na dit voorstel</div>{after_html}</div></div>')

    flip_btn = ""
    if not is_add:
        flip_lbl = ("↔ dit gaat eigenlijk over een accountability" if is_purpose
                    else "↔ dit gaat eigenlijk over de purpose")
        flip_btn = (
            f'<form method="post" action="/action" style="display:inline">'
            f'<input type="hidden" name="csrf" value="{_e(token)}">'
            f'<input type="hidden" name="iid" value="{_e(item["id"])}">'
            f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
            f'<button class="btn" type="submit" name="action" value="rov_flip_facet">'
            f'{flip_lbl}</button></form>')
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
        '<details style="margin-top:.4rem"><summary>🤖 Laat de AI een herziening voorstellen</summary>'
        f'<form method="post" action="/action" style="margin-top:.3rem">{common}'
        f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
        '<textarea name="reason" class="tg-in" rows="2" '
        'placeholder="beschrijf in gewone taal wat anders moet; de AI vult de velden hierboven"></textarea>'
        '<button class="bigbtn" type="submit" name="action" value="rov_react">'
        '🤖 Stel een herziening voor</button></form></details>')
    # Bij een accountability-voorstel: het ook nu meteen als EXPERIMENT (project) kunnen laten
    # doen door de indienende rol — een accountability is daarvoor niet nodig (purpose volstaat),
    # en pas na herhaalde uitvoering 'stolt' het tot accountability (rijpheidspoort).
    project_opt = ""
    if accs and not is_add:
        project_opt = (
            '<button class="bigbtn" type="submit" name="action" value="rov_to_project">'
            f'▶ Doe dit eerst als project<small>de rol \'{_e(item["role_id"])}\' voert het uit als '
            'omkeerbaar experiment; bij herhaling stolt het later tot accountability</small></button>')
    decide = (
        f'<form method="post" action="/action" style="margin-top:.5rem">{common}'
        f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
        '<div class="tg-opts">'
        '<button class="bigbtn go" type="submit" name="action" value="rov_consent">'
        '✓ Consent<small>geen bezwaar — wordt aangenomen en bij einde overleg doorgevoerd</small>'
        '</button>'
        f'{project_opt}'
        + ("" if valid else
           '<button class="bigbtn warn" type="submit" name="action" value="rov_invalid">'
           '⚖️ Spanning ongeldig — verwijderen<small>geen baat voor de eigen rol benoemd; '
           'direct van de agenda, zonder governance</small></button>')
        + '</div></form>')
    # Bezwaar toetsen volgens de handout (roldenken.nl/Holacracy): JIJ kiest per vraag het antwoord;
    # de uitkomst volgt uit je eigen antwoorden — de facilitator oordeelt niet over de inhoud.
    from nooch_village.roloverleg import _OBJ_QUESTIONS
    qrows = ""
    for spec in _OBJ_QUESTIONS:
        dep = spec.get("depends_on")
        sub = (f' data-dep="{dep[0]}" data-depval="{dep[1]}" style="display:none"') if dep else ""
        qrows += (
            f'<div class="objq"{sub}><div class="objq-t"><b>{_e(spec["label"])}</b> — {_e(spec["vraag"])}</div>'
            + (f'<div class="muted" style="font-size:.78rem">{_e(spec["hint"])}</div>' if spec.get("hint") else "")
            + f'<label class="objopt"><input type="radio" name="{spec["q"]}" value="left"> {_e(spec["left"])}</label>'
            f'<label class="objopt"><input type="radio" name="{spec["q"]}" value="right"> {_e(spec["right"])}</label>'
            '</div>')
    objection_form = (
        '<details style="margin-top:.5rem"><summary>⚠ Bezwaar? Toets het (4 vragen)</summary>'
        f'<form method="post" action="/action" style="margin-top:.4rem">{common}'
        f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
        '<textarea name="harm" class="tg-in" rows="2" '
        'placeholder="optioneel: beschrijf de schade — welke rol van jou wordt beperkt, en hoe?"></textarea>'
        f'{qrows}'
        '<button class="bigbtn warn" type="submit" name="action" value="rov_object" '
        'style="margin-top:.4rem">⚖️ Toets mijn bezwaar<small>geldig → blijft staan voor '
        'integratie · geen geldig bezwaar → je kunt alsnog consent geven</small></button>'
        '</form></details>'
        '<style>.objq{margin:.4rem 0;padding:.4rem .5rem;border:1px solid var(--border);'
        'border-radius:var(--radius)}.objq-t{margin-bottom:.2rem}.objopt{display:block;'
        'padding:.15rem 0;cursor:pointer}</style>'
        '<script>(function(){function sync(){document.querySelectorAll(".objq[data-dep]").forEach('
        'function(b){var d=b.getAttribute("data-dep"),v=b.getAttribute("data-depval");'
        'var c=document.querySelector("input[name="+d+"]:checked");'
        'b.style.display=(c&&c.value==v)?"block":"none";});}'
        'document.querySelectorAll(".objq input[type=radio]").forEach(function(r){'
        'r.addEventListener("change",sync);});sync();})();</script>')
    invalid_box = ("" if valid else
                   '<div class="tg-dlg" style="border-left:3px solid #c0392b;padding-left:.5rem">'
                   f'⚖️ <b>Facilitator:</b> deze spanning lijkt ongeldig — {_e(invalid_reason)}. '
                   'Een voorstel om een ándere rol te wijzigen mag direct van de agenda zonder '
                   'governance.</div>')
    # Eerder getoetst bezwaar (objection-test) tonen, met de vier criteria.
    obj = item.get("objection")
    obj_box = ""
    if obj:
        r = obj.get("result", {})
        steps_html = "".join(
            f'<li>{"✅" if s["ok"] else "❌"} <b>{_e(s["label"])}</b>: {_e(s.get("gekozen","—"))}</li>'
            for s in r.get("steps", []))
        steps_html = f'<ul style="margin:.3rem 0">{steps_html}</ul>' if steps_html else ""
        edge = "#27ae60" if r.get("valid") else "#c0392b"
        harm_line = (f'⚖️ <b>Bezwaar getoetst:</b> "{_e(obj.get("text",""))}"<br>'
                     if obj.get("text") else "⚖️ <b>Bezwaar getoetst</b><br>")
        obj_box = (f'<div class="tg-dlg" style="border-left:3px solid {edge};padding-left:.5rem">'
                   f'{harm_line}<b>{_e(r.get("summary",""))}</b>{steps_html}</div>')
    # Kop + context (spanning/voorbeeld/baat + eventuele status-bakens). De diff zit verderop
    # ingeklapt; het bewerkbare formulier is de hoofdweergave (GlassFrog-stijl).
    card = (f'<div class="tg-card"><div class="tg-meta">Voorstel · door {_e(item.get("by",""))} · '
            f'status {_e(item.get("status",""))}</div>'
            f'<h2>{_e(item["title"])}</h2>'
            f'<div class="muted" style="margin-top:.2rem"><b>Lost deze spanning op:</b> {_e(item.get("reason","")) or "—"}</div>'
            + (f'<div class="muted" style="margin-top:.15rem"><b>Concreet voorbeeld:</b> '
               f'{_e(item.get("example",""))}</div>' if item.get("example") else "")
            + (f'<div class="muted" style="margin-top:.15rem"><b>Helpt mijn eigen rol:</b> '
               f'{_e(item.get("benefit",""))}</div>' if item.get("benefit") else "")
            + invalid_box + obj_box + react_log + '</div>')
    # De diff blijft beschikbaar als ingeklapte referentie ('wat verandert er t.o.v. nu').
    diff_block = (f'<details style="margin:.4rem 0"><summary>📋 Wijzigingen t.o.v. nu</summary>'
                  f'{diff}{(("<div style=margin:.3rem0>" + flip_btn + "</div>") if flip_btn else "")}'
                  '</details>')
    # GlassFrog-stijl: direct bewerkbare velden, voorgevuld met de 'na dit voorstel'-stand.
    if is_add:
        ed_naam, ed_pur = (item.get("title") or item.get("role_id", "")), (pur_new or "")
        ed_accs_list, ed_doms_list = list(accs), list(doms_new)
        naam_attr = ""
    else:
        ed_naam = ch.get("rename") or snap.get("name") or item.get("role_id", "")
        ed_pur = pur_new or cur_pur or ""
        doms_rm = ch.get("remove_domains", [])
        ed_accs_list = [a for a in cur_accs if a not in accs_rm] + list(accs)
        ed_doms_list = [d for d in cur_doms if d not in doms_rm] + list(doms_new)
        naam_attr = ""
    _ta = lambda xs: _e("\n".join(xs))
    editor = (
        '<details open style="margin-top:.5rem"><summary>✏️ Rol bewerken — naam, purpose, '
        'accountabilities &amp; domeinen (dit is het voorstel)</summary>'
        f'<form method="post" action="/action" style="margin-top:.4rem">{common}'
        f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
        f'<div style="{_H}">Naam</div>'
        f'<input name="ed_naam" class="tg-in" value="{_e(ed_naam)}"{naam_attr}>'
        f'<div style="{_H};margin-top:.4rem">Purpose (reden van bestaan, geen -en-vorm)</div>'
        f'<textarea name="ed_purpose" class="tg-in" rows="2">{_e(ed_pur)}</textarea>'
        f'<div style="{_H};margin-top:.4rem">Accountabilities (één per regel, -en-vorm)</div>'
        f'<textarea name="ed_accs" class="tg-in" rows="5">{_ta(ed_accs_list)}</textarea>'
        f'<div style="{_H};margin-top:.4rem">Domeinen (één per regel, optioneel)</div>'
        f'<textarea name="ed_domeinen" class="tg-in" rows="2">{_ta(ed_doms_list)}</textarea>'
        '<button class="bigbtn go" type="submit" name="action" value="rov_edit" '
        'style="margin-top:.4rem">💾 Voorstel opslaan<small>werkt de wijziging bij vanuit deze '
        'velden; de Secretaris hertoetst</small></button></form>'
        + ("" if is_add else
           f'<form method="post" action="/action" style="margin-top:.4rem">{common}'
           f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
           '<button class="btn danger" type="submit" name="action" value="rov_remove" '
           'onclick="return confirm(\'Dit voorstel omzetten naar: deze rol verwijderen?\')">'
           '🗑 Stel voor deze rol te verwijderen</button></form>')
        + '</details>')
    # GlassFrog: één voorstel kan meerdere rollen raken. Toon de andere rol-onderdelen + een knop
    # om een rol toe te voegen aan dit voorstel, en om het hele voorstel in één keer aan te nemen.
    members = group_members or [item]
    gid = item.get("group") or item["id"]
    group_block = ""
    if members:
        rows = ""
        for m in members:
            here = m["id"] == item["id"]
            kindlbl = "nieuwe rol" if m["kind"] == "add_role" else "wijzigen"
            label = _e(m.get("title") or m.get("role_id") or "rol")
            cell = (f'<b>{label}</b>' if here else
                    f'<a href="/roloverleg?iid={_e(m["id"])}">{label}</a>')
            rows += (f'<li style="padding:.15rem 0">{cell} '
                     f'<span class="muted">· {kindlbl} · {_e(m.get("status",""))}'
                     f'{" · nu open" if here else ""}</span></li>')
        # `roles` is een lijst rol-ids (strings); ondersteun ook dict-vorm voor de zekerheid.
        def _rid(r): return r["id"] if isinstance(r, dict) else r
        role_opts = "".join(
            f'<option value="{_e(_rid(r))}">{_e(_rid(r))}</option>' for r in (roles or []))
        add_to = (
            f'<form method="post" action="/action" style="margin-top:.3rem">{common}'
            f'<input type="hidden" name="next" value="/roloverleg?iid={_e(item["id"])}">'
            f'<input type="hidden" name="group" value="{_e(gid)}">'
            f'<select name="g_owner" class="tg-in"><option value="__new__">➕ nieuwe rol</option>'
            f'{role_opts}</select>'
            '<input name="g_naam" class="tg-in" placeholder="naam (alleen bij nieuwe rol)">'
            '<button class="btn" type="submit" name="action" value="rov_group_add">'
            '➕ rol toevoegen aan dit voorstel</button></form>')
        if len(members) <= 1:
            # Eén rol = de simpele standaard. Geen apart blok; alleen een rustige uitklapper om er
            # eventueel een rol bij te betrekken (Duolingo: geen ruis tot je het nodig hebt).
            group_block = (
                '<details style="margin-top:.4rem"><summary>➕ Nog een rol bij dit voorstel '
                'betrekken</summary>' + add_to + '</details>')
        else:
            accept_all = (
                f'<form method="post" action="/action" style="margin-top:.3rem">{common}'
                f'<input type="hidden" name="next" value="/roloverleg">'
                f'<input type="hidden" name="group" value="{_e(gid)}">'
                '<button class="bigbtn go" type="submit" name="action" value="rov_group_consent">'
                f'✓ Neem hele voorstel aan ({len(members)} rollen)<small>consent op alle '
                'rol-onderdelen tegelijk</small></button></form>')
            group_block = (
                f'<div class="tg-card" style="margin-top:.5rem"><div style="{_H}">'
                f'📦 Dit voorstel — {len(members)} rollen</div>'
                f'<ul style="list-style:none;padding:0;margin:.2rem 0">{rows}</ul>'
                f'{add_to}{accept_all}</div>')
    # UX (Duolingo + GlassFrog): formulier is de held; secundaire dingen ingeklapt; ONE duidelijke
    # beslis-zone onderaan (consent groot, bezwaar als rustige tweede stap).
    beslis = (f'<div class="tg-card" style="margin-top:.6rem"><div style="{_H}">Beslis</div>'
              f'{decide}{objection_form}</div>')
    secondair = (f'<details style="margin-top:.4rem"><summary>🔧 Meer opties '
                 '(AI-herziening, wijzigingen t.o.v. nu)</summary>'
                 f'{react_form}{diff_block}</details>')
    inner = (f'{head}{_banner(msg)}{card}{editor}{sec}{group_block}{secondair}{beslis}'
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
    # Deliverable / voortgang die de rol (autonoom of via het projectbord) opleverde.
    deliverable = ""
    if p.get("progress"):
        deliverable = (f'<h2>Deliverable / voortgang</h2>'
                       f'<div class="tension" style="white-space:pre-wrap">{_e(p.get("progress"))}</div>')
    if p.get("outcome"):
        deliverable += (f'<h2>Uitkomst (afgerond)</h2>'
                        f'<div class="tension">{_e(p.get("outcome"))}</div>')
    hyp = (f'<p class="muted"><b>Hypothese:</b> {_e(p.get("hypothesis"))}</p>'
           if p.get("hypothesis") else "")
    # Gesprek met de rol (WhatsApp-stijl): rol links, jij rechts. Bron: de log (val terug op de
    # losse comments + laatste voortgang voor oude projecten zonder log).
    chat_log = list(p.get("log") or [])
    if not chat_log:
        if p.get("progress"):
            chat_log.append({"who": "rol", "text": p["progress"]})
        for c in p.get("comments", []):
            chat_log.append({"who": "mens", "text": c.get("text", "")})
    owner_name = _e(p.get("owner", "rol"))
    bubbles = ""
    for m in chat_log:
        mens = m.get("who") == "mens"
        side = "flex-end" if mens else "flex-start"
        bg = "var(--green-tint)" if mens else "var(--surface)"
        who = "jij" if mens else owner_name
        bubbles += (
            f'<div style="display:flex;justify-content:{side};margin:.25rem 0">'
            f'<div style="max-width:78%;background:{bg};border:1px solid var(--border);'
            f'border-radius:12px;padding:.45rem .7rem">'
            f'<div class="muted" style="font-size:.7rem;margin-bottom:.1rem">{who}</div>'
            f'<div style="white-space:pre-wrap;font-size:.9rem">{_e(m.get("text",""))}</div></div></div>')
    if not bubbles:
        bubbles = ('<p class="muted" style="font-size:.85rem">Nog geen gesprek. Stuur de rol een '
                   'bericht om bij te sturen — de rol leest het mee en pakt het project opnieuw op.</p>')
    comments = (
        '<h2>💬 Gesprek met de rol</h2>'
        f'<div style="border:1px solid var(--border);border-radius:var(--radius);'
        f'background:var(--sand);padding:.6rem;max-height:340px;overflow-y:auto">{bubbles}</div>'
        '<form method="post" action="/action" class="pf" style="margin-top:.5rem">'
        f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
        f'<input type="hidden" name="iid" value="{_e(pid)}">'
        '<input type="hidden" name="action" value="proj_comment">'
        f'<input type="hidden" name="next" value="/project?pid={_e(pid)}">'
        '<textarea name="comment" rows="3" style="width:100%;box-sizing:border-box;font-size:.95rem" '
        'placeholder="Bericht aan de rol — bijv. “richt je op technisch onderzoek naar een '
        'natuurlijke elastaan-vervanger”"></textarea>'
        '<button class="btn ok" type="submit" style="margin-top:.3rem">Versturen ➤</button></form>')
    done_note = ('<p class="muted" style="font-size:.82rem">De rol levert voortgang op (status '
                 '<b>Actief</b>); <b>jij</b> zet een project op <b>Done</b> als het af is — een rol '
                 'sluit zichzelf nooit af.</p>')
    inner = (
        '<p><a href="/">← terug naar de cockpit</a></p>'
        '<h1>Project</h1>'
        f'<div class="tension"><b>{_e(p.get("owner"))}</b> · {_e(scope)}'
        f'<br><span class="muted">status {_e(p.get("status"))}'
        f'{(" · wacht op " + _e(p.get("blocked_on"))) if p.get("blocked_on") else ""}</span></div>'
        f'{hyp}{deliverable}{comments}{done_note}'
        f'<h2>Bewerken</h2>{form}'
    )
    return _page("Project", inner)


def render_fieldnotes(files: list, sel: str, content: str, pos: int, total: int) -> str:
    """Leesbare Field Notes/bulletins in de browser: links-lijst + de gekozen note, met
    vorige/volgende-bladeren (pijltjestoetsen ←/→). Pure render."""
    if not files:
        body = ('<div class="tension"><b>Nog geen Field Notes.</b><br>'
                '<span class="muted">Draai een puls (./refresh.sh of village once); de Field Note '
                'verschijnt dan in data/output/.</span></div>')
        return _page("Field Notes", '<p><a href="/">← cockpit</a></p><h1>📓 Field Notes</h1>' + body)
    items = "".join(
        f'<li><a href="/fieldnotes?f={_e(f)}"'
        f'{" style=font-weight:700" if f == sel else ""}>{_e(f.replace("field_note_","").replace(".md",""))}</a></li>'
        for f in files)
    i = files.index(sel) if sel in files else 0
    nav = []
    if i + 1 < len(files):
        nav.append(f'<a id="older" href="/fieldnotes?f={_e(files[i+1])}">← ouder</a>')
    if i > 0:
        nav.append(f'<a id="newer" href="/fieldnotes?f={_e(files[i-1])}">nieuwer →</a>')
    navbar = ' · '.join(nav)
    js = ("<script>document.addEventListener('keydown',function(e){"
          "if(e.key==='ArrowLeft'){var o=document.getElementById('older');if(o)location=o.href;}"
          "else if(e.key==='ArrowRight'){var n=document.getElementById('newer');if(n)location=n.href;}});</script>")
    inner = (
        '<p><a href="/">← cockpit</a></p><h1>📓 Field Notes</h1>'
        '<div style="display:flex;gap:1.4rem;align-items:flex-start">'
        f'<div style="flex:0 0 200px"><b>Archief ({total})</b>'
        f'<ul style="list-style:none;padding:0;margin:.2rem 0;font-size:.85rem;line-height:1.7">{items}</ul></div>'
        f'<div style="flex:1 1 auto;min-width:0">'
        f'<div class="muted" style="font-size:.82rem;margin-bottom:.3rem">Field Note {pos} van {total} · ←/→ bladeren · {navbar}</div>'
        f'<pre style="white-space:pre-wrap;background:var(--cream-3);border:1px solid var(--border);'
        f'border-radius:var(--radius);padding:1rem;font-family:var(--font-body);font-size:.9rem;'
        f'line-height:1.55">{_e(content) or "(leeg)"}</pre></div></div>' + js)
    return _page("Field Notes", inner)


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
        link = '<div style="margin-top:.3rem">📓 <a href="/fieldnotes">Field Notes lezen →</a></div>'
        noochie_block = f'<div class="noochie">{head}{body}{vr}{link}</div>'
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


_WATCHER_STYLE = ('<style>.wgrid{display:flex;flex-wrap:wrap;gap:.7rem;margin:.3rem 0 .6rem}'
                  '.wbox{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);'
                  'padding:.55rem .8rem;flex:1 1 220px;min-width:0;box-shadow:var(--shadow)}'
                  '.wbox-h{font-family:var(--font-display);font-weight:700;font-size:.8rem;'
                  'color:var(--green-dark);margin-bottom:.2rem}'
                  '.wtoggle{display:inline-flex;gap:.3rem;margin:.2rem 0 .4rem}'
                  '.wtoggle button{cursor:pointer;border:1px solid var(--border);background:var(--surface);'
                  'border-radius:var(--radius);padding:.25rem .7rem;font-size:.82rem}'
                  '.wtoggle button.on{background:var(--green-dark);color:#fff;border-color:var(--green-dark)}'
                  '.wpanel{display:none}.wpanel.on{display:block}</style>')


def _watcher_panel(shop: dict, visitors_7d, *, show_conv: bool) -> str:
    """Inner HTML van één venster (tiles + databaken + conversie + uitsplitsingen)."""
    cur = _e(shop.get("currency", ""))
    wd = shop.get("window_days", 0)
    base = [
        ("👟", _fmt_int(shop.get("pairs_sold", 0)), "paren verkocht"),
        ("🧾", _fmt_int(shop.get("orders", 0)), "orders"),
        ("💶", f'{_fmt_int(round(shop.get("revenue", 0)))} {cur}'.strip(), "omzet"),
        ("📦", f'{shop.get("aov", 0)} {cur}'.strip(), "gem. orderwaarde"),
    ]
    if not wd and shop.get("avg_pairs_month"):     # gemiddelden alleen bij 'hele historie'
        base.append(("📅", _fmt_int(round(shop["avg_pairs_month"])), "gem. paren/maand"))
        if shop.get("avg_revenue_month"):
            base.append(("📈", f'{_fmt_int(round(shop["avg_revenue_month"]))} {cur}'.strip(),
                         "gem. omzet/maand"))
    conv_note = ""
    if show_conv and visitors_7d:
        base.append(("👣", _fmt_int(visitors_7d), "bezoekers (7d)"))
        o7 = shop.get("orders_7d", shop.get("orders"))
        if o7 is not None:
            conv = round(100 * o7 / visitors_7d, 2) if visitors_7d else 0.0
            base.append(("🎯", f"{conv}%", "conversie (7d)"))
            conv_note = ('<p class="muted" style="font-size:.78rem;margin:.1rem 0 .6rem">'
                         f'Conversie = {o7} orders ÷ {_fmt_int(visitors_7d)} bezoekers over de '
                         'laatste 7 dagen.</p>')
    elif not show_conv:
        conv_note = ('<p class="muted" style="font-size:.78rem;margin:.1rem 0 .6rem">'
                     'Conversie tonen we alleen bij 7 dagen — daar hebben we een passend '
                     'bezoekersgetal (Plausible).</p>')
    tiles = "".join(
        f'<div class="kpi"><div class="kpi-n">{ico} {val}</div>'
        f'<div class="kpi-l">{_e(label)}</div></div>' for ico, val, label in base)

    def _box(rows, lbl):
        if not rows:
            return ""
        lis = "".join(
            f'<li style="display:flex;justify-content:space-between;gap:.6rem;padding:.15rem 0;'
            f'border-bottom:1px solid var(--border)"><span>{_e(k)}</span>'
            f'<b>{_e(v)}</b></li>' for k, v in rows)
        return (f'<div class="wbox"><div class="wbox-h">{_e(lbl)}</div>'
                f'<ul style="list-style:none;margin:.2rem 0 0;padding:0;font-size:.82rem">{lis}</ul></div>')
    boxes = "".join([
        _box(shop.get("by_country", []), "Orders per land"),
        _box(shop.get("top_products", []), "Topproducten (paren)"),
        _box(shop.get("channels", []), "Kanaal → orders"),
        _box(shop.get("top_landing_pages", []), "Via landingspagina → paren"),
        _box(shop.get("top_keywords", []), "UTM-term (campagne) → paren"),
    ])
    cols = f'<div class="wgrid">{boxes}</div>' if boxes else ""
    # Eerlijke databaken: cijfers komen UITSLUITEND uit de gekoppelde Shopify-winkel.
    flags = []
    if shop.get("pairs_sold", 0) and not shop.get("revenue", 0):
        flags.append("omzet is €0 bij wél verkochte paren → dit lijkt een <b>testorder</b>, geen echte verkoop")
    if shop.get("orders", 0) <= 2:
        flags.append("er staan maar een paar orders in déze winkel; verkoop via andere kanalen "
                     "(bijv. de 530-batch) zit <b>niet</b> in Shopify en dus niet in deze cijfers")
    warn = ""
    if flags:
        lis = "".join(f"<li>{f}</li>" for f in flags)
        warn = ('<div class="wbox" style="border-left:3px solid #c9a227;margin:.2rem 0 .6rem">'
                '<div class="wbox-h">⚠️ Lees deze cijfers met een korrel zout</div>'
                f'<ul style="margin:.2rem 0 0;padding-left:1.1rem;font-size:.82rem">{lis}</ul></div>')
    return f'<div class="kpis">{tiles}</div>{warn}{conv_note}{cols}'


def _render_watcher_dashboard(shop: dict, visitors_7d=None) -> str:
    """Website Watcher-dashboard: verkoopindicatoren uit Shopify + conversie (7d ÷ Plausible).
    Met een 7d/maand/hele-historie-toggle als de refresh meerdere vensters heeft opgehaald."""
    if not shop or not shop.get("ok"):
        return ('<h2>📊 Website Watcher — verkoop</h2>'
                '<p class="muted">Nog geen Shopify-data. Draai <code>village shopify</code> '
                '(vereist SHOPIFY_STORE + Client ID/secret in .env) of <code>./refresh.sh</code>.</p>')
    scope = ('<p class="muted" style="font-size:.78rem;margin:.1rem 0 .4rem">Bron: alleen de '
             'gekoppelde Shopify-winkel (footwear-nooch). Andere verkoopkanalen tellen niet mee.</p>')
    wins = shop.get("windows") or {}
    if not wins:                                    # oude cache zonder vensters → enkel paneel
        wd = shop.get("window_days", 0)
        sinds = (f' <span class="muted">· sinds {_e(shop.get("first_order_date"))}</span>'
                 if not wd and shop.get("first_order_date") else "")
        periode = "hele historie" if not wd else f"laatste {wd} dagen"
        panel = _watcher_panel(shop, visitors_7d, show_conv=bool(visitors_7d))
        return (f'<h2>📊 Website Watcher — verkoop ({periode}){sinds}</h2>{scope}'
                f'{_WATCHER_STYLE}{panel}')
    # Toggle: 7 dagen / maand (30) / hele historie (0). Default = hele historie.
    order = [("7", "7 dagen"), ("30", "maand"), ("0", "hele historie")]
    avail = [(k, lbl) for k, lbl in order if k in wins]
    default = "0" if "0" in wins else avail[-1][0]
    btns = "".join(
        f'<button type="button" class="{"on" if k == default else ""}" '
        f'onclick="wsel(\'{k}\')" data-w="{k}">{_e(lbl)}</button>' for k, lbl in avail)
    panels = ""
    for k, _lbl in avail:
        panels += (f'<div class="wpanel{" on" if k == default else ""}" id="wpanel-{k}">'
                   + _watcher_panel(wins[k], visitors_7d, show_conv=(k == "7")) + '</div>')
    js = ("<script>function wsel(w){document.querySelectorAll('.wpanel').forEach(function(p){"
          "p.classList.toggle('on',p.id=='wpanel-'+w)});"
          "document.querySelectorAll('.wtoggle button').forEach(function(b){"
          "b.classList.toggle('on',b.dataset.w==w)});}</script>")
    return (f'<h2>📊 Website Watcher — verkoop</h2>{scope}{_WATCHER_STYLE}'
            f'<div class="wtoggle">{btns}</div>{panels}{js}')


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
        # Toon de weergavenaam (na hernoemen); het id staat er klein onder als het afwijkt.
        nm = r.get("name") or r["id"]
        naam_cell = (f'<b>{_e(nm)}</b> <span class="muted">v{_e(r["version"])}</span>'
                     + (f'<br><span class="muted" style="font-size:.75rem">{_e(r["id"])}</span>'
                        if nm != r["id"] else ""))
        rrows.append(
            f'<tr class="{cls}">'
            f'<td>{naam_cell}</td>'
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
    # Leesbare statuslabels (intern: queued/running/blocked/future/done).
    _STATUS_LBL = {"running": "Actief", "queued": "Toekomst", "future": "Toekomst",
                   "blocked": "Wachten op", "done": "Done"}
    prows = []
    for p in show_proj:
        pacts = _proj_actions(p, csrf_token) if writable else '<span class="muted">—</span>'
        # Scope is klikbaar naar de projectpagina (daar staat de deliverable/voortgang).
        scope_link = f'<a href="/project?pid={_e(p.get("id"))}">{_e(_scope(p))}</a>'
        prows.append(
            f'<tr class="st-{_e(p.get("status"))}">'
            f'<td><b>{_e(p.get("owner"))}</b></td>'
            f'<td>{scope_link}</td>'
            f'<td>{_e(_STATUS_LBL.get(p.get("status"), p.get("status")))}</td>'
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
    def _sales_cell(x):
        sp = x.get("sales_pairs")
        if sp:
            return f'<b>👟 {_fmt_int(sp)}</b>'
        return '<span class="muted">—</span>'

    trows = "".join(
        f'<tr><td><b>{_e(x["word"])}</b></td>'
        f'<td>{_num(x.get("volume"), "/mnd")}</td>'
        f'<td>{("<b>" + _fmt_int(x["opportunity"]) + "</b>") if x.get("opportunity") is not None else "<span class=muted>—</span>"}</td>'
        f'<td>{_pos_cell(x)}</td>'
        f'<td>{_sales_cell(x)}</td>'
        f'<td style="min-width:230px">{_target_acts(x)}</td></tr>'
        # sorteer op verkoop (wat geld oplevert eerst), dan op kans
        for x in sorted(targets, key=lambda x: (-(x.get("sales_pairs") or 0),
                                                -((x.get("opportunity") if x.get("opportunity") is not None else -1)))))
    targets_tbl = (
        '<table><thead><tr><th>doelwit-woord</th><th>volume</th><th>kans</th>'
        '<th>onze Google-stand</th><th>verkoop</th><th>jouw oordeel</th></tr></thead>'
        f'<tbody>{trows or "<tr><td colspan=6 class=muted>geen doelwit-woorden</td></tr>"}</tbody></table>')

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
            out += (f' <span class="muted">· 📰 <a href="{_e(expl.get("link", ""))}" '
                    f'target="_blank" rel="noopener">{_e(expl["title"][:55])}</a></span>')
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
        if b.lower() in ("nooch.earth", "nooch"):
            return "wijzelf"                              # self-monitor: ons eigen merk volgen
        return "door jou" if b.lower() in _conf_set else "vast"
    mrows = ""
    for b in monitored:
        n = news.get(b) or {}
        if n.get("title"):
            feit = (f'<a href="{_e(n.get("link", ""))}" target="_blank" rel="noopener">'
                    f'{_e(n["title"][:90])}</a>'
                    f' <span class="muted">({_e(n.get("date", ""))})</span>')
        else:
            feit = '<span class="muted">geen recent nieuws opgehaald</span>'
        mrows += (f'<tr><td><b>{_e(b)}</b> <span class="muted">{_herkomst(b)}</span></td>'
                  f'<td>{feit}</td></tr>')
    monitor_tbl = (
        '<table><thead><tr><th>concurrent</th><th>laatste nieuwsfeit</th></tr></thead>'
        f'<tbody>{mrows or "<tr><td colspan=2 class=muted>geen concurrenten gemonitord</td></tr>"}</tbody></table>')
    # Scout destilleert het nieuws → voorstellen (kaart/seed/doelwit/concurrent), mens-gated.
    props = snap.get("news_proposals", [])
    _kind_lbl = {"kaart": "📇 kenniskaart", "seed": "🌱 seed", "doelwit": "🎯 doelwit",
                 "concurrent": "👟 concurrent"}

    def _prop_btn(pid, decision, label, cls):
        return (f'<form method="post" action="/action" style="display:inline">'
                f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
                f'<input type="hidden" name="iid" value="{_e(pid)}">'
                f'<input type="hidden" name="decision" value="{decision}">'
                f'<button class="btn {cls}" type="submit" name="action" value="news_prop">'
                f'{label}</button></form>')
    prows = "".join(
        f'<tr><td>{_e(_kind_lbl.get(p["kind"], p["kind"]))}</td>'
        f'<td><b>{_e(p["content"])}</b>'
        f'{(" — <span class=muted>" + _e(p["rationale"]) + "</span>") if p.get("rationale") else ""}'
        f'{(" <br><span class=muted>uit: <a href=" + chr(34) + _e(p.get("link","")) + chr(34) + " target=_blank rel=noopener>" + _e((p.get("title") or p.get("brand") or "")[:70]) + "</a></span>") if p.get("link") else ""}</td>'
        f'<td>' + ((_prop_btn(p["id"], "confirm", "✓ overnemen", "ok") + " "
                    + _prop_btn(p["id"], "reject", "✗ negeer", "danger"))
                   if writable else '<span class="muted">—</span>') + '</td></tr>'
        for p in props)
    scan_btn = (f'<form method="post" action="/action" style="margin:.3rem 0">'
                f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">'
                f'<button class="btn" type="submit" name="action" value="news_scan">'
                f'🔎 Scout: lees het nieuws &amp; destilleer</button></form>') if writable else ''
    distill_block = (
        f'<details{" open" if props else ""}><summary>🧪 Scout uit het nieuws — '
        f'voorstellen ({len(props)})</summary>{scan_btn}'
        '<table><thead><tr><th>type</th><th>voorstel</th><th>jouw oordeel</th></tr></thead>'
        f'<tbody>{prows or "<tr><td colspan=3 class=muted>nog geen voorstellen — klik hierboven</td></tr>"}'
        '</tbody></table></details>')

    comp_block = (f'<h2>Concurrenten</h2>'
                  f'<details open><summary>🔮 Nieuw gespot — wacht op jouw oordeel ({len(cands)})</summary>'
                  f'{cand_tbl}</details>'
                  f'<details open><summary>📡 Gemonitord — alle concurrenten ({len(monitored)})</summary>'
                  f'{monitor_tbl}</details>'
                  f'{distill_block}') if (cands or monitored or props or writable) else ''

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
    # Roloverleg-knop staat ALTIJD (ook bij lege agenda) zodat je altijd een nieuwe rol kunt
    # voorstellen / het overleg kunt openen.
    _rov = (f' <a class="btn" href="/roloverleg" style="margin-left:.4rem">🏛️ Roloverleg'
            f'{f" ({_n_agenda})" if _n_agenda else ""}</a>')
    if _n_agenda:
        _parts.append(f'{_n_agenda} op de roloverleg-agenda')
    _aan_jou = (f'<div class="aanjou"><b>📥 Aan jou:</b> {" · ".join(_parts)}{_focus}{_rov}</div>'
                if _parts else
                f'<div class="aanjou">📥 <b>Aan jou:</b> niks openstaand 🎉{_rov}</div>')

    inner = (
        f'<h1>NoochVille cockpit {badge}</h1>'
        f'<div class="bar">{_e(counts)} · gegenereerd {_e(_ts(snap.get("generated_at")))} · {hist}</div>'
        f'<style>.aanjou{{background:var(--yellow-light);border:1px solid var(--border);'
        f'border-radius:var(--radius);padding:.5rem .9rem;margin:.3rem 0 1rem;font-size:.95rem}}</style>'
        f'{_aan_jou}'
        f'{_banner(msg)}'
        f'{_render_digest(snap.get("digest", {}), snap.get("noochie_daily", {}))}'
        f'{_render_watcher_dashboard(snap.get("shopify", {}), snap.get("visitors_7d"))}'
        # Kansen verwerk je in de focusmodus (▶ Verwerk in focus); geen dubbele backlog-tabel meer.
        f'<details><summary>📥 Inbox — overige items ({_n_inbox})</summary>{inbox_tbl}</details>'
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
            "react_noop": "🤖 De AI kon nu geen herziening maken (geen LLM-antwoord of onleesbaar) "
                          "— pas de velden hierboven gerust zelf aan.",
            "consented": "✓ Consent — wordt doorgevoerd bij einde roloverleg.",
            "objected": "⚠ Als schadelijk gemarkeerd — blijft staan voor de volgende keer.",
            "obj_valid": "⚖️ Geldig bezwaar — het voorstel is van de agenda gehaald. Dien "
                         "eventueel een aangepaste versie opnieuw in.",
            "obj_invalid": "⚖️ Geen geldig bezwaar — je kunt alsnog consent geven.",
            "added": "➕ Voorstel op de agenda gezet.",
            "edited": "💾 Voorstel bijgewerkt vanuit de velden.",
            "group_added": "➕ Rol toegevoegd aan dit voorstel — bewerk 'm via het rol-formulier.",
            "to_remove": "🗑 Omgezet naar een verwijder-voorstel — consent voert het bij einde "
                         "overleg door (Gate G3 bewaakt werk/kinderen).",
            "kept_role": "↩ Terug naar een gewoon wijzig-voorstel.",
            "removed_draft": "🗑 Concept-rol uit dit voorstel verwijderd (van de agenda).",
            "flipped": "↔ Omgezet (purpose ↔ accountability) en opnieuw geformuleerd.",
            "to_project": "▶ Als experiment op het projectbord gezet voor de rol — bij herhaling "
                          "stolt het later tot accountability.",
            "invalid": "⚖️ Spanning ongeldig verklaard (geen baat voor de eigen rol) en direct "
                       "van de agenda gehaald — geen governance nodig."}
    if result.get("rov") in _rov:
        return _rov[result["rov"]]
    if "news_scan" in result:
        s = result["news_scan"]
        return f"🔎 Scout las {s.get('scanned', 0)} koppen → {s.get('proposed', 0)} nieuw voorstel(len)."
    if result.get("news"):
        _nl = {"rejected": "✗ Voorstel genegeerd.", "kaart": "📇 Als kenniskaart opgeslagen.",
               "seed": "🌱 Als seed in de bibliotheek gezet.", "doelwit": "🎯 Als doelwit in de "
               "bibliotheek gezet.", "concurrent": "👟 Toegevoegd aan de gevolgde merken."}
        return _nl.get(result["news"], "✓ Verwerkt.")
    if result.get("rov") == "group_consented":
        return f"✓ Hele voorstel aangenomen — {result.get('n', 0)} rol-onderdelen op consent."
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
    if result.get("proj_comment"):
        return ("💬 Verstuurd — de rol heeft direct geantwoord (zie het gesprek)."
                if result.get("replied")
                else "💬 Verstuurd — de rol kon nu niet reageren (geen LLM); pakt het op bij de "
                     "volgende puls.")
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
        # Omkeerbaarheidspoort: kan dit onherstelbare schade doen? Zo nee → direct op het bord
        # (queued, een vrij experiment). Zo ja → eerst als concept langs jouw akkoord (draft).
        from nooch_village.maturity import irreversible_harm
        item = inbox.get(iid) or {}
        c = item.get("context") or {}
        scope = formulate_project(c.get("title") or item.get("subject", ""),
                                  c.get("wat", ""), extra.get("owner", ""))
        risky = irreversible_harm(scope, c.get("title", ""), c.get("wat", ""))
        return decide_opportunity(inbox, iid, "add", destination="project",
                                  owner=extra.get("owner", ""), scope_override=scope,
                                  project_status="draft" if risky else "queued", projects=projects)
    if action in ("rov_react", "rov_consent", "rov_object", "rov_add", "rov_end", "rov_flip_facet",
                  "rov_to_project", "rov_invalid", "rov_edit", "rov_group_add", "rov_group_consent",
                  "rov_remove", "rov_keep_role"):
        from nooch_village.roloverleg import (Agenda, amend_with_reaction, apply_consented,
                                              flip_facet, build_change_from_fields)
        agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
        records = Records(os.path.join(dd, "governance_records.json"))
        if action == "rov_flip_facet":
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            agenda.update_change(iid, flip_facet(item))
            return {"ok": True, "rov": "flipped"}
        if action == "rov_invalid":
            # Holacracy 'from your role': een voorstel om een ándere rol te wijzigen zonder
            # benoemde baat voor de eigen rol is geen geldige spanning → direct van de agenda,
            # zonder governance-proces.
            from nooch_village.roloverleg import tension_validity
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            valid, why = tension_validity(item)
            if valid:
                return {"ok": False, "error": "deze spanning is wél geldig; verwijderen kan niet"}
            agenda.remove(iid)
            return {"ok": True, "rov": "invalid"}
        if action == "rov_to_project":
            # Geen accountability nodig om te handelen: laat de indienende rol dit als omkeerbaar
            # EXPERIMENT (project) doen. Bij herhaling stolt het later tot accountability.
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            ch = item.get("change", {})
            scope = (ch.get("add_accountabilities") or [item.get("title", "")])[0]
            projects = ProjectLedger(os.path.join(dd, "projects.json"))
            projects.create(item.get("role_id", "village"), scope, "human",
                            hypothesis=item.get("reason", ""), status="queued",
                            origin="experiment")
            agenda.remove(iid)
            return {"ok": True, "rov": "to_project"}
        if action == "rov_end":
            res = apply_consented(agenda, records)
            n_ok = sum(1 for r in res if r["status"] == "adopted")
            return {"ok": True, "rov": "ended", "adopted": n_ok,
                    "escalated": len(res) - n_ok}
        if action == "rov_add":
            import re as _re2
            owner = extra.get("owner", "")
            voorbeeld = (extra.get("voorbeeld") or "").strip()
            benefit = (extra.get("benefit") or "").strip()
            new_role = owner in ("", "__new__")
            # Accountabilities: één per regel (nieuw veld 'accs'); val terug op het oude 'info'-veld.
            accs = [l.strip() for l in (extra.get("accs") or extra.get("info") or "").splitlines()
                    if l.strip()][:8]
            if new_role:
                naam = (extra.get("rolnaam") or "").strip()
                purpose = (extra.get("purpose") or "").strip()
                domein = (extra.get("domein") or "").strip()
                if not (naam or purpose):
                    return {"ok": False, "error": "geef minstens een naam of purpose voor de nieuwe rol"}
                rid = _re2.sub(r"\W+", "_", (naam or purpose).lower())[:40].strip("_") or "nieuwe_rol"
                change = {"purpose": (purpose or naam)[:140], "add_accountabilities": accs,
                          "new_role_parent": "noochville"}
                if domein:
                    change["add_domains"] = [domein[:140]]
                agenda.add(role_id=rid, kind="add_role", change=change, reason=reason,
                           by="founder", title=(naam or purpose)[:60], example=voorbeeld)
            else:
                if not accs:
                    return {"ok": False, "error": "geef minstens één accountability op"}
                agenda.add(role_id=owner, kind="amend_role", change={"add_accountabilities": accs},
                           reason=reason, by="founder", title=accs[0][:60], example=voorbeeld,
                           benefit=benefit)
            return {"ok": True, "rov": "added"}
        if action == "rov_group_add":
            # Voeg een rol-onderdeel toe aan een bestaand voorstel (zelfde group). Start leeg; je
            # bewerkt het daarna via het rol-formulier. Bestaande rol → amend; __new__ → add_role.
            gid = extra.get("group") or ""
            if not gid:
                return {"ok": False, "error": "geen voorstel-id"}
            owner = (extra.get("g_owner") or "").strip()
            if owner in ("", "__new__"):
                naam = (extra.get("g_naam") or "").strip()
                if not naam:
                    return {"ok": False, "error": "geef een naam voor de nieuwe rol"}
                import re as _re3
                rid = _re3.sub(r"\W+", "_", naam.lower())[:40].strip("_") or "nieuwe_rol"
                agenda.add(role_id=rid, kind="add_role",
                           change={"purpose": "", "add_accountabilities": [],
                                   "new_role_parent": "noochville"},
                           reason="onderdeel van een voorstel", by="founder", title=naam[:60],
                           group=gid)
            else:
                agenda.add(role_id=owner, kind="amend_role", change={}, reason="onderdeel van een voorstel",
                           by="founder", title=owner, group=gid)
            return {"ok": True, "rov": "group_added"}
        if action == "rov_group_consent":
            gid = extra.get("group") or ""
            members = agenda.members_of_group(gid, only_open=True)
            for m in members:
                agenda.set_status(m["id"], "consented")
            return {"ok": True, "rov": "group_consented", "n": len(members)}
        if action == "rov_remove":
            # Zet een voorstel om naar 'deze rol verwijderen'. Gate G3 bewaakt het bij doorvoeren
            # (werk/kinderen → escalatie). Een nieuwe-rol-voorstel verwijderen = gewoon van de agenda.
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            if item.get("kind") == "add_role":
                agenda.remove(iid)
                return {"ok": True, "rov": "removed_draft"}
            agenda.update_fields(iid, kind="remove_role", change={},
                                 title=f"verwijder {item.get('role_id')}")
            return {"ok": True, "rov": "to_remove"}
        if action == "rov_keep_role":
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            agenda.update_fields(iid, kind="amend_role", change={},
                                 title=item.get("role_id", "rol"))
            return {"ok": True, "rov": "kept_role"}
        if action == "rov_edit":
            # GlassFrog-stijl: het voorstel bijwerken vanuit de direct bewerkte velden.
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            rec = records.get(item.get("role_id"))
            snap = ({"purpose": rec.definition.purpose,
                     "name": getattr(rec.definition, "name", "") or item.get("role_id"),
                     "accountabilities": list(rec.definition.accountabilities),
                     "domains": list(rec.definition.domains)} if rec else None)
            accs = (extra.get("ed_accs") or "").splitlines()
            doms = (extra.get("ed_domeinen") or "").splitlines()
            change, rid, title = build_change_from_fields(
                item, snap, naam=extra.get("ed_naam", ""), purpose=extra.get("ed_purpose", ""),
                accs=accs, domeinen=doms)
            agenda.update_fields(iid, change=change, role_id=rid, title=title)
            return {"ok": True, "rov": "edited"}
        # de overige acties werken op één item
        if action == "rov_consent":
            return {"ok": agenda.set_status(iid, "consented"), "rov": "consented"}
        if action == "rov_object":
            # Bezwaar-toets volgens de handout: JIJ kiest per vraag; de uitkomst volgt uit je eigen
            # antwoorden (facilitator oordeelt niet). Geldig → blijft staan voor integratie; geen
            # geldig bezwaar → terug naar open (je kunt alsnog consent geven).
            from nooch_village.roloverleg import evaluate_objection
            item = agenda.get(iid)
            if item is None:
                return {"ok": False, "error": "voorstel niet gevonden"}
            answers = {k: extra.get(k, "") for k in ("q1", "q2", "q3", "q3b", "q4")}
            if not any(answers.values()):
                return {"ok": False, "error": "beantwoord eerst de toetsvragen (kies per vraag een antwoord)"}
            res = evaluate_objection(answers, harm=extra.get("harm", ""))
            if res.get("valid"):
                # Geldig bezwaar → het voorstel gaat zó niet door: van de agenda. Dien eventueel
                # een aangepaste (geïntegreerde) versie opnieuw in.
                agenda.remove(iid)
                return {"ok": True, "rov": "obj_valid"}
            agenda.set_objection(iid, res.get("harm", ""), res)  # ongeldig → blijft open, met toets
            return {"ok": True, "rov": "obj_invalid"}
        # rov_react: reactie loggen + AI past voorstel aan (gegrond in de bank)
        from nooch_village.governance_examples import GovernanceExamples, few_shot_block
        item = agenda.get(iid)
        if item is None:
            return {"ok": False, "error": "voorstel niet gevonden"}
        if not (reason or "").strip():
            return {"ok": False, "error": "typ eerst een reactie voor de AI"}
        agenda.react(iid, reason)
        ge = GovernanceExamples(os.path.join(dd, "governance_examples.json"))
        block = few_shot_block(ge, item.get("title", "") + " " + item.get("reason", ""), k=3)
        rec = records.get(item.get("role_id"))
        snap = ({"purpose": rec.definition.purpose,
                 "accountabilities": list(rec.definition.accountabilities),
                 "domains": list(rec.definition.domains)} if rec else None)
        before = item.get("change", {})
        after = amend_with_reaction(item, reason, role_snapshot=snap, examples_block=block)
        agenda.update_change(iid, after)
        # Eerlijk: als er niets veranderde (geen LLM-antwoord of onleesbaar format) → dat melden,
        # niet stilletjes 'aangepast' tonen terwijl er niets gebeurde.
        return {"ok": True, "rov": "reacted" if after != before else "react_noop"}
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
    if action == "news_scan":
        # Scout leest de gemonitorde koppen en destilleert ze tot voorstellen (mens-gated).
        from nooch_village.news_distill import NewsProposals, distill_news
        from nooch_village.competitor_news_store import CompetitorNews
        news = CompetitorNews(os.path.join(dd, "competitor_news.json")).all()
        brands = CompetitorBrands(os.path.join(dd, "competitor_brands.json"))
        known = _monitored_brands(_config_competitor_brands(dd), brands.confirmed())
        props = NewsProposals(os.path.join(dd, "news_proposals.json"))
        res = distill_news(news, props, known_brands=known)
        return {"ok": True, "news_scan": res}
    if action == "news_prop":
        from nooch_village.news_distill import NewsProposals
        props = NewsProposals(os.path.join(dd, "news_proposals.json"))
        p = props.get(iid)
        if p is None:
            return {"ok": False, "error": "voorstel niet gevonden"}
        if extra.get("decision") == "reject":
            props.set_status(iid, "rejected")
            return {"ok": True, "news": "rejected"}
        kind, content = p["kind"], p["content"]
        rat, link, brand = p.get("rationale", ""), p.get("link", ""), p.get("brand", "")
        if kind == "kaart":
            from nooch_village.insight import Insight
            notes = NotesStore(os.path.join(dd, "notes.json"))
            nid = f"news_{iid}"
            if notes.get(nid) is None:
                notes.add(Insight(id=nid, claim=content,
                                  source=(link or brand or "concurrent-nieuws"),
                                  tags=["scout", "nieuws"] + ([brand] if brand else [])))
        elif kind in ("seed", "doelwit"):
            library = Library(os.path.join(dd, "library.json"))
            library.curate(content, "approved", rationale=rat, by="Scout (nieuws, mens-bevestigd)")
            library.set_function(content, "volg" if kind == "seed" else "doelwit")
        elif kind == "concurrent":
            brands = CompetitorBrands(os.path.join(dd, "competitor_brands.json"))
            brands.add_candidate(content, article=p.get("title", ""), link=link)
            brands.confirm(content)
        props.set_status(iid, "confirmed")
        return {"ok": True, "news": kind}
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
    if action == "proj_comment":
        projects = ProjectLedger(os.path.join(dd, "projects.json"))
        ok = projects.add_comment(iid, extra.get("comment", ""))
        if not ok:
            return {"ok": False, "error": "lege opmerking of project niet gevonden"}
        # De rol antwoordt DIRECT op je bericht (eigen capaciteit, tekst-only, omkeerbaar).
        from nooch_village.project_worker import work_one
        p = projects.get(iid) or {}
        rec = records.get(p.get("owner")) if (records := Records(os.path.join(dd, "governance_records.json"))) else None
        purpose = getattr(getattr(rec, "definition", None), "purpose", "") if rec else ""
        steer = " · ".join(c.get("text", "") for c in p.get("comments", []) if c.get("text"))
        try:
            res = work_one(p.get("scope"), p.get("owner", ""), purpose, steer=steer)
        except Exception:
            res = {"ok": False, "needs": None}
        if res.get("ok"):
            projects.add_role_message(iid, res["outcome"])
            return {"ok": True, "proj_comment": True, "replied": True}
        if res.get("needs"):
            projects.add_role_message(iid, f"Dit lukt me niet met tekst alleen — nodig: {res['needs']}")
            return {"ok": True, "proj_comment": True, "replied": True}
        return {"ok": True, "proj_comment": True, "replied": False}
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
            elif path == "/suggest_accountabilities":
                # Live AI-suggestie voor accountabilities (read-only, geen mutatie → geen CSRF).
                dd = data_dir or _default_data_dir()
                from nooch_village.governance_examples import GovernanceExamples, few_shot_block
                from nooch_village.inbox_actions import suggest_accountabilities
                role = (qs.get("role") or [""])[0]
                purpose = (qs.get("purpose") or [""])[0]
                ge = GovernanceExamples(os.path.join(dd, "governance_examples.json"))
                block = few_shot_block(ge, f"{role} {purpose}", k=3)
                accs = suggest_accountabilities(role, purpose, examples_block=block)
                payload = ("\n".join(accs)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            elif path == "/fieldnotes":
                import glob
                dd = data_dir or _default_data_dir()
                out_dir = os.path.join(dd, "output")
                files = sorted((os.path.basename(p) for p in
                                glob.glob(os.path.join(out_dir, "field_note_*.md"))), reverse=True)
                sel = (qs.get("f") or [""])[0]
                if sel not in files:
                    sel = files[0] if files else ""
                content = ""
                if sel:                       # sel is gevalideerd tegen de lijst (geen traversal)
                    try:
                        content = open(os.path.join(out_dir, sel), encoding="utf-8").read()
                    except Exception:
                        content = ""
                pos = files.index(sel) + 1 if sel in files else 0
                body = render_fieldnotes(files, sel, content, pos, len(files)).encode("utf-8")
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
                             "name": getattr(rec.definition, "name", "") or item["role_id"],
                             "accountabilities": list(rec.definition.accountabilities),
                             "domains": list(rec.definition.domains)} if rec else None)
                    gmembers = agenda.members_of_group(item.get("group") or item["id"])
                    body = render_roloverleg(
                        item, snap, secretary_check(item, recs), csrf_token, msg=msg,
                        group_members=gmembers, roles=roles).encode("utf-8")
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
                     "rolnaam": (form.get("rolnaam") or [""])[0],
                     "purpose": (form.get("purpose") or [""])[0],
                     "domein": (form.get("domein") or [""])[0],
                     "accs": (form.get("accs") or [""])[0],
                     "voorbeeld": (form.get("voorbeeld") or [""])[0],
                     "benefit": (form.get("benefit") or [""])[0],
                     "harm": (form.get("harm") or [""])[0],
                     "ed_naam": (form.get("ed_naam") or [""])[0],
                     "ed_purpose": (form.get("ed_purpose") or [""])[0],
                     "ed_accs": (form.get("ed_accs") or [""])[0],
                     "ed_domeinen": (form.get("ed_domeinen") or [""])[0],
                     "group": (form.get("group") or [""])[0],
                     "g_owner": (form.get("g_owner") or [""])[0],
                     "g_naam": (form.get("g_naam") or [""])[0],
                     "comment": (form.get("comment") or [""])[0],
                     "q1": (form.get("q1") or [""])[0], "q2": (form.get("q2") or [""])[0],
                     "q3": (form.get("q3") or [""])[0], "q3b": (form.get("q3b") or [""])[0],
                     "q4": (form.get("q4") or [""])[0],
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
