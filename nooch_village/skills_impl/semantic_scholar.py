"""SemanticScholarSkill — capability "semscholar_tldr".

Zoekt wetenschappelijke papers op via de Semantic Scholar Graph API.
Gebruikt het `tldr`-veld als machinaal gegenereerde één-regel-distillatie.

Authenticatie:
  Geen key vereist voor basisgebruik (~100 req / 5 min).
  Optioneel: zet SEMANTIC_SCHOLAR_API_KEY in .env voor hogere limieten.

Rate-limit-gedrag:
  Bij HTTP 429: exponentiële backoff (2 × attempt + 1s jitter), max 4 pogingen.
  Bij een 5xx of een timeout: één herhaling na een korte pauze (scope 54 — de gemeten faalwijze
  was "5 fout: 500/429/timeouts", en een enkele hik hoort geen ⚠️ op de wall te kosten).
  Daarna fail-closed: {"error": "…"}.

Ladder-trede (scope 54). Deze skill is de tweede tree onder `openalex_evidence` (evidence_ledger
.SKILL_LADDERS) en krijgt de OpenAlex-payload ONGEWIJZIGD. OpenAlex splitst een ' OR '-keten in losse
frases; hier ging die keten tot scope 54 als één string de zoekmachine in ("a OR b OR c" als keywords),
en dan gaf de trede stil nul waar OpenAlex al leeg was. Nu wordt de term hetzelfde genormaliseerd:
splitsen op ' OR ' (elke clausule apart, unie op paperId), koppeltekens naar spaties.

Records: `url` (semanticscholar.org/paper/<id>) en `doi` per paper, abstract tot 2000 tekens (zodat
`leesextract` er iets mee kan; de oude cap van 300 lag onder zijn drempel), en een `text` als leeswijzer.

Segmentatie:
  Elke aanroep draagt een `locale`-sleutel door in de output.
  `no_data: True` onderscheidt "niets gevonden" van een netwerk-fout.

Fail-closed: bij élke fout retourneert de skill een dict met "error"; nooit mock-data.
"""
from __future__ import annotations
import logging
import re
import socket
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import json
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_BASE   = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "paperId,externalIds,url,title,abstract,year,citationCount,tldr"
_AUTHOR_SEARCH = "https://api.semanticscholar.org/graph/v1/author/search"
_PAPER_URL = "https://www.semanticscholar.org/paper/"
_ABSTRACT_MAX = 2000          # zie de moduletekst: boven de leesextract-drempel van 600
_MAX_OR_CLAUSES = 5           # zelfde plafond-gedachte als openalex._MAX_OR_CLAUSES, maar de S2-limiet
                              # is krapper (100 req / 5 min), dus lager
_RETRY_PAUZE = 2.0            # seconden vóór de ene herhaling op 5xx/timeout


def _clausules(term: str) -> list[str]:
    """De zoekclausules uit een term: gesplitst op ' OR ', koppeltekens en schuine strepen naar spaties,
    quotes en haakjes weg (S2 zoekt op keywords, niet op boolean-syntax). Geen ' OR ' → één clausule."""
    uit = []
    for deel in re.split(r"\s+OR\s+", (term or "").strip()):
        d = re.sub(r"[-/–]", " ", deel)
        d = d.replace('"', " ").replace("(", " ").replace(")", " ")
        d = " ".join(d.split())
        if d:
            uit.append(d)
    return uit[:_MAX_OR_CLAUSES]


def _als_tekst(term: str, total: int, hits: list, gezocht: list[str]) -> str:
    """De leeswijzer voor de wall: hoeveel papers, op welke term, en het meest geciteerde erbij."""
    kop = f"{total} paper(s) on Semantic Scholar for '{term}'"
    if len(gezocht) > 1:
        kop += f" (searched {len(gezocht)} clauses separately)"
    top = hits[0] if hits else None
    if not top:
        return kop + "."
    detail = f"“{str(top.get('title') or '').strip()[:120]}”"
    if top.get("year"):
        detail += f", {top['year']}"
    detail += f", {int(top.get('citations') or 0)} citations"
    return f"{kop}; top cited: {detail}."


