"""EPO Open Patent Services (OPS) — wereldwijde patent-zoekskill voor harry_hemp (Scientist).

OAuth-token-flow (consumer key + secret → access token, zoals de GSC-token) + de OPS **XML**-interface
(published-data search met de biblio-constituent). Output volgens het lijst-archetype ({patents:[...]})
zodat het uitvoer-primitief het autonoom afvinkt en als leesbare note wegschrijft (net als
openalex_evidence/semscholar_tldr).

XML-parse gebaseerd op de officiële OPS-structuur (ops:world-patent-data → ops:biblio-search →
ops:search-result → exchange-documents/exchange-document met bibliographic-data + abstract), met
namespace-agnostische matching ({*}) zodat een schema-prefix-wijziging het parsen niet breekt.

Fail-closed: ontbrekende/ongeldige credentials → ERROR, geen kale call. Lege set → geldige "0 patenten".
API-fout/timeout/403 fair-use → gat + ERROR, geen crash. Credentials UITSLUITEND uit de env
(EPO_CONSUMER_KEY + EPO_CONSUMER_SECRET / EPO_CONSUMER_SECRET_KEY) — nooit hardcoded.
"""
from __future__ import annotations
import base64
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
# biblio-constituent op de search: levert de bibliografische velden (titel/datum/partijen/abstract) inline,
# in één call — i.p.v. search (alleen doc-nummers) + N losse biblio-calls. Fair-use-vriendelijk.
_SEARCH_BIBLIO_URL = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"


def _dedup(names) -> list[str]:
    """Unieke, niet-lege, gestripte namen, gesorteerd (OPS levert partijen vaak in twee data-formats)."""
    return sorted({(n or "").strip() for n in names if (n or "").strip()})


def _party_names(ed, tag: str) -> list[str]:
    """Namen van applicants/inventors uit een exchange-document. OPS levert elke partij in meerdere
    data-formats (epodoc/docdb/original); we prefereren 'epodoc' (leesbare naam, bv. 'ASICS CORP [JP]')
    en vallen anders terug op alle formats — zodat partijen niet gedropt worden."""
    parts = ed.findall(f".//{{*}}{tag}")
    epodoc = [p.findtext(".//{*}name") for p in parts if p.get("data-format") == "epodoc"]
    return _dedup(epodoc or [p.findtext(".//{*}name") for p in parts])


