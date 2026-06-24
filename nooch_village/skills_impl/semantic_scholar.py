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
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import json
from nooch_village.skills import Skill

_BASE   = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,year,citationCount,tldr"


class SemanticScholarSkill(Skill):
    name = "semscholar_tldr"
    cost = "rate_limited"
    optional_env = ("SEMANTIC_SCHOLAR_API_KEY",)
    description = (
        "Zoekt wetenschappelijke papers op via Semantic Scholar (tldr-veld, "
        "optionele API-key via .env, backoff bij 429, locale-bewust, fail-closed)."
    )

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
