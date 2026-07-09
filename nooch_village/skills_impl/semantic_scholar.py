"""SemanticScholarSkill — capability "semscholar_tldr".

Zoekt wetenschappelijke papers op via de Semantic Scholar Graph API.
Gebruikt het `tldr`-veld als machinaal gegenereerde één-regel-distillatie.

Authenticatie:
  Geen key vereist voor basisgebruik (~100 req / 5 min).
  Optioneel: zet SEMANTIC_SCHOLAR_API_KEY in .env voor hogere limieten.

Rate-limit-gedrag:
  Bij HTTP 429: exponentiële backoff (2 × attempt + 1s jitter), max 4 pogingen.
  Daarna fail-closed: {"error": "rate-limit overschreden na 4 pogingen"}.

Segmentatie:
  Elke aanroep draagt een `locale`-sleutel door in de output.
  `no_data: True` onderscheidt "niets gevonden" van een netwerk-fout.

Fail-closed: bij élke fout retourneert de skill een dict met "error"; nooit mock-data.
"""
from __future__ import annotations
import logging
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import json
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_BASE   = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,year,citationCount,tldr"
_AUTHOR_SEARCH = "https://api.semanticscholar.org/graph/v1/author/search"


class SemanticScholarSkill(DataSourceSkill):
    name = "semscholar_tldr"
    input_schema = "term: str (zoekterm). optioneel: limit: int, locale: str"
    required_payload = ("term",)
    output_schema = "lijst: total: int, hits: list[{title, year, citations, tldr, abstract}] | no_data | error"
    SOURCE = "semanticscholar"
    # Snapshot-bron (cumulatieve auteur-tellers, groeien traag) → maandelijks meten. De tegel toont de
    # genormaliseerde delta i.p.v. de oplopende stand (erft het OpenAlex-snapshot-patroon).
    kind = "snapshot"
    DEFAULT_FREQUENCY = "monthly"
    cost = "rate_limited"
    optional_env = ("SEMANTIC_SCHOLAR_API_KEY",)
    description = (
        "Zoekt wetenschappelijke papers op via Semantic Scholar (tldr-veld, "
        "optionele API-key via .env, backoff bij 429, locale-bewust, fail-closed)."
    )

    def available_metrics(self, context=None) -> list[str]:
        """Cumulatieve tellers van de gemeten auteur: totaal aantal publicaties en citaties."""
        return ["papers", "citations"]

    def is_configured(self, context) -> bool:
        """Keyless: Semantic Scholar werkt zonder key (rate-limited); een key geeft alleen hogere
        limieten. 'Niet geconfigureerd' geldt hier dus niet — een lege reeks is een echte fout of
        nog-niet-gemeten, niet ontbrekende creds."""
        return True

    def daily_values(self, context, datum: str) -> dict:
        """Snapshot van de cumulatieve tellers (paperCount/citationCount) van de top-auteur die matcht op
        de missie-query (`semanticscholar_query`, curator-instelbaar zoals openalex_query). Legt de STAND
        vast (geen verschil — dat leidt de tegel bij weergave af); `datum` is het periode-LABEL (monthly),
        geen historische query-datum. Keyless; optionele key voor hogere limieten. Fail-closed per veld."""
        out = {"papers": None, "citations": None}
        settings = getattr(context, "settings", {}) or {}
        query = (settings.get("semanticscholar_query") or "regenerative agriculture").strip()
        api_key = settings.get("SEMANTIC_SCHOLAR_API_KEY", "")
        url = (f"{_AUTHOR_SEARCH}?query={urllib.parse.quote(query)}"
               f"&fields=paperCount,citationCount&limit=1")
        headers = {"User-Agent": "NoochVillage/1.0 (nooch.earth research bot)"}
        if api_key:
            headers["x-api-key"] = api_key
        data = self._fetch_with_backoff(url, headers)
        if isinstance(data, str):                 # fout-string uit de backoff-helper
            log.warning("Semantic Scholar daily_values faalde (%s): %s", query, data)
            return out
        results = data.get("data", [])
        if not results:
            return out                            # geen auteur gevonden → None (geen 'dood')
        a = results[0]
        out["papers"] = int(a.get("paperCount", 0) or 0)
        out["citations"] = int(a.get("citationCount", 0) or 0)
        return out

    def run(self, payload: dict, context) -> dict:
        term   = payload.get("term", "").strip()
        locale = payload.get("locale", "")
        if not term:
            return {"error": "geen term opgegeven", "hits": [], "locale": locale}

        limit  = int(payload.get("limit", 5))
        api_key = getattr(context, "settings", {}).get("SEMANTIC_SCHOLAR_API_KEY", "")

        q   = urllib.parse.quote(term)
        url = f"{_BASE}?query={q}&limit={limit}&fields={_FIELDS}"

        headers: dict[str, str] = {
            "User-Agent": "NoochVillage/1.0 (nooch.earth research bot)"}
        if api_key:
            headers["x-api-key"] = api_key

        data = self._fetch_with_backoff(url, headers)
        if isinstance(data, str):   # fout-string
            return {"error": data, "hits": [], "term": term, "locale": locale}

        papers = data.get("data", [])
        total  = data.get("total", len(papers))

        if total == 0 or not papers:
            return {"term": term, "locale": locale, "total": 0,
                    "no_data": True, "reason": "geen papers gevonden voor deze term",
                    "hits": []}

        hits = []
        for paper in papers:
            tldr_obj = paper.get("tldr") or {}
            tldr     = tldr_obj.get("text", "") if isinstance(tldr_obj, dict) else ""
            abstract = (paper.get("abstract") or "")[:300]
            hits.append({
                "source":    "semantic_scholar",
                "locale":    locale,
                "title":     paper.get("title") or "",
                "year":      paper.get("year"),
                "citations": paper.get("citationCount", 0),
                "tldr":      tldr,
                "abstract":  abstract,
            })

        time.sleep(1.0)
        return {"term": term, "locale": locale, "total": total, "hits": hits}

    def _fetch_with_backoff(self, url: str, headers: dict,
                            max_retries: int = 4) -> dict | str:
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=14) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    if attempt < max_retries - 1:
                        delay = 2 ** (attempt + 1) + random.uniform(0, 1)
                        time.sleep(delay)
                        continue
                    return "rate-limit overschreden na 4 pogingen (HTTP 429)"
                return f"HTTP {e.code}: {e.reason}"
            except Exception as e:
                return f"Semantic Scholar niet bereikbaar: {e}"
        return "rate-limit overschreden na 4 pogingen"
