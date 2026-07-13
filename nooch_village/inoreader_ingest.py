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


def ingest_items(items: list, data_dir: str, *, mission: str = "", limit: int = 40,
                 own_brand_terms=("nooch", "nooch.earth"), llm_reason=None) -> dict:
    """Kern-pilot: items → veiligheidsfilter → distill_article → news_proposals (idempotent).
    Fail-closed per item (een kapot/onbruikbaar item stopt de run niet). Geeft een telling terug.
    `llm_reason` is injecteerbaar voor tests; None = de echte LLM via news_distill."""
    from nooch_village.news_distill import NewsProposals, distill_article
    from nooch_village.competitor_brands import CompetitorBrands

    props = NewsProposals(os.path.join(data_dir, "news_proposals.json"))
    try:
        known = CompetitorBrands(os.path.join(data_dir, "competitor_brands.json")).confirmed()
    except Exception:
        known = []

    res = {"fetched": len(items), "blocked": 0, "seen": 0, "distilled": 0,
           "proposed": 0, "own_brand": 0}
    for it in (items[:limit] if limit else items):
        link = (it.get("url") or "").strip()
        title = (it.get("title") or "").strip()
        if not title or not link:
            continue
        if _blocked(link):
            res["blocked"] += 1
            continue
        if props.seen(link):
            res["seen"] += 1
            continue
        art = _to_article(it)
        try:
            d = distill_article(art, mission=mission, known_brands=known, llm_reason=llm_reason)
        except Exception as e:                                   # fail-closed: item overslaan, niet crashen
            log.warning("distill faalde voor %s: %s", link, e)
            props.mark_seen(link)                                # niet eeuwig herproberen op een kapot item
            continue
        props.mark_seen(link)
        if not d:
            continue
        res["distilled"] += 1
        # Eigen-merk-signaal apart labelen: een artikel OVER Nooch is reputatie, geen concurrent-zet.
        blob = (title + " " + art["content"]).lower()
        own_hit = any(t.lower() in blob for t in own_brand_terms)
        if own_hit:
            res["own_brand"] += 1
        rationale = ("[eigen merk] " if own_hit else "") + (d.get("rationale") or "")
        if props.add(d["kind"], d["content"], rationale, art["brand"], title, link):
            res["proposed"] += 1
    return res


def ingest(url: str, data_dir: str, **kw) -> dict:
    """Haal de folder-JSON op en verwerk 'm. Dunne wrapper rond fetch_items + ingest_items."""
    return ingest_items(fetch_items(url), data_dir, **kw)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        from nooch_village.cockpit2 import _load_env
        _load_env()                                              # .env laden (URL + LLM-key), no-quote-conventie
    except Exception as e:
        log.warning("kon .env niet laden: %s", e)
    dd = os.environ.get("NOOCH_DATA_DIR", "data")
    url = (os.environ.get("INOREADER_COMPETITOR_JSON_URL") or "").strip()
    if not url:
        print("✗ zet INOREADER_COMPETITOR_JSON_URL in /opt/noochville/.env (de JSON-URL van de folder Competitor Watch)")
        return 2
    try:
        res = ingest(url, dd)
    except Exception as e:
        print(f"✗ ophalen/verwerken mislukt: {e}")
        return 1
    print(f"📥 Inoreader Competitor Watch: {res['fetched']} opgehaald · {res['blocked']} geblokkeerd "
          f"· {res['seen']} al gezien · {res['distilled']} gedistilleerd · {res['proposed']} nieuwe "
          f"voorstellen ({res['own_brand']} eigen-merk).")
    from nooch_village.news_distill import NewsProposals
    pend = NewsProposals(os.path.join(dd, "news_proposals.json")).pending()
    for p in pend[:res["proposed"]]:
        print(f"  - [{p.get('kind')}] {p.get('content')}  ({p.get('brand')}) — {p.get('rationale', '')[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
