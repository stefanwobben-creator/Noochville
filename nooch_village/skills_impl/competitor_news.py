"""competitor_news — wekelijks/dagelijks marktnieuws over directe (duurzame) concurrenten.

Haalt per merk recent nieuws op via de Google News RSS-feed, filtert op een venster van
N dagen en op strategische thema's (funding, launch, B-Corp, vegan leather, ...), en schrijft
een Markdown field report. Dependency-vrij: `requests` (al een dependency) + stdlib-XML, geen
feedparser. Fail-closed: een netwerk-/parse-fout per merk levert een nette foutmelding, geen
verzonnen nieuws.

Drie uitkomsten (scope 55): geen merken (payload noch config) of álle merken fout → `ok: False,
error`; merken bevraagd maar nergens nieuws → `no_data: True, reason`; anders records met een
`snippet` (de RSS-description zonder de kop) en de uitgever als `source`.

De skill leest alleen het web en schrijft het rapport; het dorp voeden (signalen, spanningen)
doet de ConcurrentScout-rol, niet deze skill.
"""
from __future__ import annotations

import html
import logging
import os
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from nooch_village.skills import Skill
from nooch_village.web_read import strip_html

log = logging.getLogger("village.skill.competitor")

# Geen `_DEFAULT_BRANDS` meer (scope 55): de merkenlijst is projectkennis (payload) of een staande
# monitor (config `competitor_brands`), nooit een code-default — die gokte Veja/Moea/… voor élk
# project (het scope-contract van skills.resolve_source_scope).
_SNIPPET_MAX = 300
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


def _snippet(description: str, title: str, source: str) -> str:
    """De strekking van een RSS-item: de `<description>` zonder HTML en zonder de kop zelf.

    Google News zet in de description alleen de gelinkte kop plus de uitgever ('<a>Kop</a>
    <font>Uitgever</font>'); dan blijft na het strippen de uitgever over, en dat is nog steeds
    iets wat een mens wil weten ('… — Footwear News'). Een feed met een echte samenvatting
    levert die samenvatting. Nooit de kop dubbel."""
    tekst = " ".join(html.unescape(strip_html(description or "")).split())
    # De kop staat vooraan in de description (Google News: '<a>Kop</a> Uitgever'); alleen dáár
    # weghalen, niet midden in een echte samenvatting die toevallig de kopwoorden herhaalt. De
    # kop in de feed draagt vaak nog ' - Uitgever' achteraan; de description-kop niet.
    for kop in (title, re.sub(r"\s+-\s+[^-]+$", "", title or "")):
        if kop:
            tekst = re.sub(r"^\s*" + re.escape(kop), " ", tekst, count=1, flags=re.I)
    tekst = " ".join(tekst.split()).strip(" -–—|·")
    if not tekst and source:
        tekst = source
    return tekst[:_SNIPPET_MAX]


def _parse_all(xml_text: str, *, now: datetime, brand: str) -> list[dict]:
    """Pure parser: RSS-XML → álle items met hun publicatiedatum, uitgever en snippet. Geen
    venster-filter (dat doet de cascade). Onparseerbare datum → hard overslaan."""
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
        source = (item.findtext("source") or "").strip()
        items.append({"brand": brand, "title": title, "link": link,
                      "published": published, "date": published.strftime("%Y-%m-%d"),
                      "source": source,
                      "snippet": _snippet(item.findtext("description") or "", title, source)})
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
    description = ("Monitors strategic market news about named competitor brands (funding, launches, "
                   "B-Corp, materials, flagship stores) via Google News RSS with a footwear context; "
                   "picks the shortest window (30/90/365 days) that has news per brand, dedups by link "
                   "and writes a Markdown field report. Fail-closed: no brands or all brands failing is "
                   "an error; no news at all is 'nothing found'.")
    input_schema = ("brands: list[str] (REQUIRED — the competitor brands to search news for, e.g. "
                    "['Vivobarefoot', 'Wildling']; a comma-separated string is accepted) · windows: "
                    "list[int] (optional, days per step, default 30/90/365 from the config) · days: int "
                    "(optional, one fixed window instead of the steps)")
    required_payload = ("brands",)
    output_schema = ("ok: bool, items: list[{brand, title, link, date, source, snippet}], total: int, "
                     "text: str, path: str (the Markdown report), _brands, _windows, errors: {brand: reason} "
                     "| no_data: True, reason | ok: False, error")

    def _brands(self, payload: dict, context) -> list[str]:
        """Merken uit de payload (projectscope), anders de staande monitor uit de config. Leeg = leeg:
        de aanroeper weigert dan zichtbaar (geen code-default)."""
        raw = payload.get("brands")
        if isinstance(raw, str):
            raw = re.split(r"[,\n;]+", raw)               # een planner-string 'Veja, Moea' is ook een lijst
        if raw:
            return [str(b).strip() for b in raw if str(b).strip()]
        conf = str((getattr(context, "settings", {}) or {}).get("competitor_brands", "") or "")
        return [b.strip() for b in conf.split(",") if b.strip()]

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
        payload = payload or {}
        brands = self._brands(payload, context)
        if not brands:
            return {"ok": False, "error": ("geen merken: geef `brands` mee via het project of zet "
                                           "'competitor_brands' in de config — de skill gokt bewust "
                                           "geen merkenlijst (fail-closed)")}
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
                from nooch_village.sleutelmasker import masker
                errors[brand] = masker(exc)
                per_brand[brand] = {"items": [], "window": windows[-1]}
                log.warning("competitor_news: '%s' faalde: %s", brand, masker(exc))
            if i < len(brands) - 1:
                time.sleep(1.0)                          # beleefd

        # Hele run mislukt (alle merken faalden) → geen rapport, fail-closed.
        if (len(errors) == len(brands)
                and all(not v["items"] for v in per_brand.values()) and errors):
            return {"ok": False, "error": f"alle merken faalden: {errors}"}

        items = [{"brand": it["brand"], "title": it["title"], "link": it["link"], "date": it["date"],
                  "source": it.get("source", ""), "snippet": it.get("snippet", "")}
                 for v in per_brand.values() for it in v["items"]]
        path = self._write_report(context, brands, per_brand, windows, now)
        # `_brands`/`_windows`: de echo van de invoer is metadata, geen uitkomst. Tot scope 55 las
        # de wall de vier merknamen die de planner zelf meegaf als "4 results".
        out = {"ok": True, "path": path, "items": items, "total": len(items),
               "_brands": brands, "_windows": windows, "errors": errors}
        if not items:
            out["no_data"] = True
            out["reason"] = (f"no news about {', '.join(brands)} in the last {windows[-1]} days"
                             + (f" ({len(errors)} of {len(brands)} brands failed: "
                                f"{'; '.join(f'{b}: {e[:80]}' for b, e in errors.items())})" if errors else ""))
            return out
        per = ", ".join(f"{b} {len(v['items'])} ({v['window']}d)" for b, v in per_brand.items() if v["items"])
        stil = [b for b, v in per_brand.items() if not v["items"] and b not in errors]
        out["text"] = (f"{len(items)} news item(s) about {len(brands)} brand(s): {per}"
                       + (f"; nothing in {windows[-1]} days for {', '.join(stil)}" if stil else "")
                       + (f"; failed: {', '.join(errors)}" if errors else ""))
        return out

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
                    if it.get("snippet"):
                        lines.append(f"  - {it['snippet']}")
            else:
                lines.append("- _Geen ontwikkelingen in het afgelopen jaar._")
            lines.append("")
        out_dir = os.path.join(getattr(context, "data_dir", "."), "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"competitor_report_{now.strftime('%Y-%m-%d')}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path
