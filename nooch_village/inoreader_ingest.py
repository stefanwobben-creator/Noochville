"""inoreader_ingest — pilot: haal een gecureerde Inoreader-folder (JSON Feed) op en distilleer de
artikelen tot voorstellen in de review-wachtrij (news_proposals).

Read-only, fail-closed, idempotent op de artikel-URL (NewsProposals.seen). De feed-URL bevat een
persoonlijke user-token en komt daarom UIT DE OMGEVING (INOREADER_COMPETITOR_JSON_URL), nooit uit de
repo. Eén bron van waarheid voor de intelligentie blijft de village-distill (news_distill); Inoreader
doet alleen de curatie/verzameling. Fase 1 leest alleen de kop (zoals distill_article nu werkt); het
volledige-tekst-gebruik en een cockpit-knop/puls zijn bewust fase 2.
"""
from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlparse

log = logging.getLogger("village.inoreader")

# Adult/irrelevante domeinen die keyword-feeds oppikken op woorden als 'barefoot'. Substring op host.
# Dit is een VANGNET; de echte curatie hoort in de Inoreader-folder (bron). Breid gerust uit.
_BLOCK_DOMAINS = (
    "rawporn", "femdomss", "pimpandhost", "pornhub", "xvideos", "xhamster",
    "onlyfans", "k2s.cc", "filesor", "fapel", "erome",
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _blocked(url: str) -> bool:
    h = _host(url)
    return any(b in h for b in _BLOCK_DOMAINS)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _to_article(item: dict) -> dict:
    """Map een JSON-Feed-item naar het article-formaat dat news_distill verwacht. `brand` = het
    bron-domein als grove context-hint (distill_article gebruikt 'm alleen in de prompt)."""
    url = (item.get("url") or "").strip()
    return {
        "title": (item.get("title") or "").strip(),
        "link": url,
        "date": item.get("date_published") or "",
        "brand": _host(url),
        "content": _strip_html(item.get("content_html") or "")[:2000],
    }


def fetch_items(url: str) -> list:
    """Haal de JSON-Feed op en geef de items-lijst. Fail-loud (raise) bij netwerk-/parse-fout, zodat
    de caller een stille lege run kan onderscheiden van 'niets nieuws'."""
    import requests
    r = requests.get(url, timeout=30, headers={"User-Agent": "NoochVille ingest (+https://nooch.earth)"})
    r.raise_for_status()
    data = r.json()
    items = data.get("items") or []
    return items if isinstance(items, list) else []


def ingest_feed_items(items: list, *, role: str, feed: str, data_dir: str, mission: str = "",
                      limit: int = 40, own_brand_terms=("nooch", "nooch.earth"), llm_reason=None) -> dict:
    """Verwerk de items van één feed naar de RadarStore van de gekoppelde rol (status 'wacht'). Strenge
    distill (precisie), idempotent op artikel-URL, fail-closed per item. Houdt een trace bij (--debug)."""
    from nooch_village.news_distill import distill_article
    from nooch_village.competitor_brands import CompetitorBrands
    from nooch_village.radar_store import RadarStore

    radar = RadarStore(os.path.join(data_dir, "radar.json"))
    try:
        known = CompetitorBrands(os.path.join(data_dir, "competitor_brands.json")).confirmed()
    except Exception:
        known = []

    res = {"fetched": len(items), "blocked": 0, "seen": 0, "distilled": 0,
           "proposed": 0, "own_brand": 0, "trace": []}
    for it in (items[:limit] if limit else items):
        link = (it.get("url") or "").strip()
        title = (it.get("title") or "").strip()
        if not title or not link:
            res["trace"].append(("(geen titel/link)", "overgeslagen"))
            continue
        if _blocked(link):
            res["blocked"] += 1
            res["trace"].append((title[:75], "geblokkeerd"))
            continue
        if radar.seen(link):
            res["seen"] += 1
            res["trace"].append((title[:75], "al gezien"))
            continue
        art = _to_article(it)
        try:
            d = distill_article(art, mission=mission, known_brands=known, llm_reason=llm_reason, strict=True)
        except Exception as e:                                   # fail-closed: item overslaan, niet crashen
            log.warning("distill faalde voor %s: %s", link, e)
            radar.mark_seen(link)
            res["trace"].append((title[:75], "distill-fout"))
            continue
        radar.mark_seen(link)
        if not d:
            res["trace"].append((title[:75], "geen"))
            continue
        res["distilled"] += 1
        # Eigen-merk-signaal apart labelen: een artikel OVER Nooch is reputatie, geen concurrent-zet.
        blob = (title + " " + art["content"]).lower()
        own_hit = any(t.lower() in blob for t in own_brand_terms)
        if own_hit:
            res["own_brand"] += 1
        rationale = ("[eigen merk] " if own_hit else "") + (d.get("rationale") or "")
        if radar.add(role=role, feed=feed, kind=d["kind"], content=d["content"],
                     rationale=rationale, source=art["brand"], link=link):
            res["proposed"] += 1
        res["trace"].append((title[:75], d["kind"] + (" [eigen merk]" if own_hit else "")))
    return res


def ingest_feed(url: str, *, role: str, feed: str, data_dir: str, **kw) -> dict:
    """Haal één feed-JSON op en verwerk 'm naar de radar van de rol."""
    return ingest_feed_items(fetch_items(url), role=role, feed=feed, data_dir=data_dir, **kw)


def ingest_all(data_dir: str, *, limit: int = 40) -> dict:
    """Loop de geconfigureerde feeds langs (alleen 'precisie' in deze stap) en route elk naar de radar
    van de gekoppelde rol. Geeft {feed-label: telling}. 'recall'-feeds (materials) volgen in 2b."""
    from nooch_village.radar_store import load_feeds
    out = {}
    for f in load_feeds(data_dir):
        if f.get("mode") != "precisie":
            continue
        url = (os.environ.get(f.get("env", "")) or "").strip()
        if not url:
            continue
        label = f.get("label") or f.get("env")
        try:
            out[label] = ingest_feed(url, role=f["role"], feed=label, data_dir=data_dir, limit=limit)
        except Exception as e:
            print(f"feed '{label}' overgeslagen: {e}")
    return out


def main(argv=None) -> int:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="inoreader_ingest")
    ap.add_argument("--reset", action="store_true", help="leeg de radar (alle feeds) vóór je draait")
    ap.add_argument("--limit", type=int, default=40, help="max artikelen per feed")
    ap.add_argument("--debug", action="store_true", help="toon per artikel de titel + het oordeel")
    args = ap.parse_args(argv)
    try:
        from nooch_village.cockpit2 import _load_env
        _load_env()
    except Exception as e:
        log.warning("kon .env niet laden: %s", e)
    dd = os.environ.get("NOOCH_DATA_DIR", "data")
    store = os.path.join(dd, "radar.json")
    if args.reset:
        try:
            if os.path.exists(store):
                os.remove(store)
            print("-> radar geleegd.")
        except OSError as e:
            print(f"kon de radar niet legen: {e}")
            return 1
    results = ingest_all(dd, limit=args.limit)
    if not results:
        print("geen feeds verwerkt - staan de INOREADER_*_JSON_URL's in .env, met een 'precisie'-feed?")
        return 2
    for label, res in results.items():
        print(f"{label}: {res['fetched']} opgehaald - {res['blocked']} geblokkeerd - {res['seen']} al gezien "
              f"- {res['distilled']} gedistilleerd - {res['proposed']} nieuw ({res['own_brand']} eigen-merk).")
        if args.debug:
            for t, v in res.get("trace", []):
                print(f"    - [{v}] {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