class SemanticScholarSkill(DataSourceSkill):
    name = "semscholar_tldr"
    input_schema = ("term: str (required — an ENGLISH keyword phrase of 2-5 words, e.g. 'bio-based "
                    "adhesives footwear'; join alternatives with ' OR ' — each clause is searched "
                    "separately and the results merged). Optional: limit: int (default 5) · "
                    "locale: str (echoed back)")
    required_payload = ("term",)
    output_schema = ("list: total: int, hits: list[{title, url, doi, year, citations, tldr (one-sentence "
                     "machine summary), abstract (up to 2000 chars)}], text (summary for the wall), "
                     "gezocht (the clauses searched) | no_data + reason | error")
    SOURCE = "semanticscholar"
    CATALOG_LABEL = "Semantic Scholar (auteur-tellers)"
    # Snapshot-bron (cumulatieve auteur-tellers, groeien traag) → maandelijks meten. De tegel toont de
    # genormaliseerde delta i.p.v. de oplopende stand (erft het OpenAlex-snapshot-patroon).
    kind = "snapshot"
    DEFAULT_FREQUENCY = "monthly"
    cost = "rate_limited"
    optional_env = ("SEMANTIC_SCHOLAR_API_KEY",)
    description = (
        "Scientific papers via Semantic Scholar, each with a one-sentence machine summary (tldr): give "
        "an English keyword phrase of 2-5 words. Returns title, link, DOI, year, citations, tldr and "
        "abstract per paper; keyless (an optional key raises the rate limit); backoff on 429, one "
        "retry on a server error or timeout; 'no_data' when nothing matches."
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
        term   = str((payload or {}).get("term") or "").strip()
        locale = (payload or {}).get("locale", "")
        if not term:
            return {"error": "geen term opgegeven", "hits": [], "locale": locale}

        try:
            limit = max(1, int((payload or {}).get("limit", 5)))
        except (TypeError, ValueError):
            limit = 5
        api_key = (getattr(context, "settings", {}) or {}).get("SEMANTIC_SCHOLAR_API_KEY", "")
        headers: dict[str, str] = {
            "User-Agent": "NoochVillage/1.0 (nooch.earth research bot)"}
        if api_key:
            headers["x-api-key"] = api_key

        clausules = _clausules(term) or [term]
        # Per clausule één zoekopdracht; de unie (dedup op paperId, meest geciteerd eerst) is het
        # antwoord — dezelfde vorm als openalex, zodat de ladder-trede op dezelfde term hetzelfde
        # betekent. Faalt élke clausule → error; geeft geen enkele iets → no_data.
        papers: list[dict] = []
        gezien: set[str] = set()
        fouten: list[str] = []
        total = 0
        for i, clausule in enumerate(clausules):
            url = f"{_BASE}?query={urllib.parse.quote(clausule)}&limit={limit}&fields={_FIELDS}"
            data = self._fetch_with_backoff(url, headers)
            if isinstance(data, str):                            # fout-string
                fouten.append(f"'{clausule}': {data}")
                continue
            deel = data.get("data") or []
            try:
                total += int(data.get("total", len(deel)) or 0)
            except (TypeError, ValueError):
                total += len(deel)
            for p in deel:
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("paperId") or "") or json.dumps(p.get("title") or "", ensure_ascii=False)
                if pid in gezien:
                    continue
                gezien.add(pid)
                papers.append(p)
            if i < len(clausules) - 1:
                time.sleep(0.5)                                   # kleine pauze tussen deel-calls

        if not papers and fouten and len(fouten) == len(clausules):
            return {"error": "; ".join(fouten), "hits": [], "term": term, "locale": locale,
                    "gezocht": clausules}
        if not papers:
            return {"term": term, "locale": locale, "total": 0, "gezocht": clausules,
                    "no_data": True, "reason": "geen papers gevonden voor deze term",
                    "hits": []}

        papers.sort(key=lambda p: int(p.get("citationCount") or 0), reverse=True)
        hits = []
        for paper in papers[:limit]:
            tldr_obj = paper.get("tldr") or {}
            tldr     = tldr_obj.get("text", "") if isinstance(tldr_obj, dict) else ""
            abstract = (paper.get("abstract") or "")[:_ABSTRACT_MAX]
            ext = paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else {}
            pid = str(paper.get("paperId") or "")
            hits.append({
                "source":    "semantic_scholar",
                "locale":    locale,
                "title":     paper.get("title") or "",
                "url":       str(paper.get("url") or (f"{_PAPER_URL}{pid}" if pid else "")),
                "doi":       str(ext.get("DOI") or ""),
                "year":      paper.get("year"),
                "citations": paper.get("citationCount", 0),
                "tldr":      tldr,
                "abstract":  abstract,
            })

        time.sleep(1.0)
        uit = {"term": term, "locale": locale, "total": total or len(hits), "hits": hits,
               "gezocht": clausules, "text": _als_tekst(term, total or len(hits), hits, clausules)}
        if fouten:
            uit["_fouten"] = fouten                              # deel-clausules die faalden: metadata
        return uit

    def _fetch_with_backoff(self, url: str, headers: dict,
                            max_retries: int = 4, *, _sleep=None) -> dict | str:
        """Eén GET → JSON, of een FOUT-STRING (de caller maakt er `error` van). 429 → backoff, tot
        `max_retries` pogingen; 5xx of timeout → precies één herhaling na `_RETRY_PAUZE`; elke andere
        fout direct. De sleutel zit alleen in de header, dus de melding draagt hem niet; `masker`
        erover voor de zekerheid (verdediging in de diepte, scope 53)."""
        from nooch_village.sleutelmasker import masker
        slaap = _sleep if _sleep is not None else time.sleep
        herhaald = False
        attempt = 0
        while attempt < max_retries:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=14) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    attempt += 1
                    if attempt < max_retries:
                        slaap(2 ** attempt + random.uniform(0, 1))
                        continue
                    return "rate-limit overschreden na 4 pogingen (HTTP 429)"
                if 500 <= e.code < 600 and not herhaald:
                    herhaald = True
                    slaap(_RETRY_PAUZE)
                    continue
                return masker(f"HTTP {e.code}: {e.reason}")
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
                if not herhaald:
                    herhaald = True
                    slaap(_RETRY_PAUZE)
                    continue
                return masker(f"Semantic Scholar niet bereikbaar: {e}")
            except Exception as e:                                 # noqa: BLE001 — parse-fout e.d.
                return masker(f"Semantic Scholar niet bereikbaar: {e}")
        return "rate-limit overschreden na 4 pogingen"
