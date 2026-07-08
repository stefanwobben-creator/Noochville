"""EPO Open Patent Services (OPS) — wereldwijde patent-zoekskill voor harry_hemp (Scientist).

OAuth-token-flow (consumer key + secret → access token, zoals de GSC-token), published-data search +
biblio, en een lijst-archetype-output ({patents:[...]}) zodat het uitvoer-primitief het autonoom afvinkt
en als leesbare note wegschrijft (net als openalex_evidence/semscholar_tldr).

Fail-closed: ontbrekende/ongeldige credentials → ERROR, geen kale call. Lege set → geldige "0 patenten"
(echte observatie). API-fout/timeout/403 fair-use → gat + ERROR, geen crash. Credentials komen UITSLUITEND
uit de env (EPO_CONSUMER_KEY + EPO_CONSUMER_SECRET / EPO_CONSUMER_SECRET_KEY) — nooit hardcoded.
"""
from __future__ import annotations
import base64
import json
import logging
import os
import time
import urllib.parse
import urllib.request

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"
_BIBLIO_TMPL = "https://ops.epo.org/3.2/rest-services/published-data/publication/docdb/{ref}/biblio"


def _txt(node) -> str:
    """OPS-waarde: {'$': '...'} → '...'; str → str; anders ''."""
    if isinstance(node, dict):
        return str(node.get("$", "")).strip()
    return str(node).strip() if node not in (None, "") else ""


