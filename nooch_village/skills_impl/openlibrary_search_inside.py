"""OpenLibrarySearchInsideSkill — zoekt boeken op OpenLibrary en haalt relevante titels,
auteurs en onderwerpen op voor een term.

Endpoint: https://openlibrary.org/search.json (open, geen key vereist)
Fail-closed: netwerk- of parse-fouten retourneren {"error": ...}, nooit mock-data.
"""
from __future__ import annotations
import time
import urllib.request
import urllib.parse
import json
from nooch_village.skills import Skill


class OpenlibrarySearchInsideSkill(Skill):
    name = "openlibrary_search_inside"
    input_schema = "term: str (zoekterm in boek-voltekst). optioneel: limit: int"
    required_payload = ("term",)
    output_schema = "lijst: total: int, hits: list[{title, ...}] | error"
    cost = "free"
    description = (
        "Zoekt op OpenLibrary naar boeken die een term bevatten en retourneert "
        "titels, auteurs en onderwerp-tags (geen key vereist, fail-closed)."
    )

    def run(self, payload: dict, context) -> dict:
        term = payload.get("term", "").strip()
        if not term:
            return {"error": "geen term opgegeven", "hits": []}

        limit = int(payload.get("limit", 5))
        q = urllib.parse.quote(term)
        url = (
            f"https://openlibrary.org/search.json"
            f"?q={q}&limit={limit}"
            f"&fields=title,author_name,subject,first_sentence,publish_year"
        )

        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "NoochVillage/1.0 (nooch.earth research bot)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            return {"error": f"OpenLibrary niet bereikbaar: {e}", "hits": []}

        hits = []
        for doc in data.get("docs", []):
            title = doc.get("title", "")
            authors = (doc.get("author_name") or [])[:2]
            subjects = (doc.get("subject") or [])[:5]
            year = (doc.get("publish_year") or [None])[0]
            first_sentence = doc.get("first_sentence")
            if isinstance(first_sentence, dict):
                first_sentence = first_sentence.get("value", "")
            hits.append({
                "source":   "openlibrary",
                "title":    title,
                "authors":  authors,
                "year":     year,
                "subjects": subjects,
                "snippet":  (first_sentence or "")[:200],
            })

        time.sleep(0.5)   # vriendelijk voor het openbare endpoint
        return {
            "term":  term,
            "total": data.get("numFound", len(hits)),
            "hits":  hits,
        }
