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
    "Hieronder staat de tekst van een artikel over {topic}.\n"
    "Geef UITSLUITEND de namen van schoenmerken die het artikel presenteert als voorbeeld binnen "
    "'{topic}'. Neem GEEN merken mee die alleen ter vergelijking, contrast of zijdelings genoemd worden "
    "(bijvoorbeeld een mainstream-merk dat als tegenpool dient). Geen publicatienamen, geen auteurs, geen "
    "algemene woorden, niet 'Nooch'. Kommagescheiden lijst. Niets gevonden → antwoord precies: NONE.\n\n"
    "Artikel:\n{text}"
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
    input_schema = ("brands: list[str] (bekende merken, worden gefilterd) · "
                    "topic: str (optioneel maar STERK aanbevolen voor een project — de categorie merken om "
                    "te ontdekken, AFGELEID uit het projectdoel, bv. 'best barefoot shoe brands'; weglaten = "
                    "de staande categorie uit de config) · limit: int (aantal gidsen)")
    required_payload = ("brands",)
    output_schema = "ok: bool, candidates: list[{brand, article, link}], query: str | error"

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        brands = payload.get("brands") or []
        topic = (payload.get("topic") or payload.get("query") or "").strip()
        try:
            limit = int(payload.get("limit", 4))
        except (TypeError, ValueError):
            limit = 4
        query = self._query(context, topic)
        try:
            guides = self._serpapi_guides(context, query)
        except Exception as exc:
            log.warning("competitor_discover: SerpAPI-zoekopdracht faalde: %s", exc)
            return {"ok": False, "error": str(exc)}

        topic_label = topic or "duurzame, ethische of vegan schoenen"
        from nooch_village.llm import reason
        seen, candidates = set(), []
        for g in guides[:limit]:
            text = self._fetch_text(g["link"])
            if len(text) < 200:                          # niet leesbaar → overslaan
                continue
            out = reason(_PROMPT.format(topic=topic_label, text=text[:6000]),
                         call_site="skill_competitor_discover")
            for name in _parse_brand_list(out, brands):
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                candidates.append({"brand": name, "article": g["title"], "link": g["link"]})
        return {"ok": True, "candidates": candidates, "guides": len(guides), "query": query}

    def _query(self, context, topic: str) -> str:
        """De gids-zoekopdracht. Voorrang: het projectkennis-onderwerp (payload) → globale setting →
        default. Zo zoekt een barefoot-project naar barefoot-gidsen, niet naar de vaste vegan-default.
        Het onderwerp is CONTENT (komt uit het project), niet in de code gebakken."""
        if topic:
            return topic
        setting = str((getattr(context, "settings", {}) or {}).get("discover_query", "")).strip()
        return setting or _GUIDE_QUERY

    def _serpapi_guides(self, context, query: str) -> list[dict]:
        from nooch_village import web_read
        key = ((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
               or os.getenv("SERPAPI_API_KEY"))
        if not key:
            raise RuntimeError("SERPAPI_API_KEY ontbreekt — skill faalt bewust closed")
        return web_read.serpapi_search(query, key)

    def _fetch_text(self, link: str) -> str:
        """Lees een echte artikel-URL en geef platte tekst terug. Faalt → lege string."""
        from nooch_village import web_read
        return web_read.fetch_text(link)
