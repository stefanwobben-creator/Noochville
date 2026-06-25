"""Attributie: koppel verkoop (via landingspagina) terug aan de woordenschat.

Een order draagt de landingspagina van het eerste bezoek (bijv. /blogs/vegan/sneakers). Die pagina
hoort bij een doelwit-woord uit de bibliotheek (bijv. 'vegan sneakers'). Door het pad te matchen
aan de doelwit-woorden zien we per woord hoeveel paren het opleverde: welke targets geld opleveren.

Puur en deterministisch (geen LLM, geen netwerk): woord-overlap tussen het pad en het zoekwoord,
met een drempel zodat één toevallig woord geen match forceert.
"""
from __future__ import annotations
import re
from collections import Counter

_STOP = {"de", "het", "een", "en", "van", "the", "and", "for", "shop", "products", "product",
         "collections", "collection", "blogs", "blog", "pages", "page", "nl", "en", "www"}


def _toks(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower())
            if len(t) >= 3 and t not in _STOP]


def _hits(kw_tokens: list[str], path_tokens: list[str]) -> int:
    """Aantal zoekwoord-tokens dat in het pad voorkomt (met prefix-match voor enkelvoud/meervoud)."""
    n = 0
    for t in kw_tokens:
        if any(t == p or (len(t) >= 4 and (t in p or p in t)) for p in path_tokens):
            n += 1
    return n


def attribute_keywords(landing_pages, keywords) -> dict:
    """Wijs de paren van elke landingspagina toe aan het best passende doelwit-woord.
    `landing_pages` = [(pad, paren), ...]; `keywords` = lijst doelwit-woorden. Eén pagina telt mee
    bij hoogstens één woord (het sterkst overlappende). Drempel: ≥1 token én ≥helft van het
    zoekwoord aanwezig, zodat een enkel toevallig woord geen match maakt. Geeft {woord: paren}."""
    kw_toks = {k: _toks(k) for k in (keywords or [])}
    out: Counter = Counter()
    for path, pairs in (landing_pages or []):
        ptoks = _toks(path)
        if not ptoks:
            continue
        best, best_hits = None, 0
        for k, kt in kw_toks.items():
            if not kt:
                continue
            h = _hits(kt, ptoks)
            if h >= 1 and h / len(kt) >= 0.5 and h > best_hits:
                best, best_hits = k, h
        if best:
            out[best] += pairs
    return dict(out)
