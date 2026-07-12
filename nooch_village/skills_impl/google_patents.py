"""Google Patents — keyless wereldwijde patent-zoekskill, het alternatieve pad voor de skill-ladder
wanneer `epo_patents` (OPS) een fout geeft (De Kroniek: dode route → alternatief pad).

Gebruikt het publieke xhr/query-JSON-endpoint van patents.google.com (geen key/OAuth, in tegenstelling
tot EPO OPS). Zelfde lijst-archetype als epo_patents ({term, total, patents:[...], no_data|error}) zodat
de ladder de resultaten identiek classificeert en het uitvoer-primitief ze afvinkt.

Fail-closed: netwerk-/HTTP-/parse-fout → {"error": ...} (geen crash); lege set → geldige no_data.
Fragieler dan een officiële API (ongedocumenteerd endpoint, kan van vorm wijzigen) — daarom bewust de
tweede tree, niet de eerste. De parse is los getest op een vaste sample (geen netwerk in de test).
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_ENDPOINT = "https://patents.google.com/xhr/query"
_UA = "Mozilla/5.0 (compatible; NoochVille/1.0; +https://nooch.earth)"   # zonder UA geeft het endpoint 403


class GooglePatentsSkill(DataSourceSkill):
    name = "google_patents"
    SOURCE = "google_patents"              # research-skill, geen dagobservatie (net als epo_patents)
    kind = "snapshot"
    cost = "rate_limited"                  # ongedocumenteerd endpoint — bescheiden gebruik
    needs_secret = False                   # keyless (het alternatieve pad naast het key-vereisende EPO)
    input_schema = "term: str (zoekterm). optioneel: limit: int (default 5, max 10)"
    output_schema = ("lijst: total: int, patents: list[{title, abstract, publication_date, "
                     "publication_number, assignee, inventors}] | no_data | error")
    description = ("Zoekt wereldwijde patenten via het keyless xhr-endpoint van Google Patents. Het "
                   "alternatieve pad voor de skill-ladder als EPO OPS faalt. Fail-closed.")

    def available_metrics(self, context=None):
        return ["patents"]

    def is_configured(self, context):
        return True                        # keyless → altijd 'geconfigureerd'

    def daily_values(self, context, datum):
        return {}                          # geen meetbron — nooit door de collector geschreven

    # ── HTTP → JSON ─────────────────────────────────────────────────────────
    @staticmethod
    def _default_get(url):
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def _fetch(self, term, limit, *, _get=None):
        get = _get or self._default_get
        inner = urllib.parse.urlencode({"q": term, "num": limit})     # de q-string wordt zelf een param
        url = f"{_ENDPOINT}?{urllib.parse.urlencode({'url': inner, 'exp': ''})}"
        return get(url)

    @staticmethod
    def _parse(data) -> tuple[int, list[dict]]:
        """Google-Patents-xhr-JSON → (total, [patent-dict]). Defensief: onbekende/afwezige velden → leeg."""
        results = (data or {}).get("results") or {}
        try:
            total = int(results.get("total_num_results") or 0)
        except (TypeError, ValueError):
            total = 0
        patents: list[dict] = []
        for cluster in results.get("cluster") or []:
            for item in (cluster or {}).get("result") or []:
                p = (item or {}).get("patent") or {}
                if not p:
                    continue
                rec = {
                    "title": (p.get("title") or "").strip(),
                    "publication_number": (p.get("publication_number") or "").strip(),
                    "publication_date": (p.get("publication_date") or p.get("priority_date") or "").strip(),
                }
                abstract = (p.get("snippet") or p.get("abstract") or "").strip()
                if abstract:
                    rec["abstract"] = abstract[:400]
                assignee = p.get("assignee")
                if assignee:
                    rec["assignee"] = assignee if isinstance(assignee, list) else [assignee]
                inventor = p.get("inventor") or p.get("inventors")
                if inventor:
                    rec["inventors"] = inventor if isinstance(inventor, list) else [inventor]
                patents.append(rec)
        return total, patents

    # ── run ─────────────────────────────────────────────────────────────────
    def run(self, payload: dict, context) -> dict:
        term = (payload.get("term") or "").strip()
        if not term:
            return {"error": "geen term opgegeven", "patents": []}
        limit = max(1, min(int(payload.get("limit", 5)), 10))
        try:
            data = self._fetch(term, limit)
        except Exception as exc:
            log.warning("Google Patents query faalde (%s): %s", term, exc)
            return {"error": f"Google Patents: {exc}", "patents": []}     # netwerk/HTTP/parse → gat + error
        total, patents = self._parse(data)
        if not patents:
            return {"term": term, "total": 0, "patents": [], "no_data": True,
                    "reason": "geen patenten gevonden voor deze term"}
        return {"term": term, "total": total or len(patents), "patents": patents}
