"""linkbuilding_targets — spot gidsen/lijstjes waar Nooch in vermeld wil worden, en prioriteer.

Vindt gids-artikelen via SerpAPI (échte URLs) op het ONDERWERP van het project (of de staande
`linkbuilding_query` uit de config — nooit een code-default: die leverde vegan-sneakergidsen aan
een barefoot-project), leest de pagina, en bepaalt de prioriteit op de volledige tekst: noemt de
gids je concurrenten maar Nooch NIET, dan is dat je sterkste pitch ('je mist een merk') → 'hoog'.
Staat Nooch er al in → 'laag'. Onleesbaar → 'onbekend'. Dependency-vrij (gedeelde web_read-
helpers). Fail-closed: geen key/onderwerp/SerpAPI → error; geen gidsen → no_data.
"""
from __future__ import annotations

import logging
import os

from nooch_village.skills import Skill, resolve_source_scope
from nooch_village import web_read

log = logging.getLogger("village.skill.linkbuilding")

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


def _scope(payload: dict, context) -> tuple[str, str]:
    """Het onderwerp van de gidsen-zoekopdracht: payload (`topic`/`query`) > config
    (`linkbuilding_query`) > zichtbaar weigeren. Zelfde contract als competitor_discover."""
    payload = payload or {}
    topic = str(payload.get("topic") or payload.get("query") or "").strip()
    config_scope = str((getattr(context, "settings", {}) or {}).get("linkbuilding_query", "") or "").strip()
    return resolve_source_scope(topic, config_scope, veld="onderwerp (topic)",
                                config_key="linkbuilding_query")


class LinkbuildingTargetsSkill(Skill):
    name = "linkbuilding_targets"
    cost = "credits"               # SerpAPI-zoekopdracht
    side_effect_free = True
    required_env = ("SERPAPI_API_KEY",)
    description = ("Finds guide/listicle pages on a topic where Nooch could be listed (SerpAPI, real "
                   "URLs), reads each page and ranks it: mentions competitor brands but not Nooch = "
                   "'hoog' (strongest pitch), already mentions Nooch = 'laag'. Each target carries the "
                   "search snippet. Fail-closed: no key/topic is an error, no guides is 'nothing found'.")
    input_schema = ("topic: str (the subject to find guides about, DERIVED from the project goal, e.g. "
                    "'best barefoot shoe brands'; `query` is accepted as alias; omitted = the standing "
                    "`linkbuilding_query` from the config) · brands: list[str] (REQUIRED — competitor "
                    "brands, used to rank the guides) · limit: int (pages to read, default 8)")
    # `brands` is hard verplicht (de prioritering leunt erop); het onderwerp is VOORWAARDELIJK
    # (payload óf config) en wordt daarom door validate_payload bewaakt, zoals competitor_discover.
    required_payload = ("brands",)
    output_schema = ("ok: bool, targets: list[{title, link, source, snippet, priority, mentions}], "
                     "text: str, query: str, gescand: int | no_data: True, reason | ok: False, error")

    def validate_payload(self, payload: dict, context) -> list:
        """Is er een onderwerp (payload of config)? Anders is het item niet uitvoerbaar — vóór het
        draaien, zodat het project niet parkeert op een fout die bij het plannen al te zien was."""
        _q, err = _scope(payload, context)
        return [err] if err else []

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        brands = payload.get("brands") or []
        if isinstance(brands, str):
            brands = [b.strip() for b in brands.split(",") if b.strip()]
        try:
            limit = int(payload.get("limit", 8))
        except (TypeError, ValueError):
            limit = 8
        query, err = _scope(payload, context)
        if err:
            log.warning("linkbuilding_targets: %s", err)
            return {"ok": False, "error": err}
        key = ((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
               or os.getenv("SERPAPI_API_KEY"))
        if not key:
            return {"ok": False, "error": "SERPAPI_API_KEY ontbreekt"}
        try:
            guides = web_read.serpapi_search(query, key, num=max(limit, 10))
        except Exception as exc:
            from nooch_village.sleutelmasker import masker      # een ConnectionError draagt de URL mét api_key
            log.warning("linkbuilding_targets: SerpAPI faalde: %s", masker(exc))
            return {"ok": False, "error": masker(exc)}
        if not guides:
            # Onderzocht, niets gevonden (📭): de zoekmachine gaf geen gids terug voor dit onderwerp.
            return {"ok": True, "no_data": True, "targets": [], "gescand": 0, "query": query,
                    "reason": f"no guide pages found for '{query}'"}

        targets = []
        for g in guides[:limit]:
            text = web_read.fetch_text(g["link"])
            prio, mentions = _assess_priority(text, brands)
            targets.append({"title": g["title"], "link": g["link"],
                            "source": web_read.domain_of(g["link"]),
                            "snippet": (g.get("snippet") or "").strip(),   # de strekking van de zoekmachine
                            "priority": prio, "mentions": mentions})
        hoog = [t for t in targets if t["priority"] == "hoog"]
        per_prio = {p: sum(1 for t in targets if t["priority"] == p) for p in ("hoog", "midden", "laag", "onbekend")}
        return {"ok": True, "targets": targets, "gescand": len(guides), "query": query,
                "text": (f"{len(targets)} guide page(s) for '{query}': "
                         + ", ".join(f"{n} {p}" for p, n in per_prio.items() if n)
                         + (f"; strongest pitch: {', '.join(t['source'] for t in hoog[:4])}" if hoog else ""))}
