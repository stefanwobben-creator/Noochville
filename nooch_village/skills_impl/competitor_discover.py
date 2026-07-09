"""competitor_discover — spot nieuwe concurrenten door gids-artikelen UIT TE LEZEN.

Bron: SerpAPI Google-zoekopdracht (geeft échte artikel-URLs, geen Google News-redirects waar
een lezer niet doorheen komt). Per gevonden gids: pagina lezen, en de LLM de genoemde
merknamen laten extraheren ('15 Best Vegan Sneaker Brands' → Veja, Vesica Piscis, Etiko, ...).
Dependency-vrij (requests + stdlib) + de gedeelde LLM-ladder.

Fail-closed: geen SerpAPI-key, geen leesbare pagina of geen LLM → géén kandidaten (geen rommel).
Liever niets dan een verkeerde merknaam; de mens bevestigt de rest in de cockpit.
"""
from __future__ import annotations

import logging
import os
import re

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.discover")

_GUIDE_QUERY = "best sustainable vegan sneaker brands"

_PROMPT = (
    "Hieronder staat de tekst van een artikel over duurzame/ethische/vegan schoenen.\n"
    "Geef UITSLUITEND de namen van schoen- of sneakermerken die erin genoemd worden, als "
    "kommagescheiden lijst. Geen publicatienamen, geen auteurs, geen algemene woorden, niet "
    "'Nooch'. Niets gevonden → antwoord precies: NONE.\n\nArtikel:\n{text}"
)

_NOT_A_BRAND = {
    "none", "best", "top", "guide", "sustainable", "ethical", "vegan", "sneakers",
    "shoes", "footwear", "brands", "brand", "the", "good on you", "business insider",
    "esquire", "vogue", "nooch", "review", "and", "more", "vegnews", "peta",
}


def _strip_html(html: str) -> str:
    from nooch_village.web_read import strip_html
    return strip_html(html)


def _parse_brand_list(llm_out: str, known: list[str]) -> list[str]:
    """LLM-output → schone, ontdubbelde merknamenlijst, gefilterd op ruis + bekende merken."""
    if not llm_out or llm_out.strip().upper().startswith("NONE"):
        return []
    raw = re.split(r"[,\n;]+", llm_out)
    known_l = {k.lower() for k in known}
    seen, out = set(), []
    for part in raw:
        name = re.sub(r"^[\s\-\*\d\.\)]+", "", part).strip().strip('"').strip()
        low = name.lower()
        if (not name or len(name) < 2 or len(name) > 40 or low in _NOT_A_BRAND
                or low in known_l or "nooch" in low or low in seen):
            continue
        seen.add(low)
        out.append(name)
    return out


class CompetitorDiscoverSkill(Skill):
    name = "competitor_discover"
    cost = "credits"               # SerpAPI-zoekopdracht
    side_effect_free = True
    required_env = ("SERPAPI_API_KEY",)
    description = ("Vindt gids-artikelen via SerpAPI (echte URLs), leest ze, en laat de LLM "
                   "de genoemde merknamen extraheren als kandidaat-concurrenten. Fail-closed.")
    input_schema = "brands: list[str] (bekende merken, worden gefilterd), limit: int (gidsen)"
    required_payload = ("brands",)
    output_schema = "ok: bool, candidates: list[{brand, article, link}] | error"

    def run(self, payload: dict, context=None) -> dict:
        brands = payload.get("brands") or []
        try:
            limit = int(payload.get("limit", 4))
        except (TypeError, ValueError):
            limit = 4
        try:
            guides = self._serpapi_guides(context)
        except Exception as exc:
            log.warning("competitor_discover: SerpAPI-zoekopdracht faalde: %s", exc)
            return {"ok": False, "error": str(exc)}

        from nooch_village.llm import reason
        seen, candidates = set(), []
        for g in guides[:limit]:
            text = self._fetch_text(g["link"])
            if len(text) < 200:                          # niet leesbaar → overslaan
                continue
            out = reason(_PROMPT.format(text=text[:6000]))
            for name in _parse_brand_list(out, brands):
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                candidates.append({"brand": name, "article": g["title"], "link": g["link"]})
        return {"ok": True, "candidates": candidates, "guides": len(guides)}

    def _serpapi_guides(self, context) -> list[dict]:
        from nooch_village import web_read
        key = ((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
               or os.getenv("SERPAPI_API_KEY"))
        if not key:
            raise RuntimeError("SERPAPI_API_KEY ontbreekt — skill faalt bewust closed")
        query = str((getattr(context, "settings", {}) or {}).get("discover_query", "")) or _GUIDE_QUERY
        return web_read.serpapi_search(query, key)

    def _fetch_text(self, link: str) -> str:
        """Lees een echte artikel-URL en geef platte tekst terug. Faalt → lege string."""
        from nooch_village import web_read
        return web_read.fetch_text(link)
