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


def _controleer(resp, bron: str) -> None:
    """In plaats van `resp.raise_for_status()`: die zet de volledige URL — mét `api_key=…` — in de
    foutmelding, en zes aanroepers schreven `str(exc)` door naar wall, store en log (skill-review
    12-09-2026). De melding hier draagt status, reden en het begin van de body, en geen URL."""
    try:
        status = int(getattr(resp, "status_code", 200))
    except (TypeError, ValueError):
        status = 200                                      # een stub zonder statuscode: niets te melden
    if status >= 400:
        from nooch_village.sleutelmasker import http_fout
        raise RuntimeError(http_fout(resp, bron))


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
    _controleer(resp, "SerpAPI")
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


_BRAVE_SLEUTEL_PREFIX = "BSA"


def _brave_fout(resp, key: str) -> str:
    """De foutmelding die Brave zélf geeft, plus de aanwijzing die hem bruikbaar maakt.

    GEMETEN AANLEIDING (6 september 2026). Brave gaf 422 op elk verzoek. `raise_for_status()` levert
    dan "422 Client Error: for url: …" en verder niets, want de reden staat in de RESPONSE BODY die
    hij weggooit. Die body zei letterlijk `SUBSCRIPTION_TOKEN_INVALID`. In de sleutel in `.env` was
    bij het plakken een teken meegekomen: hij begon met `jBSA` in plaats van `BSA`.

    Dat kostte een los diagnose-script en drie rondes voor iets wat de API in één zin had verteld.
    De statuscode alleen stuurde bovendien de verkeerde kant op: 422 leest als "mijn verzoek klopt
    niet" terwijl het hier authenticatie was — de meeste API's geven daar 401 voor.

    De prefix-hint staat er alleen bij een AUTHENTICATIE-fout, en de sleutel wordt nooit afgekeurd op
    zijn vorm: de API is de autoriteit over geldigheid, wij maken de melding alleen bruikbaar. Zou dit
    vooraf weigeren, dan breekt het zodra Brave zijn sleutelformaat wijzigt.
    """
    detail = code = ""
    try:
        fout = (resp.json() or {}).get("error") or {}
        code = str(fout.get("code") or "")
        detail = str(fout.get("detail") or "")
    except Exception:
        detail = (resp.text or "")[:200]
    melding = f"Brave gaf {resp.status_code}"
    if code or detail:
        melding += f" — {code}{': ' if code and detail else ''}{detail}"
    if "TOKEN" in code.upper() or "auth" in detail.lower():
        gezien = f"{key[:4]}…" if key else "(leeg)"
        melding += (f" · de sleutel begint met {gezien} en zou met "
                    f"'{_BRAVE_SLEUTEL_PREFIX}' moeten beginnen; controleer BRAVE_API_KEY in .env op "
                    f"een meegeplakt teken"
                    if not key.startswith(_BRAVE_SLEUTEL_PREFIX) else
                    " · de sleutelvorm klopt, dus controleer of het abonnement op 'Data for Search' "
                    "actief is")
    return melding


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
    if resp.status_code >= 400:
        raise RuntimeError(_brave_fout(resp, key))
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
        _controleer(resp, "SerpAPI news")
        data = resp.json()
    except Exception as exc:
        from nooch_village.sleutelmasker import masker
        log.info("web_read: google_news faalde (%s): %s", query[:40], masker(exc))
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
