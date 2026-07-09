"""linkbuilding_targets — spot gidsen/lijstjes waar Nooch in vermeld wil worden, en prioriteer.

Vindt gids-artikelen via SerpAPI (échte URLs), leest de pagina, en bepaalt de prioriteit op de
volledige tekst: noemt de gids je concurrenten maar Nooch NIET, dan is dat je sterkste pitch
('je mist een merk') → 'hoog'. Staat Nooch er al in → 'laag'. Onleesbaar → 'onbekend'.
Dependency-vrij (gedeelde web_read-helpers). Fail-closed.
"""
from __future__ import annotations

import logging
import os

from nooch_village.skills import Skill
from nooch_village import web_read

log = logging.getLogger("village.skill.linkbuilding")

_GUIDE_QUERY = "best sustainable vegan sneaker brands guide"
_NOOCH = ("nooch", "nooch.earth")


def _assess_priority(text: str, brands: list[str]) -> tuple[str, list[str]]:
    """Prioriteit uit de gids-tekst. Noemt concurrenten maar niet Nooch → 'hoog' (sterkste
    pitch). Nooch erin → 'laag'. Geen tekst → 'onbekend'. Anders 'midden'."""
    low = (text or "").lower()
    if not low:
        return "onbekend", []
    mentions = [b for b in brands if b and b.lower() in low]
    has_nooch = any(n in low for n in _NOOCH)
    if mentions and not has_nooch:
        return "hoog", mentions
    if has_nooch:
        return "laag", mentions
    return "midden", mentions


class LinkbuildingTargetsSkill(Skill):
    name = "linkbuilding_targets"
    cost = "credits"               # SerpAPI-zoekopdracht
    side_effect_free = True
    required_env = ("SERPAPI_API_KEY",)
    description = ("Spot gidsen/lijstjes over duurzame sneakers (SerpAPI, echte URLs), leest ze, "
                   "en prioriteert op 'noemt concurrenten maar niet Nooch'. Fail-closed.")
    input_schema = "brands: list[str] (concurrenten, voor prioritering), limit: int"
    required_payload = ("brands",)
    output_schema = "ok: bool, targets: list[{title, link, source, priority, mentions}] | error"

    def run(self, payload: dict, context=None) -> dict:
        brands = payload.get("brands") or []
        try:
            limit = int(payload.get("limit", 8))
        except (TypeError, ValueError):
            limit = 8
        key = ((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
               or os.getenv("SERPAPI_API_KEY"))
        if not key:
            return {"ok": False, "error": "SERPAPI_API_KEY ontbreekt"}
        query = str((getattr(context, "settings", {}) or {}).get("linkbuilding_query", "")) or _GUIDE_QUERY
        try:
            guides = web_read.serpapi_search(query, key, num=max(limit, 10))
        except Exception as exc:
            log.warning("linkbuilding_targets: SerpAPI faalde: %s", exc)
            return {"ok": False, "error": str(exc)}

        targets = []
        for g in guides[:limit]:
            text = web_read.fetch_text(g["link"])
            prio, mentions = _assess_priority(text, brands)
            targets.append({"title": g["title"], "link": g["link"],
                            "source": web_read.domain_of(g["link"]),
                            "priority": prio, "mentions": mentions})
        return {"ok": True, "targets": targets, "scanned": len(guides)}
