"""Globale zoek-pagina: doorzoekt in één keer rollen/cirkels, projecten en de kennisbank (founder 23 jul).

Bereikbaar via de zoekbalk in de gedeelde header (`_nav`). Puur leeswerk, fail-soft per store: een
store die ontbreekt of afwijkt slaat zijn groep over i.p.v. de pagina te breken. De organisatieboom-rail
en de footer komen via de gedeelde shell-injectie in `_send`, net als op elke andere pagina."""
from __future__ import annotations

from nooch_village.web_base import _e, _page
from nooch_village.cockpit2_util import _nav, _DS_LINK, _name
from nooch_village import org


def _match(tekst: str, termen: list[str]) -> bool:
    t = (tekst or "").lower()
    return all(term in t for term in termen)


def _hit(url: str, kind: str, titel: str, snip: str = "") -> str:
    snip_html = f"<span class='gs-snip'>{_e(snip[:160])}</span>" if snip else ""
    return (f"<a class='gs-hit' href='{_e(url)}'>"
            f"<span class='gs-kind'>{_e(kind)}</span> {_e(titel[:120])}{snip_html}</a>")


def _rollen(st, termen: list[str]) -> list[str]:
    uit = []
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        d = getattr(r, "definition", None)
        purpose = getattr(d, "purpose", "") or ""
        accs = " ".join(getattr(d, "accountabilities", []) or []) if d else ""
        naam = _name(r)
        if _match(f"{naam} {purpose} {accs}", termen):
            kind = "cirkel" if org.is_circle(r) else "rol"
            uit.append(_hit(f"/node?id={r.id}", kind, naam, purpose))
        if len(uit) >= 15:
            break
    return uit


def _projecten(st, termen: list[str]) -> list[str]:
    uit = []
    try:
        alle = st.projects.all()
    except Exception:
        return uit
    for p in alle:
        scope = str(p.get("scope") or "")
        if _match(scope, termen):
            status = p.get("status") or ""
            uit.append(_hit(f"/project?id={p.get('id')}", f"project · {status}", scope))
        if len(uit) >= 15:
            break
    return uit


def _kennis(st, termen: list[str]) -> list[str]:
    uit = []
    # Laag 2: geversioneerde standpunten (titel = de claim in mensentaal).
    try:
        for k in st.kennisbank.all():
            if _match(f"{k.get('title','')} {k.get('why','')}", termen):
                uit.append(_hit(f"/kennisbank?id={k.get('id')}", "standpunt",
                                k.get("title", ""), k.get("why", "")))
            if len(uit) >= 12:
                break
    except Exception:
        pass
    # Laag 1: atomen (kenniskaartjes).
    try:
        for a in st.notes.all():
            if getattr(a, "archived", False):
                continue
            if _match(getattr(a, "claim", ""), termen):
                uit.append(_hit("/kennisbank", "kenniskaartje", getattr(a, "claim", "")))
            if len(uit) >= 24:
                break
    except Exception:
        pass
    return uit


def render_search(st, q: str = "") -> str:
    q = (q or "").strip()
    termen = [t for t in q.lower().split() if t]
    if not termen:
        main = ("<div class='c2-main'><h1>Zoeken</h1>"
                "<p class='muted'>Typ in de zoekbalk hierboven om in één keer door rollen, "
                "projecten en de kennisbank te zoeken.</p></div>")
        return _page("Zoeken", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")

    groepen = [("Rollen & cirkels", _rollen(st, termen)),
               ("Projecten", _projecten(st, termen)),
               ("Kennisbank", _kennis(st, termen))]
    totaal = sum(len(h) for _, h in groepen)

    blokken = []
    for titel, hits in groepen:
        if hits:
            blokken.append(f"<div class='gs-group'><h2>{_e(titel)} ({len(hits)})</h2>{''.join(hits)}</div>")
    if not blokken:
        blokken.append("<p class='muted'>Niets gevonden. Probeer een ander woord.</p>")

    main = (f"<div class='c2-main'><h1>Zoeken naar “{_e(q)}”</h1>"
            f"<p class='muted'>{totaal} treffer(s) in rollen, projecten en de kennisbank.</p>"
            f"{''.join(blokken)}</div>")
    return _page("Zoeken", f"{_DS_LINK}{_nav()}<div class='c2-wrap'>{main}</div>")
