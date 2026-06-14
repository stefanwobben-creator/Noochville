"""SemanticScholarSkill — haalt wetenschappelijke papers op via de Semantic Scholar API.

Endpoint: https://api.semanticscholar.org/graph/v1/paper/search (open, geen key vereist)
Rate-limit: ~100 req/5 min zonder key. Wacht 1s tussen aanroepen.
Fail-closed: netwerk- of parse-fouten retourneren {"error": ...}, nooit mock-data.
"""
from __future__ import annotations
import time
import urllib.request
import urllib.parse
import json
from nooch_village.skills import Skill

_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,authors,year,citationCount,fieldsOfStudy"


class SemanticScholarSkill(Skill):
    name = "semantic_scholar"
    description = (
        "Zoekt wetenschappelijke papers op via Semantic Scholar Graph API "
        "(geen key vereist, fail-closed)."
    )

    def run(self, payload: dict, context) -> dict:
        term = payload.get("term", "").strip()
        if not term:
            return {"error": "geen term opgegeven", "hits": []}

        limit = int(payload.get("limit", 5))
        q = urllib.parse.quote(term)
        url = f"{_BASE}?query={q}&limit={limit}&fields={_FIELDS}"

        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "NoochVillage/1.0 (nooch.earth research bot)"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            return {"error": f"Semantic Scholar niet bereikbaar: {e}", "hits": []}

        hits = []
        for paper in data.get("data", []):
            abstract = (paper.get("abstract") or "")[:300]
            hits.append({
                "source":        "semantic_scholar",
                "title":         paper.get("title", ""),
                "authors":       [a.get("name", "") for a in (paper.get("authors") or [])[:3]],
                "year":          paper.get("year"),
                "citations":     paper.get("citationCount", 0),
                "fields":        paper.get("fieldsOfStudy") or [],
                "snippet":       abstract,
            })

        time.sleep(1.0)   # vriendelijk voor het gratis endpoint
        return {
            "term":  term,
            "total": data.get("total", len(hits)),
            "hits":  hits,
        }
