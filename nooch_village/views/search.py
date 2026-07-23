"""Globale zoek: doorzoekt in één keer roles, projects, insights (laag 2) en signals (laag 1).

Bereikbaar via de zoekbalk in de gedeelde header (`_nav`) — live terwijl je typt (uitklap-dropdown, via
de fragment-modus) en als volledige pagina op Enter. Vier duidelijk gescheiden groepen zodat je meteen
ziet of een treffer een rol, een project, een inzicht of een signal (kenniskaartje) is. Puur leeswerk,
fail-soft per store."""
from __future__ import annotations

import difflib
import re
from urllib.parse import quote

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _nav, _DS_LINK, _name
from nooch_village import org


def _woorden(tekst: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (tekst or "").lower())


def _match(tekst: str, termen: list[str]) -> bool:
    """Elke zoekterm moet aan het BEGIN van een woord matchen (woord-prefix), niet ergens midden in
    een ander woord. Zo matcht 'pha' wel 'PHA' en 'PHA-outsole', maar niet 'hyphalite'. Prefix (niet
    exact) houdt de live-zoek fijn: 'veg' vindt 'vegan'."""
    ws = _woorden(tekst)
    return all(any(w.startswith(term) for w in ws) for term in termen)


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


def _words(st, termen):
    uit = []
    try:
        for w, e in (st.library.all() or {}).items():
            if _match(w, termen):
                uit.append({"url": "/woordenschat", "kind": "word",
                            "titel": w, "snip": str(e.get("status") or "")})
    except Exception:
        pass
    return uit


# Volgorde en labels van de groepen (founder 23 jul: signal = kenniskaartje, insight = laag 2,
# word = library-zoekwoord).
_GROEPEN = (("Roles", _roles), ("Projects", _projects), ("Insights", _insights),
            ("Signals", _signals), ("Words", _words))


def _zoek(st, termen):
    return [(label, fn(st, termen)) for label, fn in _GROEPEN]


def _vocab(st) -> set:
    """Kleine woordenschat voor de 'bedoelde u'-suggestie: rolnamen, library-woorden en inzicht-titels
    (geen atomen — dat zou te groot en te ruis-gevoelig worden). Fail-soft per bron."""
    v: set = set()
    try:
        for r in st.records.all():
            if not getattr(r, "archived", False):
                v.update(_woorden(_name(r)))
    except Exception:
        pass
    try:
        for w in (st.library.all() or {}):
            v.update(_woorden(w))          # library-sleutels zijn vaak meerwoordig → op woord splitsen
    except Exception:
        pass
    try:
        for k in st.kennisbank.all():
            v.update(_woorden(k.get("title", "")))
    except Exception:
        pass
    return {w for w in v if len(w) >= 3}


def _suggestie(st, q: str, totaal: int) -> str:
    """Bedoelde-u-misschien: alleen bij weinig treffers en een enkele term; de dichtstbijzijnde bekende
    term (difflib, geen externe dep). Leeg als er niets dichtbij genoeg is of het gelijk is aan de invoer."""
    termen = [t for t in q.lower().split() if t]
    if totaal > 3 or len(termen) != 1 or len(termen[0]) < 3:
        return ""
    m = difflib.get_close_matches(termen[0], _vocab(st), n=1, cutoff=0.72)
    return m[0] if (m and m[0] != termen[0]) else ""


def _suggestie_html(sug: str) -> str:
    if not sug:
        return ""
    return (f"<div class='gs-didyoumean'>Bedoelde u: "
            f"<a href='/search?q={quote(sug)}'>{_e(sug)}</a>?</div>")


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
    totaal = sum(len(h) for _, h in resultaten)
    blokken = []
    for label, hits in resultaten:
        if hits:
            rijen = "".join(_hit_html(h) for h in hits[:4])
            meer = (f"<span class='gs-more'>+{len(hits) - 4} meer</span>" if len(hits) > 4 else "")
            blokken.append(f"<div class='gs-group'><h2>{_e(label)} ({len(hits)}){meer}</h2>{rijen}</div>")
    sug = _suggestie_html(_suggestie(st, q, totaal))
    if not blokken:
        return sug + "<div class='gs-empty'>geen treffers</div>" if sug else "<div class='gs-empty'>geen treffers</div>"
    alle = f"<a class='gs-all' href='/search?q={quote(q)}'>Alle resultaten →</a>"
    return sug + "".join(blokken) + alle


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
    sug = _suggestie_html(_suggestie(st, q, totaal))

    main = (f"<div class='c2-main'><h1>Zoeken naar “{_e(q)}”</h1>"
            f"<p class='muted'>{totaal} treffer(s) in roles, projects, insights, signals en words.</p>"
            f"{sug}{''.join(blokken)}</div>")
    return _page("Zoeken", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