class EpoPatentsSkill(DataSourceSkill):
    name = "epo_patents"
    SOURCE = "epo_patents"                 # los van de meetcatalogus: research-skill, geen dagobservatie
    kind = "snapshot"
    cost = "rate_limited"                  # OAuth + fair-use (~4GB/week), bescheiden Range
    needs_secret = True
    input_schema = "term: str (zoekterm). optioneel: limit: int (default 5, max 10 — Range 1-limit)"
    output_schema = ("lijst: total: int, patents: list[{title, abstract, publication_date, "
                     "publication_number, applicants, inventors}] | no_data | error")
    description = ("Zoekt wereldwijde patenten via de EPO Open Patent Services (OPS, XML-interface): "
                   "OAuth-token uit EPO_CONSUMER_KEY + EPO_CONSUMER_SECRET, published-data search/biblio. "
                   "Fail-closed.")

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

    # ── OAuth-token (cache + verversen bij verloop) — het token-endpoint levert JSON ─────────
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

    # ── HTTP-GET → rauwe XML-bytes (Bearer) ─────────────────────────────────
    @staticmethod
    def _default_get(url, token):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                   "Accept": "application/xml"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read()

    @staticmethod
    def _normalize_term(term: str) -> str:
        """Reduceer een (LLM-)zoekstring tot een kernfrase die EPO's CQL title-search (ti="…") aankan.
        Complexe boolean-strings ('X OR Y', '"A" AND ("B" OR "C")') geven anders een HTTP 400/404 (de
        operators/haakjes/quotes breken de CQL). We nemen de eerste OR-clausule (de dominante frase) en
        strippen quotes/haakjes/AND → een schone woordfrase. Leeg na normalisatie → val terug op de ruwe
        term zonder quotes."""
        import re as _re
        t = _re.split(r"\s+OR\s+", term or "", flags=_re.IGNORECASE)[0]
        t = t.replace('"', " ").replace("(", " ").replace(")", " ")
        t = _re.sub(r"\s+AND\s+", " ", t, flags=_re.IGNORECASE)
        t = _re.sub(r"\s+", " ", t).strip()
        return t or (term or "").replace('"', " ").strip()

    # ── search/biblio → (total, [patent-dicts]) via XML-parse ───────────────
    def _search(self, token, term, limit, *, _get=None):
        get = _get or (lambda u: self._default_get(u, token))
        # De term wordt genormaliseerd (boolean/quotes strippen). CQL-vorm hangt af van de lengte: EPO's
        # exacte titel-frase ti="a b" werkt tot ~2 woorden, maar 404't bij ≥3 (empirisch). ti any "…" (elk
        # woord in de titel) werkt voor élke lengte zonder 404 — breder, maar levert kandidaten i.p.v. een
        # doodloper. Zo blijft een korte query precies en rondt een lange query af i.p.v. eeuwig te falen.
        words = self._normalize_term(term).split()
        inner = " ".join(words) or (term or "")
        cql = f'ti="{inner}"' if len(words) <= 2 else f'ti any "{inner}"'
        url = f"{_SEARCH_BIBLIO_URL}?q={urllib.parse.quote(cql)}&Range=1-{limit}"
        return self._parse_patents(get(url))

    @staticmethod
    def _parse_patents(xml_bytes):
        """Parse de OPS-search/biblio-XML → (total_result_count, [patent-dict]). Namespace-agnostisch ({*})."""
        root = ET.fromstring(xml_bytes)
        bs = root.find(".//{*}biblio-search")
        try:
            total = int((bs.get("total-result-count") if bs is not None else "0") or 0)
        except (TypeError, ValueError):
            total = 0
        patents = []
        for ed in root.findall(".//{*}exchange-document"):
            # invention-title (voorkeur en)
            title = ""
            for t in ed.findall(".//{*}invention-title"):
                txt = (t.text or "").strip()
                if t.get("lang") == "en":
                    title = txt
                    break
                title = title or txt
            # abstract (voorkeur en)
            abstract = ""
            for a in ed.findall(".//{*}abstract"):
                txt = " ".join((p.text or "").strip() for p in a.findall("{*}p")).strip()
                if a.get("lang") == "en":
                    abstract = txt
                    break
                abstract = abstract or txt
            # publicatienummer + datum uit de docdb-publication-reference
            pub_no, pub_date = "", ""
            pr = ed.find(".//{*}publication-reference")
            for did in (pr.findall("{*}document-id") if pr is not None else []):
                if did.get("document-id-type") == "docdb":
                    c = (did.findtext("{*}country") or "").strip()
                    n = (did.findtext("{*}doc-number") or "").strip()
                    k = (did.findtext("{*}kind") or "").strip()
                    pub_no = f"{c}{n}{k}"
                    pub_date = (did.findtext("{*}date") or "").strip()
                    break
            if not pub_no:                 # fallback op de exchange-document-attributen
                pub_no = f"{ed.get('country', '')}{ed.get('doc-number', '')}{ed.get('kind', '')}"
            applicants = _party_names(ed, "applicant")
            inventors = _party_names(ed, "inventor")
            rec = {"title": title, "publication_number": pub_no, "publication_date": pub_date}
            if abstract:
                rec["abstract"] = abstract[:400]
            if applicants:
                rec["applicants"] = applicants
            if inventors:
                rec["inventors"] = inventors
            patents.append(rec)
        return total, patents

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
            total, patents = self._search(token, term, limit)
        except Exception as exc:
            log.warning("EPO OPS search faalde (%s): %s", term, exc)
            return {"error": f"EPO OPS search: {exc}", "patents": []}   # 403/timeout/parse → gat + error
        if not patents:
            return {"term": term, "total": 0, "patents": [], "no_data": True,
                    "reason": "geen patenten gevonden voor deze term"}
        return {"term": term, "total": total or len(patents), "patents": patents}
