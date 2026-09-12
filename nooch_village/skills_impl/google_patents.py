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
_PATENT_URL = "https://patents.google.com/patent/"
# Boven de leesextract-drempel van 600 (scope 54); de oude cap van 400 maakte elk extract onmogelijk.
_ABSTRACT_MAX = 2000


def _als_tekst(term: str, total: int, patents: list) -> str:
    """De leeswijzer voor de wall: hoeveel patenten, op welke term, en het eerste erbij."""
    kop = f"{total} patent(s) on Google Patents for '{term}'"
    eerste = patents[0] if patents else None
    if not eerste:
        return kop + "."
    detail = f"“{str(eerste.get('title') or '').strip()[:120]}”"
    if eerste.get("publication_number"):
        detail += f" ({eerste['publication_number']}"
        if eerste.get("publication_date"):
            detail += f", {eerste['publication_date']}"
        detail += ")"
    return f"{kop}; first: {detail}."


class GooglePatentsSkill(DataSourceSkill):
    name = "google_patents"
    SOURCE = "google_patents"              # research-skill, geen dagobservatie (net als epo_patents)
    kind = "snapshot"
    cost = "rate_limited"                  # ongedocumenteerd endpoint — bescheiden gebruik
    needs_secret = False                   # keyless (het alternatieve pad naast het key-vereisende EPO)
    input_schema = ("term: str (required — the words a patent title or abstract would use, English; "
                    "' OR ' is passed through as Google Patents understands it). Optional: limit: int "
                    "(default 5, max 10)")
    output_schema = ("list: total: int, patents: list[{title, url (patents.google.com), "
                     "publication_number, publication_date, abstract (up to 2000 chars), assignee, "
                     "inventors}], text (summary for the wall) | no_data + reason | error")
    description = ("Worldwide patents via the keyless query endpoint of Google Patents: the second rung "
                   "under epo_patents when EPO OPS fails. Returns title, link, number, date, abstract "
                   "and assignee per patent; 'no_data' when nothing matches. Fail-closed.")

    _MIN_INTERVAL = 1.2                    # min. seconden tussen calls (burst-throttle); test zet 0
    _last_call_ts = 0.0                    # class-state: tijdstip laatste call, over de puls-burst heen

    @classmethod
    def _throttle(cls, *, _now=None, _sleep=None):
        """Burst-throttle: houd minimaal _MIN_INTERVAL tussen opeenvolgende calls, zodat een puls die veel
        patent-items achter elkaar draait het keyless endpoint niet plat vuurt (retry redt losse calls,
        niet een burst). _now/_sleep injecteerbaar voor de test."""
        import time as _t
        now = (_now or _t.time)()
        wait = cls._MIN_INTERVAL - (now - cls._last_call_ts)
        if wait > 0:
            (_sleep or _t.sleep)(wait)
        cls._last_call_ts = (_now or _t.time)()

    def available_metrics(self, context=None):
        return ["patents"]

    def is_configured(self, context):
        return True                        # keyless → altijd 'geconfigureerd'

    def daily_values(self, context, datum):
        return {}                          # geen meetbron — nooit door de collector geschreven

    # ── HTTP → JSON ─────────────────────────────────────────────────────────
    @staticmethod
    def _default_get(url, *, _open=None, _sleep=None, _now=None):
        """HTTP-GET → JSON met burst-throttle vooraf + beleefde jittered backoff-retry tegen de rate-limit/
        blokkade van het keyless endpoint (3 pogingen). Pas na 3 mislukte pogingen faalt 'ie — zodat een
        transiënte 429/403 een 'fout' wordt maar geen dagelijkse doodloper. _open/_sleep/_now injecteerbaar
        (zodat een geïnjecteerde _fetch/_get in de test nooit echt slaapt of throttlet)."""
        import time as _t
        opener = _open or (lambda rq: urllib.request.urlopen(rq, timeout=20))
        sleep = _sleep or _t.sleep
        GooglePatentsSkill._throttle(_now=_now, _sleep=sleep)   # burst-throttle over opeenvolgende calls
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
                with opener(req) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as exc:
                last = exc
                if attempt < 2:
                    import random as _r
                    sleep(1.0 + attempt + _r.uniform(0, 0.5))   # jittered backoff (~1-1.5s, ~2-2.5s)
        raise last

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
                pub_no = (p.get("publication_number") or "").strip()
                rec = {
                    "title": (p.get("title") or "").strip(),
                    "publication_number": pub_no,
                    "publication_date": (p.get("publication_date") or p.get("priority_date") or "").strip(),
                }
                if pub_no:
                    # Deterministisch adres: de patentpagina op publicatienummer. Zonder link kon een
                    # mens vanuit note of verslag niet doorklikken — ook niet als deze skill als
                    # fallback voor EPO draaide.
                    rec["url"] = f"{_PATENT_URL}{urllib.parse.quote(pub_no)}"
                abstract = (p.get("snippet") or p.get("abstract") or "").strip()
                if abstract:
                    rec["abstract"] = abstract[:_ABSTRACT_MAX]
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
        term = str((payload or {}).get("term") or "").strip()
        if not term:
            return {"error": "geen term opgegeven", "patents": []}
        try:
            limit = max(1, min(int((payload or {}).get("limit", 5)), 10))
        except (TypeError, ValueError):
            limit = 5
        try:
            data = self._fetch(term, limit)
        except Exception as exc:
            from nooch_village.sleutelmasker import masker
            log.warning("Google Patents query faalde (%s): %s", term, masker(exc))
            return {"error": f"Google Patents: {masker(exc)}", "patents": []}   # netwerk/HTTP/parse → gat + error
        total, patents = self._parse(data)
        if not patents:
            return {"term": term, "total": 0, "patents": [], "no_data": True,
                    "reason": "geen patenten gevonden voor deze term"}
        return {"term": term, "total": total or len(patents), "patents": patents,
                "text": _als_tekst(term, total or len(patents), patents)}
