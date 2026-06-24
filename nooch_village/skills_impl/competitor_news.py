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
# Footwear-context: dwingt af dat het écht over schoenen gaat. Lost homoniemen op
# (bijv. 'Moea' = Taiwan Ministry of Economic Affairs). Instelbaar via competitor_context.
_CONTEXT = ('"sneakers" OR "footwear" OR "shoes" OR "trainers" OR "vegan leather" '
            'OR "sustainable fashion"')
_THEMES = ('"CEO" OR "funding" OR "launch" OR "partner" OR "B-Corp" OR "collaboration" '
           'OR "flagship store" OR "greenwashing" OR "vegan leather" OR "materials" '
           'OR "sustainability"')
# Thema's die voor Nooch's missie strategisch relevant zijn (triggeren een spanning).
_MISSION_THEMES = ("b-corp", "vegan leather", "materials", "sustainability",
                   "greenwashing", "recycl", "circular")
_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
_UA = "Mozilla/5.0 (NoochVille competitor monitor; +https://nooch.earth)"

# Getrapt venster: eerst de afgelopen maand; niets? dan het kwartaal; niets? dan het jaar.
_DEFAULT_WINDOWS = (30, 90, 365)


def _window_label(days: int) -> str:
    return {30: "laatste maand", 90: "laatste kwartaal", 365: "laatste jaar"}.get(
        days, f"laatste {days} dagen")


def _parse_all(xml_text: str, *, now: datetime, brand: str) -> list[dict]:
    """Pure parser: RSS-XML → álle items met hun publicatiedatum. Geen venster-filter
    (dat doet de cascade). Onparseerbare datum → 'now' (telt als recent)."""
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        try:
            published = parsedate_to_datetime(pub)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue                                     # geen betrouwbare datum → hard overslaan
        items.append({"brand": brand, "title": title, "link": link,
                      "published": published, "date": published.strftime("%Y-%m-%d")})
    return items


def _cascade_select(items: list[dict], *, now: datetime, windows) -> tuple[list[dict], int]:
    """Kies het kórtste venster dat nieuws oplevert. Niets in alle vensters → ([], grootste)."""
    for w in windows:
        cutoff = now - timedelta(days=w)
        sel = [i for i in items if i["published"] >= cutoff]
        if sel:
            return sel, w
    return [], (windows[-1] if windows else 0)


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

    def _fetch_brand(self, brand: str, *, now: datetime, context=None) -> list[dict]:
        import requests
        ctx = str((getattr(context, "settings", {}) or {}).get("competitor_context", "")) or _CONTEXT
        query = f'"{brand}" AND ({ctx}) AND ({_THEMES})'
        url = _RSS.format(q=urllib.parse.quote(query))
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
        resp.raise_for_status()
        return _parse_all(resp.text, now=now, brand=brand)

    def _windows(self, payload: dict, context) -> list[int]:
        if payload.get("windows"):
            return [int(w) for w in payload["windows"]]
        if payload.get("days"):                          # back-compat: één vast venster
            return [int(payload["days"])]
        raw = str((getattr(context, "settings", {}) or {}).get("competitor_windows", ""))
        parsed = [int(x) for x in raw.replace(" ", "").split(",") if x.strip().isdigit()]
        return parsed or list(_DEFAULT_WINDOWS)

    def run(self, payload: dict, context=None) -> dict:
        brands = self._brands(payload, context)
        windows = self._windows(payload, context)
        now = datetime.now(timezone.utc)

        per_brand: dict[str, dict] = {}                  # brand -> {"items": [...], "window": int}
        errors: dict[str, str] = {}
        seen_links: set[str] = set()                     # ontdubbel dezelfde roundup over merken
        for i, brand in enumerate(brands):
            try:
                allitems = self._fetch_brand(brand, now=now, context=context)
                sel, used = _cascade_select(allitems, now=now, windows=windows)
                deduped = []
                for it in sel:
                    if it["link"] and it["link"] in seen_links:
                        continue
                    seen_links.add(it["link"])
                    deduped.append(it)
                per_brand[brand] = {"items": deduped, "window": used}
            except Exception as exc:                     # fail-closed per merk
                errors[brand] = str(exc)
                per_brand[brand] = {"items": [], "window": windows[-1]}
                log.warning("competitor_news: '%s' faalde: %s", brand, exc)
            if i < len(brands) - 1:
                time.sleep(1.0)                          # beleefd

        # Hele run mislukt (alle merken faalden) → geen rapport, fail-closed.
        if (len(errors) == len(brands)
                and all(not v["items"] for v in per_brand.values()) and errors):
            return {"ok": False, "error": f"alle merken faalden: {errors}"}

        items = [{"brand": it["brand"], "title": it["title"], "link": it["link"], "date": it["date"]}
                 for v in per_brand.values() for it in v["items"]]
        path = self._write_report(context, brands, per_brand, windows, now)
        return {"ok": True, "path": path, "items": items, "total": len(items),
                "brands": brands, "windows": windows, "errors": errors}

    def _write_report(self, context, brands, per_brand, windows, now) -> str:
        cascade = "/".join(str(w) for w in windows)
        lines = ["# Competitor Field Report",
                 f"*Gegenereerd op: {now.strftime('%Y-%m-%d %H:%M')} UTC*", "",
                 f"Monitor van strategische ontwikkelingen (funding, materiaalinnovatie, "
                 f"winkelopeningen, B-Corp, lanceringen) bij directe concurrenten. "
                 f"Getrapt venster per merk: {cascade} dagen (het kortste met nieuws).", "",
                 "---", ""]
        for brand in brands:
            entry = per_brand.get(brand, {"items": [], "window": windows[-1]})
            news, used = entry["items"], entry["window"]
            lines.append(f"## 👟 {brand}  _({_window_label(used)})_")
            if news:
                for it in news:
                    lines.append(f"- **[{it['title']}]({it['link']})**")
                    lines.append(f"  - *Publicatiedatum:* {it['date']}")
            else:
                lines.append("- _Geen ontwikkelingen in het afgelopen jaar._")
            lines.append("")
        out_dir = os.path.join(getattr(context, "data_dir", "."), "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"competitor_report_{now.strftime('%Y-%m-%d')}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path
