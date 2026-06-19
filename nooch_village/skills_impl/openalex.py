"""OpenAlexSkill — capability "openalex_evidence".

Zoekt academische werken op via de OpenAlex API.
Authenticatie via OPENALEX_API_KEY (vereist — skill faalt bewust closed zonder key).
Polite pool: mailto-adres in de User-Agent voor hogere rate-limit.
Mailto komt uit context.settings["openalex_mailto"] (settings.ini of .env).

Segmentatie:
  Elke aanroep draagt een `locale`-sleutel door in de output.
  Resultaten gesorteerd op citaties (meest geciteerd eerst).
  `no_data: True` onderscheidt "API werkt, maar niets gevonden" van een echte fout.

Rate-limit-gedrag:
  Bij HTTP 429: exponentiële backoff (2**attempt + jitter), max 4 pogingen.
  Daarna: raise (use_skill vangt dit op als {"error": ...}).

Fail-closed: ontbrekende key of definitieve fout → raise, nooit mock-data.
"""
from __future__ import annotations
import os
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import json
from nooch_village.skills import Skill

_BASE   = "https://api.openalex.org/works"
_SELECT = ("id,title,publication_year,cited_by_count,"
           "abstract_inverted_index,primary_topic,authorships")


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """Reconstrueer abstracttekst vanuit OpenAlex inverted index."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[p] for p in sorted(words.keys()))[:400]


class OpenalexSkill(Skill):
    name = "openalex_evidence"
    needs_secret = True
    cost = "rate_limited"
    description = (
        "Haalt academische evidentie op via OpenAlex (API-key vereist, polite pool, "
        "gesorteerd op citaties, backoff bij 429, locale-bewust, fail-closed)."
    )

    def run(self, payload: dict, context) -> dict:
        key = (getattr(context, "settings", {}).get("OPENALEX_API_KEY")
               or os.getenv("OPENALEX_API_KEY"))
        if not key:
            raise RuntimeError(
                "OPENALEX_API_KEY ontbreekt in .env — openalex_evidence faalt bewust closed"
            )

        term   = payload.get("term", "").strip()
        locale = payload.get("locale", "")
        if not term:
            return {"error": "geen term opgegeven", "hits": [], "locale": locale}

        limit  = int(payload.get("limit", 5))
        mailto = getattr(context, "settings", {}).get("openalex_mailto", "info@nooch.earth")
        ua     = f"NoochVillage/1.0 (nooch.earth; mailto:{mailto})"

        q   = urllib.parse.quote(term)
        url = (f"{_BASE}?search={q}"
               f"&per_page={limit}"
               f"&sort=cited_by_count:desc"
               f"&select={_SELECT}"
               f"&mailto={urllib.parse.quote(mailto)}"
               f"&api_key={urllib.parse.quote(key)}")

        req  = urllib.request.Request(url, headers={"User-Agent": ua})
        data = self._fetch_with_backoff(req)

        results = data.get("results", [])
        total   = data.get("meta", {}).get("count", len(results))

        if total == 0 or not results:
            time.sleep(0.5)
            return {"term": term, "locale": locale, "total": 0,
                    "no_data": True, "reason": "geen werken gevonden voor deze term",
                    "hits": []}

        hits = []
        for work in results:
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in (work.get("authorships") or [])[:3]
            ]
            topic    = (work.get("primary_topic") or {}).get("display_name", "")
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            hits.append({
                "source":    "openalex",
                "locale":    locale,
                "title":     work.get("title") or "",
                "authors":   [a for a in authors if a],
                "year":      work.get("publication_year"),
                "citations": work.get("cited_by_count", 0),
                "topic":     topic,
                "abstract":  abstract,
            })

        time.sleep(0.5)
        return {"term": term, "locale": locale, "total": total, "hits": hits}

    def _fetch_with_backoff(self, req, timeout: int = 12, max_retries: int = 4) -> dict:
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
                    continue
                raise
        raise RuntimeError("OpenAlex rate-limit overschreden na 4 pogingen")
