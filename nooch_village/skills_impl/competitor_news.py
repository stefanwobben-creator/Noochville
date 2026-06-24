"""competitor_news — wekelijks/dagelijks marktnieuws over directe (duurzame) concurrenten.

Haalt per merk recent nieuws op via de Google News RSS-feed, filtert op een venster van
N dagen en op strategische thema's (funding, launch, B-Corp, vegan leather, ...), en schrijft
een Markdown field report. Dependency-vrij: `requests` (al een dependency) + stdlib-XML, geen
feedparser. Fail-closed: een netwerk-/parse-fout per merk levert een nette foutmelding, geen
verzonnen nieuws.

De skill leest alleen het web en schrijft het rapport; het dorp voeden (signalen, spanningen)
doet de ConcurrentScout-rol, niet deze skill.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.competitor")

_DEFAULT_BRANDS = ["Veja", "Moea", "Flamingos Life", "Komrads"]
_THEMES = ('"CEO" OR "funding" OR "launch" OR "partner" OR "B-Corp" OR "collaboration" '
           'OR "flagship store" OR "greenwashing" OR "vegan leather" OR "materials" '
           'OR "sustainability"')
# Thema's die voor Nooch's missie strategisch relevant zijn (triggeren een spanning).
_MISSION_THEMES = ("b-corp", "vegan leather", "materials", "sustainability",
                   "greenwashing", "recycl", "circular")
_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "Mozilla/5.0 (NoochVille competitor monitor; +https://nooch.earth)"


def _parse_feed(xml_text: str, *, now: datetime, days: int, brand: str) -> list[dict]:
    """Pure parser: RSS-XML → lijst items binnen het venster. Geen netwerk, testbaar."""
    root = ET.fromstring(xml_text)
    cutoff = now - timedelta(days=days)
    items: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        try:
            published = parsedate_to_datetime(pub)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published = now
        if published >= cutoff and title:
            items.append({
                "brand": brand,
                "title": title,
                "link": link,
                "date": published.strftime("%Y-%m-%d"),
            })
    return items


class CompetitorNewsSkill(Skill):
    name = "competitor_news"
    cost = "rate_limited"          # onofficieel RSS-endpoint, beleefde sleep tussen merken
    side_effect_free = False       # schrijft een rapport (zoals field_note)
    required_env = ()              # keyless (Google News RSS)
    description = ("Monitort strategisch marktnieuws over directe duurzame concurrenten via "
                   "Google News RSS en schrijft een Markdown field report. Fail-closed.")
    input_schema = "brands: list[str] (optioneel), days: int (optioneel, default 7)"
    output_schema = "ok: bool, path: str, items: list[dict], total: int, brands: list[str] | error"

    def _brands(self, payload: dict, context) -> list[str]:
        if payload.get("brands"):
            return [b.strip() for b in payload["brands"] if b.strip()]
        raw = (getattr(context, "settings", {}) or {}).get("competitor_brands", "")
        parsed = [b.strip() for b in raw.split(",") if b.strip()]
        return parsed or list(_DEFAULT_BRANDS)

    def _fetch_brand(self, brand: str, *, days: int, now: datetime) -> list[dict]:
        import requests
        query = f'"{brand}" AND ({_THEMES})'
        url = _RSS.format(q=urllib.parse.quote(query))
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
        resp.raise_for_status()
        return _parse_feed(resp.text, now=now, days=days, brand=brand)

    def run(self, payload: dict, context=None) -> dict:
        brands = self._brands(payload, context)
        try:
            days = int(payload.get("days")
                       or (getattr(context, "settings", {}) or {}).get("competitor_days", 7))
        except (TypeError, ValueError):
            days = 7
        now = datetime.now(timezone.utc)

        per_brand: dict[str, list[dict]] = {}
        errors: dict[str, str] = {}
        for i, brand in enumerate(brands):
            try:
                per_brand[brand] = self._fetch_brand(brand, days=days, now=now)
            except Exception as exc:                     # fail-closed per merk
                errors[brand] = str(exc)
                per_brand[brand] = []
                log.warning("competitor_news: '%s' faalde: %s", brand, exc)
            if i < len(brands) - 1:
                time.sleep(1.0)                          # beleefd

        # Hele run mislukt (alle merken faalden) → geen rapport, fail-closed.
        if errors and all(not v for v in per_brand.values()) and len(errors) == len(brands):
            return {"ok": False, "error": f"alle merken faalden: {errors}"}

        items = [it for lst in per_brand.values() for it in lst]
        path = self._write_report(context, brands, per_brand, days, now)
        return {"ok": True, "path": path, "items": items, "total": len(items),
                "brands": brands, "errors": errors}

    def _write_report(self, context, brands, per_brand, days, now) -> str:
        lines = ["# Competitor Field Report",
                 f"*Gegenereerd op: {now.strftime('%Y-%m-%d %H:%M')} UTC*", "",
                 f"Wekelijkse monitor van strategische ontwikkelingen (funding, materiaal-"
                 f"innovaties, winkelopeningen, B-Corp, lanceringen) bij directe concurrenten. "
                 f"Venster: {days} dagen.", "", "---", ""]
        for brand in brands:
            lines.append(f"## 👟 {brand}")
            news = per_brand.get(brand, [])
            if news:
                for it in news:
                    lines.append(f"- **[{it['title']}]({it['link']})**")
                    lines.append(f"  - *Publicatiedatum:* {it['date']}")
            else:
                lines.append("- _Geen opvallende strategische ontwikkelingen in dit venster._")
            lines.append("")
        out_dir = os.path.join(getattr(context, "data_dir", "."), "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"competitor_report_{now.strftime('%Y-%m-%d')}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path
