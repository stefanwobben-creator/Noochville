"""OpenAlexSkill — zoekt academische werken op via de OpenAlex API.

Endpoint: https://api.openalex.org/works (open, geen key vereist)
Beleefd gebruik: User-Agent met e-mailadres (polite pool, hogere rate-limit).
Fail-closed: netwerk- of parse-fouten retourneren {"error": ...}, nooit mock-data.
"""
from __future__ import annotations
import time
import urllib.request
import urllib.parse
import json
from nooch_village.skills import Skill

_BASE = "https://api.openalex.org/works"
# Polite pool: hogere rate-limit als User-Agent een e-mailadres bevat
_USER_AGENT = "NoochVillage/1.0 (nooch.earth; mailto:info@nooch.earth)"


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """Reconstrueer de abstracttekst vanuit OpenAlex's inverted index."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[p] for p in sorted(words.keys()))[:300]


class OpenalexSkill(Skill):
    name = "openalex"
    description = (
        "Zoekt academische werken op via OpenAlex (geen key vereist, polite pool, "
        "fail-closed). Retourneert titels, jaar, citaties en gereconstrueerde abstracten."
    )

    def run(self, payload: dict, context) -> dict:
        term = payload.get("term", "").strip()
        if not term:
            return {"error": "geen term opgegeven", "hits": []}

        limit = int(payload.get("limit", 5))
        q = urllib.parse.quote(term)
        select = "id,title,publication_year,cited_by_count,abstract_inverted_index,authorships,primary_topic"
        url = f"{_BASE}?search={q}&per-page={limit}&select={select}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            return {"error": f"OpenAlex niet bereikbaar: {e}", "hits": []}

        hits = []
        for work in data.get("results", []):
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in (work.get("authorships") or [])[:3]
            ]
            topic = (work.get("primary_topic") or {}).get("display_name", "")
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            hits.append({
                "source":    "openalex",
                "title":     work.get("title", ""),
                "authors":   authors,
                "year":      work.get("publication_year"),
                "citations": work.get("cited_by_count", 0),
                "topic":     topic,
                "snippet":   abstract,
            })

        time.sleep(0.5)
        return {
            "term":  term,
            "total": data.get("meta", {}).get("count", len(hits)),
            "hits":  hits,
        }
