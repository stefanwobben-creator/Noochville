"""competitor_discover — spot nieuwe concurrenten door gids-artikelen UIT TE LEZEN.

De vorige aanpak (hoofdletter-woorden uit krantenkoppen) gaf rommel: titelwoorden en
publicatienamen ('Ultimate', 'Good', 'Business', 'Insider') in plaats van merken. De échte
merken staan in de tekst van de gids ('15 Best Vegan Sneaker Brands' → Veja, Vesica Piscis,
Etiko, ...). Daarom: vind de gidsen via Google News RSS, lees de pagina, en laat de LLM de
merknamen extraheren. Dependency-vrij (requests + stdlib-XML) + de gedeelde LLM-ladder.

Fail-closed: geen LLM, geen leesbare pagina of geen merken → géén kandidaten (geen rommel).
De heuristiek is bewust verdwenen; liever niets dan een verkeerde merknaam.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from xml.etree import ElementTree as ET

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.discover")

_GUIDE_QUERY = ('("best" OR "top" OR "guide" OR "brands") AND '
                '("sustainable sneakers" OR "ethical sneakers" OR "vegan sneakers" '
                'OR "sustainable shoes" OR "vegan footwear")')
_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "Mozilla/5.0 (NoochVille competitor monitor; +https://nooch.earth)"

_PROMPT = (
    "Hieronder staat de tekst van een artikel over duurzame/ethische/vegan schoenen.\n"
    "Geef UITSLUITEND de namen van schoen- of sneakermerken die erin genoemd worden, als "
    "kommagescheiden lijst. Geen publicatienamen, geen auteurs, geen algemene woorden, niet "
    "'Nooch'. Geen niets gevonden → antwoord precies: NONE.\n\nArtikel:\n{text}"
)

# Woorden die nooit een merk zijn (vangnet als de LLM toch ruis teruggeeft).
_NOT_A_BRAND = {
    "none", "best", "top", "guide", "sustainable", "ethical", "vegan", "sneakers",
    "shoes", "footwear", "brands", "brand", "the", "good on you", "business insider",
    "esquire", "vogue", "nooch", "review", "guide to", "and", "more",
}


def _parse_titles(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            out.append({"title": title, "link": link})
    return out


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
    cost = "rate_limited"
    side_effect_free = True
    required_env = ()
    description = ("Leest gids-artikelen over duurzame sneakers en laat de LLM de genoemde "
                   "merknamen extraheren als kandidaat-concurrenten. Fail-closed (geen rommel).")
    input_schema = "brands: list[str] (bekende merken, worden gefilterd), limit: int (gidsen)"
    output_schema = "ok: bool, candidates: list[{brand, article, link}] | error"

    def run(self, payload: dict, context=None) -> dict:
        brands = payload.get("brands") or []
        try:
            limit = int(payload.get("limit", 4))
        except (TypeError, ValueError):
            limit = 4
        try:
            guides = self._fetch_guides(context)
        except Exception as exc:
            log.warning("competitor_discover: gidsen ophalen faalde: %s", exc)
            return {"ok": False, "error": str(exc)}

        from nooch_village.llm import reason
        seen, candidates = set(), []
        for g in guides[:limit]:
            text = self._fetch_text(g["link"])
            if len(text) < 200:                          # interstitial / lege pagina → overslaan
                continue
            out = reason(_PROMPT.format(text=text[:6000]))
            for name in _parse_brand_list(out, brands):
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                candidates.append({"brand": name, "article": g["title"], "link": g["link"]})
        return {"ok": True, "candidates": candidates, "guides": len(guides)}

    def _fetch_guides(self, context) -> list[dict]:
        import requests
        query = str((getattr(context, "settings", {}) or {}).get("discover_query", "")) or _GUIDE_QUERY
        url = _RSS.format(q=urllib.parse.quote(query))
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
        resp.raise_for_status()
        return _parse_titles(resp.text)

    def _fetch_text(self, link: str) -> str:
        """Best-effort: volg de link en geef platte tekst terug. Faalt → lege string."""
        if not link:
            return ""
        try:
            import requests
            resp = requests.get(link, headers={"User-Agent": _UA}, timeout=20,
                                allow_redirects=True)
            resp.raise_for_status()
            return _strip_html(resp.text)
        except Exception as exc:
            log.info("competitor_discover: pagina lezen faalde (%s): %s", link[:60], exc)
            return ""
