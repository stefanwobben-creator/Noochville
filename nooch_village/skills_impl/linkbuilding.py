"""linkbuilding_targets — spot gidsen/lijstjes waar Nooch in vermeld wil worden.

Zoekt merk-onafhankelijk naar 'best/top/guide'-stukken over duurzame sneakers (Google News
RSS) en levert ze als doelwitten voor linkbuilding. Prioriteit komt uit titel + samenvatting
in de feed zelf (geen website-scrape): noemt het stuk je concurrenten maar Nooch niet, dan is
dat je sterkste pitch → 'hoog'. Dependency-vrij, fail-closed.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from xml.etree import ElementTree as ET

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.linkbuilding")

_GUIDE_QUERY = ('("best" OR "top" OR "guide" OR "ultimate guide" OR "brands") AND '
                '("sustainable sneakers" OR "ethical sneakers" OR "vegan sneakers" '
                'OR "sustainable shoes" OR "ethical shoes" OR "vegan footwear")')
_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "Mozilla/5.0 (NoochVille competitor monitor; +https://nooch.earth)"
_NOOCH = ("nooch", "nooch.earth")


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")


def _publication(title: str) -> str:
    """Google News-titels eindigen vaak op ' - Publicatie'. Pak die als bron."""
    parts = (title or "").rsplit(" - ", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _parse_guides(xml_text: str) -> list[dict]:
    """Pure parser: RSS → [{title, link, summary}]. Geen netwerk."""
    root = ET.fromstring(xml_text)
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        out.append({"title": title,
                    "link": (item.findtext("link") or "").strip(),
                    "summary": _strip_html(item.findtext("description") or "").strip()})
    return out


def _assess_priority(text: str, brands: list[str]) -> tuple[str, list[str]]:
    """Prioriteit uit titel+samenvatting. Noemt concurrenten maar niet Nooch → 'hoog'."""
    low = (text or "").lower()
    mentions = [b for b in brands if b and b.lower() in low]
    has_nooch = any(n in low for n in _NOOCH)
    if mentions and not has_nooch:
        return "hoog", mentions            # sterkste pitch: 'je mist een merk'
    if has_nooch:
        return "laag", mentions            # Nooch staat er al in
    if not low:
        return "onbekend", mentions        # geen tekst om op te oordelen
    return "midden", mentions


class LinkbuildingTargetsSkill(Skill):
    name = "linkbuilding_targets"
    cost = "rate_limited"
    side_effect_free = True
    required_env = ()
    description = ("Spot gidsen/lijstjes (best/top/guide) over duurzame sneakers als "
                   "linkbuilding-doelwitten; prioriteert op concurrent-zonder-Nooch.")
    input_schema = "brands: list[str] (concurrenten, voor prioritering), limit: int"
    output_schema = "ok: bool, targets: list[{title, link, source, priority, mentions}] | error"

    def run(self, payload: dict, context=None) -> dict:
        brands = payload.get("brands") or []
        try:
            limit = int(payload.get("limit", 15))
        except (TypeError, ValueError):
            limit = 15
        query = str((getattr(context, "settings", {}) or {}).get("linkbuilding_query", "")) or _GUIDE_QUERY
        url = _RSS.format(q=urllib.parse.quote(query))
        try:
            import requests
            resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
            resp.raise_for_status()
            guides = _parse_guides(resp.text)
        except Exception as exc:
            log.warning("linkbuilding_targets faalde: %s", exc)
            return {"ok": False, "error": str(exc)}

        targets = []
        for g in guides[:limit]:
            prio, mentions = _assess_priority(f"{g['title']} {g['summary']}", brands)
            targets.append({"title": g["title"], "link": g["link"],
                            "source": _publication(g["title"]),
                            "priority": prio, "mentions": mentions})
        return {"ok": True, "targets": targets, "scanned": len(guides)}
