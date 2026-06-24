"""competitor_discover — spot nieuwe/aanverwante concurrenten in vergelijkingsartikelen.

Zoekt via Google News RSS naar stukken die alternatieven vergelijken ('brands like Veja',
'sustainable sneakers alternatives', ...) en haalt met een regel-gebaseerde heuristiek
kandidaat-merknamen (hoofdletter-woorden) uit de koppen. Dependency-vrij (requests +
stdlib-XML). Fail-closed.

LET OP: dit is een ruizige hint-generator, geen waarheid. De heuristiek vangt naast echte
merken ('Cariuma') ook valse positieven ('Sneaker'). Daarom levert de skill alleen
KANDIDATEN; de mens bevestigt ze in de cockpit voordat ze worden gemonitord.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from xml.etree import ElementTree as ET

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.discover")

_COMPARISON = ('"alternatives" OR "brands like" OR "competitors" OR "sustainable sneakers" '
               'OR "vegan sneaker brands"')
_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "Mozilla/5.0 (NoochVille competitor monitor; +https://nooch.earth)"

# Hoofdletter-woorden die vaak in koppen staan maar GEEN merk zijn.
_STOP = {
    "the", "best", "top", "sustainable", "sneaker", "sneakers", "shoe", "shoes", "vegan",
    "like", "alternatives", "alternative", "review", "reviews", "brand", "brands", "new",
    "with", "from", "in", "on", "for", "to", "is", "are", "and", "or", "of", "your",
    "these", "this", "that", "eco", "ethical", "fashion", "style", "guide", "list",
    "buy", "best-selling", "made", "you", "we", "our", "more", "most", "why", "how",
    "what", "where", "compared", "comparison", "versus", "vs", "europe", "european",
}


def _extract(titles: list[tuple[str, str]], brands: list[str], *, limit: int = 8) -> list[dict]:
    """Pure extractie: lijst (title, link) → kandidaat-merken. Testbaar zonder netwerk."""
    stop = set(_STOP) | {b.lower() for b in brands}
    seen: set[str] = set()
    out: list[dict] = []
    for title, link in titles:
        for word in re.findall(r"\b[A-Z][a-z]{2,}\b", title or ""):
            key = word.lower()
            if key in stop or key in seen:
                continue
            seen.add(key)
            out.append({"brand": word, "article": title, "link": link})
            if len(out) >= limit:
                return out
    return out


def _parse_titles(xml_text: str) -> list[tuple[str, str]]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            items.append((title, link))
    return items


class CompetitorDiscoverSkill(Skill):
    name = "competitor_discover"
    cost = "rate_limited"
    side_effect_free = True        # geeft kandidaten terug; de scout/store persisteert
    required_env = ()
    description = ("Spot kandidaat-concurrenten in vergelijkingsartikelen (Google News RSS) "
                   "via een hoofdletter-heuristiek. Ruizig: levert hints, geen besluiten.")
    input_schema = "brands: list[str] (optioneel, referentiemerken), limit: int (optioneel)"
    output_schema = "ok: bool, candidates: list[{brand, article, link}] | error"

    def run(self, payload: dict, context=None) -> dict:
        brands = payload.get("brands") or self._settings_brands(context) or ["Veja", "Moea"]
        try:
            limit = int(payload.get("limit", 8))
        except (TypeError, ValueError):
            limit = 8
        ref = brands[:2] or ["Veja"]
        ors = " OR ".join(f'"{b}"' for b in ref)
        query = f"({ors}) AND ({_COMPARISON})"
        url = _RSS.format(q=urllib.parse.quote(query))
        try:
            import requests
            resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
            resp.raise_for_status()
            titles = _parse_titles(resp.text)
        except Exception as exc:
            log.warning("competitor_discover faalde: %s", exc)
            return {"ok": False, "error": str(exc)}
        candidates = _extract(titles, brands, limit=limit)
        return {"ok": True, "candidates": candidates, "scanned": len(titles)}

    @staticmethod
    def _settings_brands(context) -> list[str]:
        raw = (getattr(context, "settings", {}) or {}).get("competitor_brands", "")
        return [b.strip() for b in raw.split(",") if b.strip()]