def _aslist(x):
    """OPS levert 1 element als dict, meerdere als list — normaliseer naar list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


class EpoPatentsSkill(DataSourceSkill):
    name = "epo_patents"
    SOURCE = "epo_patents"                 # los van de meetcatalogus: research-skill, geen dagobservatie
    kind = "snapshot"
    cost = "rate_limited"                  # OAuth + fair-use (~4GB/week), bescheiden page-size
    needs_secret = True
    input_schema = "term: str (zoekterm, gezocht in de patenttitel). optioneel: limit: int (default 5, max 10)"
    output_schema = ("lijst: total: int, patents: list[{title, abstract, publication_date, "
                     "publication_number, applicants, inventors}] | no_data | error")
    description = ("Zoekt wereldwijde patenten via de EPO Open Patent Services (OPS): OAuth-token uit "
                   "EPO_CONSUMER_KEY + EPO_CONSUMER_SECRET, published-data search + biblio. Fail-closed.")

    def __init__(self):
        self._token: str | None = None
        self._token_exp: float = 0.0

    # ── config ──────────────────────────────────────────────────────────────
    def available_metrics(self, context=None):
        return ["patents"]

    def _creds(self, context):
        s = getattr(context, "settings", {}) or {}
        key = s.get("EPO_CONSUMER_KEY") or os.getenv("EPO_CONSUMER_KEY")
        # accepteer beide spellingen: de scope-naam én de werkelijke .env-naam (EPO's 'Consumer Secret Key')
        secret = (s.get("EPO_CONSUMER_SECRET") or os.getenv("EPO_CONSUMER_SECRET")
                  or s.get("EPO_CONSUMER_SECRET_KEY") or os.getenv("EPO_CONSUMER_SECRET_KEY"))
        return key, secret

    def is_configured(self, context):
        k, s = self._creds(context)
        return bool(k and s)

    def daily_values(self, context, datum):
        return {}                          # geen meetbron — nooit door de collector geschreven

    # ── OAuth-token (cache + verversen bij verloop) ─────────────────────────
    def _get_token(self, context, *, _post=None):
        now = time.time()
        if self._token and now < self._token_exp - 60:        # nog geldig (marge 60s)
            return self._token
        key, secret = self._creds(context)
        if not (key and secret):
            raise RuntimeError("EPO_CONSUMER_KEY/EPO_CONSUMER_SECRET ontbreekt — epo_patents faalt closed")
        basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
        if _post is None:
            def _post(url, data, headers):
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as r:
                    return json.loads(r.read().decode("utf-8"))
        resp = _post(_AUTH_URL, b"grant_type=client_credentials",
                     {"Authorization": f"Basic {basic}",
                      "Content-Type": "application/x-www-form-urlencoded"})
        tok = (resp or {}).get("access_token")
        if not tok:
            raise RuntimeError("EPO OPS: geen access_token in auth-respons")
        self._token = tok
        self._token_exp = now + float((resp or {}).get("expires_in", 1200))
        return tok

    # ── HTTP-helper (Bearer + JSON) ─────────────────────────────────────────
    @staticmethod
    def _default_get(url, token):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                   "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    # ── search → publicatie-referenties (docdb) ─────────────────────────────
    def _search(self, token, cql, limit, *, _get=None):
        get = _get or (lambda u: self._default_get(u, token))
        url = f"{_SEARCH_URL}?q={urllib.parse.quote(cql)}&Range=1-{limit}"
        data = get(url)
        root = (data or {}).get("ops:world-patent-data", {}).get("ops:biblio-search", {})
        total = int(str(root.get("@total-result-count", "0")) or 0)
        refs = []
        for pr in _aslist(root.get("ops:search-result", {}).get("ops:publication-reference")):
            for did in _aslist(pr.get("document-id")):
                if did.get("@document-id-type") != "docdb":
                    continue
                c, n, k = _txt(did.get("country")), _txt(did.get("doc-number")), _txt(did.get("kind"))
                if c and n:
                    refs.append(f"{c}.{n}.{k}" if k else f"{c}.{n}")
        return total, refs

    # ── biblio per referentie → {title, abstract, datum, nummer, applicants, inventors} ─────
    def _biblio(self, token, ref, *, _get=None):
        get = _get or (lambda u: self._default_get(u, token))
        data = get(_BIBLIO_TMPL.format(ref=urllib.parse.quote(ref)))
        doc = ((data or {}).get("ops:world-patent-data", {})
               .get("exchange-documents", {}).get("exchange-document", {}))
        if isinstance(doc, list):
            doc = doc[0] if doc else {}
        bib = doc.get("bibliographic-data", {}) if isinstance(doc, dict) else {}
        # titel (voorkeur en)
        titles = _aslist(bib.get("invention-title"))
        title = next((_txt(t) for t in titles if isinstance(t, dict) and t.get("@lang") == "en"), "")
        title = title or (_txt(titles[0]) if titles else "")
        # abstract (voorkeur en)
        absn = _aslist(doc.get("abstract"))
        abstract = ""
        for a in absn:
            if isinstance(a, dict) and (a.get("@lang") == "en" or not abstract):
                abstract = " ".join(_txt(p) for p in _aslist(a.get("p"))).strip() or abstract
                if a.get("@lang") == "en":
                    break
        # publicatie-nummer + datum (docdb publication-reference)
        pub_no, pub_date = ref, ""
        for did in _aslist(bib.get("publication-reference", {}).get("document-id")):
            if did.get("@document-id-type") == "docdb":
                c, n, k = _txt(did.get("country")), _txt(did.get("doc-number")), _txt(did.get("kind"))
                pub_no = f"{c}{n}{k}" or pub_no
                pub_date = _txt(did.get("date")) or pub_date
        # partijen
        parties = bib.get("parties", {})
        applicants = [_txt(a.get("applicant-name", {}).get("name")) for a in
                      _aslist(parties.get("applicants", {}).get("applicant"))]
        inventors = [_txt(i.get("inventor-name", {}).get("name")) for i in
                     _aslist(parties.get("inventors", {}).get("inventor"))]
        rec = {"title": title, "publication_number": pub_no, "publication_date": pub_date}
        if abstract:
            rec["abstract"] = abstract[:400]
        applicants = sorted({a for a in applicants if a})
        inventors = sorted({i for i in inventors if i})
        if applicants:
            rec["applicants"] = applicants
        if inventors:
            rec["inventors"] = inventors
        return rec

    # ── run ─────────────────────────────────────────────────────────────────
    def run(self, payload: dict, context) -> dict:
        term = (payload.get("term") or "").strip()
        if not term:
            return {"error": "geen term opgegeven", "patents": []}
        limit = max(1, min(int(payload.get("limit", 5)), 10))
        try:
            token = self._get_token(context)
        except Exception as exc:
            return {"error": str(exc), "patents": []}          # fail-closed: geen creds/token
        try:
            total, refs = self._search(token, f'ti="{term}"', limit)
        except Exception as exc:
            log.warning("EPO OPS search faalde (%s): %s", term, exc)
            return {"error": f"EPO OPS search: {exc}", "patents": []}
        if not refs:
            return {"term": term, "total": 0, "patents": [], "no_data": True,
                    "reason": "geen patenten gevonden voor deze term"}
        patents = []
        for ref in refs[:limit]:
            try:
                patents.append(self._biblio(token, ref))
            except Exception as exc:
                log.warning("EPO OPS biblio '%s' faalde: %s", ref, exc)
            time.sleep(0.3)                                     # beleefd tegen de fair-use-limiet
        if not patents:
            return {"error": "EPO OPS: refs gevonden maar biblio-ophalen mislukte", "patents": []}
        return {"term": term, "total": total or len(patents), "patents": patents}
