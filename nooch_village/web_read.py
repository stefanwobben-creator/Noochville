"""Gedeelde web-leeshelpers: zoekopdrachten (echte URLs) + pagina lezen + HTML strippen.

Eén bron voor competitor_discover, linkbuilding, claim_evidence en web_zoek (geen dubbele
fetch-logica). Dependency-vrij op stdlib na `requests` (al een dependency). Faalt closed: een
leesfout geeft een lege string.

TWEE ZOEKMACHINES, ÉÉN VORM. `serpapi_search` (Google via SerpAPI) en `brave_search` (Brave's eigen
index) leveren allebei [{title, link, snippet}] met dezelfde signatuur. Dat normaliseren hoort hier,
bij de bron: `web_zoek` mag niet hoeven weten wélke motor er draaide, anders zit de motorkeuze straks
op vier plekken.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("village.web_read")

_ENDPOINT = "https://serpapi.com/search.json"
_UA = "Mozilla/5.0 (NoochVille market monitor; +https://nooch.earth)"


def strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def serpapi_search(query: str, key: str, *, num: int = 10, gl: str = "", hl: str = "") -> list[dict]:
    """Google-organic via SerpAPI → [{title, link, snippet}] met échte URLs (geen redirects).

    `snippet` is toegevoegd op 06-09-2026 voor `web_zoek`: het fragment is voor een mens het
    waardevolste veld van een zoekresultaat (je leest eraan af óf je die pagina wilt openen), en
    SerpAPI leverde het altijd al mee — wij gooiden het weg. Additief: de drie bestaande aanroepers
    (competitor_discover, linkbuilding, claim_evidence) lezen title/link en merken er niets van.

    `gl`/`hl` zijn land- en taalvoorkeur. Leeg = Google's eigen keuze, precies zoals voorheen.
    """
    import requests
    params = {"engine": "google", "q": query, "num": num, "api_key": key}
    if gl:
        params["gl"] = gl
    if hl:
        params["hl"] = hl
    resp = requests.get(_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    out = []
    for item in data.get("organic_results", []):
        link = (item.get("link") or "").strip()
        if link:
            out.append({"title": (item.get("title") or "").strip(), "link": link,
                        "snippet": (item.get("snippet") or "").strip()})
    return out


_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _zonder_markering(s: str) -> str:
    """Brave's `<strong>`-markering eruit, ZONDER spatie ervoor in de plaats.

    `strip_html` zet een spatie op de plek van elke tag, want daar gaat het om hele pagina's waar
    `</p><p>` een woordgrens is. Hier is de tag inline: hij staat om het gezochte woord midden in een
    zin. Een spatie levert dan "Sales rose 30% ." op, en dat staat straks zo op de wall."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def brave_search(query: str, key: str, *, num: int = 10, gl: str = "", hl: str = "") -> list[dict]:
    """Brave's EIGEN index → [{title, link, snippet}], dezelfde vorm als `serpapi_search`.

    Waarom dezelfde vorm en niet Brave's eigen velden: `web_zoek` mag niet hoeven weten wélke
    motor er draaide. Normaliseren hoort hier, bij de bron, niet bij de skill.

    Brave zet `<strong>`-tags om de gezochte woorden in de description. Die halen we eruit met
    `_zonder_markering` en niet met `strip_html`, want die laatste zet er een spatie voor in de
    plaats en dan leest de wall "Sales rose 30% .".

    `gl`/`hl` heten bij Brave `country` en `search_lang`; de namen zijn hier gelijkgetrokken met
    `serpapi_search` zodat de aanroeper één signatuur kent. `count` gaat bij Brave tot 20.
    """
    import requests
    params = {"q": query, "count": max(1, min(int(num), 20))}
    if gl:
        params["country"] = gl
    if hl:
        params["search_lang"] = hl
    resp = requests.get(_BRAVE_ENDPOINT, params=params, timeout=20,
                        headers={"X-Subscription-Token": key, "Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    out = []
    for item in ((data.get("web") or {}).get("results") or []):
        link = (item.get("url") or "").strip()
        if link:
            out.append({"title": _zonder_markering(item.get("title")), "link": link,
                        "snippet": _zonder_markering(item.get("description"))})
    return out


def serpapi_news(query: str, key: str, *, num: int = 10) -> list[dict]:
    """Google News via SerpAPI → [{title, link, date, source}]. Breed: alleen de term, geen
    extra filters (de aanleiding bepalen we daarna). Echte URLs. Fail-closed → []."""
    import requests
    if not key or not query:
        return []
    params = {"engine": "google_news", "q": query, "api_key": key}
    try:
        resp = requests.get(_ENDPOINT, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.info("web_read: google_news faalde (%s): %s", query[:40], exc)
        return []
    out = []
    for item in data.get("news_results", []):
        for r in (item.get("stories") or [item]):        # SerpAPI groepeert soms in 'stories'
            link = (r.get("link") or "").strip()
            if link:
                src = r.get("source")
                out.append({"title": (r.get("title") or "").strip(), "link": link,
                            "date": (r.get("date") or "").strip(),
                            "source": (src.get("name") if isinstance(src, dict) else src) or ""})
    return out[:num]


def fetch_text(url: str, *, timeout: int = 20) -> str:
    """Lees een echte URL en geef platte tekst terug. Faalt → lege string (fail-closed)."""
    if not url:
        return ""
    try:
        import requests
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout,
                            allow_redirects=True)
        resp.raise_for_status()
        return strip_html(resp.text)
    except Exception as exc:
        log.info("web_read: pagina lezen faalde (%s): %s", url[:60], exc)
        return ""


def domain_of(url: str) -> str:
    """Korte bron-naam uit een URL (bijv. 'goodonyou.eco')."""
    import urllib.parse
    netloc = urllib.parse.urlparse(url or "").netloc
    return netloc[4:] if netloc.startswith("www.") else netloc
