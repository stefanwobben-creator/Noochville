"""Gedeelde web-leeshelpers: SerpAPI-zoekopdracht (echte URLs) + pagina lezen + HTML strippen.

Eén bron voor competitor_discover en linkbuilding (geen dubbele fetch-logica). Dependency-vrij
op stdlib na `requests` (al een dependency). Faalt closed: een leesfout geeft een lege string.
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


def serpapi_search(query: str, key: str, *, num: int = 10) -> list[dict]:
    """Google-organic via SerpAPI → [{title, link}] met échte URLs (geen redirects)."""
    import requests
    params = {"engine": "google", "q": query, "num": num, "api_key": key}
    resp = requests.get(_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    out = []
    for item in data.get("organic_results", []):
        link = (item.get("link") or "").strip()
        if link:
            out.append({"title": (item.get("title") or "").strip(), "link": link})
    return out


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
