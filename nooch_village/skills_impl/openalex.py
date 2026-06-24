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


def _parse_year_groups(data: dict) -> dict[int, int]:
    """Zet een OpenAlex group_by=publication_year-respons om naar {jaar: aantal}.
    Niet-numerieke sleutels ('unknown'/None) worden overgeslagen."""
    out: dict[int, int] = {}
    for g in (data.get("group_by") or []):
        try:
            year = int(g.get("key"))
        except (TypeError, ValueError):
            continue
        out[year] = int(g.get("count", 0))
    return out


def relative_attention(term_counts: dict[int, int],
                       total_counts: dict[int, int]) -> dict[int, float]:
    """Relatieve academische aandacht per jaar: aandeel van de term in álle werken dat jaar.
    Analoog aan ngram's relatieve frequentie, dus vergelijkbaar. Jaren zonder totaal worden
    overgeslagen (geen deling door nul). Gesorteerd op jaar."""
    out: dict[int, float] = {}
    for year, c in term_counts.items():
        tot = total_counts.get(year, 0)
        if tot > 0:
            out[year] = c / tot
    return dict(sorted(out.items()))


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
    required_env = ("OPENALEX_API_KEY",)
    optional_env = ("openalex_mailto",)
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

        # Jaar-aandeel-modus: relatieve academische aandacht per jaar (voor de lange-boog-
        # voortzetting voorbij de ngram-cutoff). Zelfde bron/capaciteit, andere query.
        if payload.get("mode") == "yearly":
            return self._yearly(term, locale, mailto, key, ua)

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

    def _yearly(self, term: str, locale: str, mailto: str, key: str, ua: str) -> dict:
        """Twee group_by=publication_year-calls (term + totaal) → relatief aandeel per jaar."""
        creds = (f"&mailto={urllib.parse.quote(mailto)}"
                 f"&api_key={urllib.parse.quote(key)}")
        q = urllib.parse.quote(term)
        term_url  = f"{_BASE}?search={q}&group_by=publication_year{creds}"
        total_url = f"{_BASE}?group_by=publication_year{creds}"

        term_data  = self._fetch_with_backoff(
            urllib.request.Request(term_url, headers={"User-Agent": ua}))
        total_data = self._fetch_with_backoff(
            urllib.request.Request(total_url, headers={"User-Agent": ua}))

        series = relative_attention(_parse_year_groups(term_data),
                                    _parse_year_groups(total_data))
        time.sleep(0.5)
        if not series:
            return {"term": term, "locale": locale, "mode": "yearly",
                    "no_data": True, "reason": "geen jaardata gevonden", "series": {}}
        return {"term": term, "locale": locale, "mode": "yearly", "series": series}

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
