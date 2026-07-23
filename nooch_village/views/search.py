"""Globale zoek: doorzoekt in één keer roles, projects, insights (laag 2) en signals (laag 1).

Bereikbaar via de zoekbalk in de gedeelde header (`_nav`) — live terwijl je typt (uitklap-dropdown, via
de fragment-modus) en als volledige pagina op Enter. Vier duidelijk gescheiden groepen zodat je meteen
ziet of een treffer een rol, een project, een inzicht of een signal (kenniskaartje) is. Puur leeswerk,
fail-soft per store."""
from __future__ import annotations

from urllib.parse import quote

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _nav, _DS_LINK, _name
from nooch_village import org


def _match(tekst: str, termen: list[str]) -> bool:
    t = (tekst or "").lower()
    return all(term in t for term in termen)


def _kaartje_url(claim: str) -> str:
    """Signal/kenniskaartje heeft geen eigen detailpagina; open de kennisbank met de claim voorgevuld
    in de zoek, zodat het kaartje daar bovenaan verschijnt."""
    return "/kennisbank?q=" + quote(" ".join((claim or "").split()[:6]))


def _roles(st, termen):
    uit = []
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        d = getattr(r, "definition", None)
        purpose = getattr(d, "purpose", "") or ""
        accs = " ".join(getattr(d, "accountabilities", []) or []) if d else ""
        naam = _name(r)
        if _match(f"{naam} {purpose} {accs}", termen):
            kind = "circle" if org.is_circle(r) else "role"
            uit.append({"url": f"/node?id={r.id}", "kind": kind, "titel": naam, "snip": purpose})
    return uit


def _projects(st, termen):
    uit = []
    try:
        alle = st.projects.all()
    except Exception:
        return uit
    for p in alle:
        scope = str(p.get("scope") or "")
        if _match(scope, termen):
            uit.append({"url": f"/project?id={p.get('id')}", "kind": "project",
                        "titel": scope, "snip": str(p.get("status") or "")})
    return uit


def _insights(st, termen):
    uit = []
    try:
        for k in st.kennisbank.all():
            if _match(f"{k.get('title','')} {k.get('why','')}", termen):
                uit.append({"url": f"/kennisbank?id={k.get('id')}", "kind": "insight",
                            "titel": k.get("title", ""), "snip": k.get("why", "")})
    except Exception:
        pass
    return uit


def _signals(st, termen):
    uit = []
    try:
        for a in st.notes.all():
            if getattr(a, "archived", False):
                continue
            claim = getattr(a, "claim", "")
            if _match(claim, termen):
                uit.append({"url": _kaartje_url(claim), "kind": "signal",
                            "titel": claim, "snip": getattr(a, "source", "") or ""})
    except Exception:
        pass
    return uit


# Volgorde en labels van de vier groepen (founder 23 jul: signal = kenniskaartje, insight = laag 2).
_GROEPEN = (("Roles", _roles), ("Projects", _projects), ("Insights", _insights), ("Signals", _signals))


def _zoek(st, termen):
    return [(label, fn(st, termen)) for label, fn in _GROEPEN]


def _hit_html(h: dict) -> str:
    snip = f"<span class='gs-snip'>{_e((h.get('snip') or '')[:150])}</span>" if h.get("snip") else ""
    return (f"<a class='gs-hit' href='{_e(h['url'])}'>"
            f"<span class='gs-kind gs-{_e(h['kind'])}'>{_e(h['kind'])}</span> "
            f"{_e((h.get('titel') or '')[:120])}{snip}</a>")


def render_search_fragment(st, q: str = "") -> str:
    """Compacte dropdown-inhoud voor de live-zoek (max een paar per groep). chrome=False in de route."""
    termen = [t for t in (q or "").lower().split() if t]
    if len(q.strip()) < 2:
        return ""
    resultaten = _zoek(st, termen)
    blokken = []
    for label, hits in resultaten:
        if hits:
            rijen = "".join(_hit_html(h) for h in hits[:4])
            meer = (f"<span class='gs-more'>+{len(hits) - 4} meer</span>" if len(hits) > 4 else "")
            blokken.append(f"<div class='gs-group'><h2>{_e(label)} ({len(hits)}){meer}</h2>{rijen}</div>")
    if not blokken:
        return "<div class='gs-empty'>geen treffers</div>"
    alle = f"<a class='gs-all' href='/search?q={quote(q)}'>Alle resultaten →</a>"
    return "".join(blokken) + alle


def render_search(st, q: str = "") -> str:
    q = (q or "").strip()
    termen = [t for t in q.lower().split() if t]
    if not termen:
        main = ("<div class='c2-main'><h1>Zoeken</h1>"
                "<p class='muted'>Typ in de zoekbalk hierboven om in één keer door roles, projects, "
                "insights en signals te zoeken.</p></div>")
        return _page("Zoeken", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")

    resultaten = _zoek(st, termen)
    totaal = sum(len(h) for _, h in resultaten)
    blokken = []
    for label, hits in resultaten:
        if hits:
            rijen = "".join(_hit_html(h) for h in hits[:25])
            blokken.append(f"<div class='gs-group'><h2>{_e(label)} ({len(hits)})</h2>{rijen}</div>")
    if not blokken:
        blokken.append("<p class='muted'>Niets gevonden. Probeer een ander woord.</p>")

    main = (f"<div class='c2-main'><h1>Zoeken naar “{_e(q)}”</h1>"
            f"<p class='muted'>{totaal} treffer(s) in roles, projects, insights en signals.</p>"
            f"{''.join(blokken)}</div>")
    return _page("Zoeken", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
