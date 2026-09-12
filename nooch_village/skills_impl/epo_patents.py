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

"NIETS GEVONDEN" IS GEEN FOUT (scope 54). OPS meldt een lege trefferset niet als 200 met nul
documenten maar als HTTP 404 met de fault "No results found". Tot scope 54 werd élke exceptie uit de
search een `error`: de Kroniek boekte "fout", de ladder liep door naar google_patents met het label
"fallback voor epo_patents", en `consecutive_failures` telde op — voor een gewone "niets gevonden". De
juli-meting telde 12× "Not Found" op precies die manier. Nu leest een 404/"No results" als `no_data`.

OR-KETENS (scope 54). Een ' OR '-keten wordt per clausule apart gezocht (max 3) en de uitkomsten
samengevoegd (dedup op publicatienummer) — dezelfde vorm als openalex/semscholar, zodat een term op elke
trede hetzelfde betekent. Tot dan werd alleen de eerste clausule gezocht zonder dat de uitkomst dat zei.
Wat er werkelijk naar OPS ging staat in `gezocht`.

Records: `url` naar Espacenet per patent (klikbaar in note en verslag), abstract tot 2000 tekens (boven de
leesextract-drempel van 600), en een `text` als leeswijzer.
"""
from __future__ import annotations
import base64
import json
import logging
import os
import re
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
_ESPACENET_URL = "https://worldwide.espacenet.com/patent/search?q=pn%3D"
_ABSTRACT_MAX = 2000
_MAX_OR_CLAUSES = 3            # fair use: elke clausule is een OPS-call
# Hoe OPS "niets gevonden" zegt: een 404 (urllib.error.HTTPError.code) of de fault-tekst.
_LEEG_RE = re.compile(r"no results found|entitynotfound|http error 404|\bhttp 404\b", re.I)


def _is_leeg(exc: BaseException) -> bool:
    """Is deze exceptie OPS' manier om 'geen treffers' te zeggen? 404 of de fault-tekst."""
    if getattr(exc, "code", None) == 404:
        return True
    return bool(_LEEG_RE.search(str(exc) or ""))


def _als_tekst(term: str, total: int, patents: list, gezocht: str) -> str:
    """De leeswijzer voor de wall: hoeveel patenten, welke CQL er werkelijk naar OPS ging, het eerste."""
    kop = f"{total} patent(s) via EPO OPS for '{term}' (searched: {gezocht})"
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
    input_schema = ("term: str (required — searched in patent TITLES: use the words a patent title "
                    "would use, e.g. 'shoe sole attachment' or 'stitched footwear sole', never a "
                    "research question; 1-2 words = exact title phrase, more = any of the words in the "
                    "title. Join alternatives with ' OR ': each clause is searched separately (max 3) "
                    "and the results merged). Optional: limit: int (default 5, max 10 — Range 1-limit)")
    output_schema = ("list: total: int, patents: list[{title, url (Espacenet), publication_number, "
                     "publication_date, abstract (up to 2000 chars), applicants, inventors}], gezocht "
                     "(the CQL that went to OPS), text (summary for the wall) | no_data + reason | error")
    description = ("Worldwide patents via the EPO Open Patent Services (title search): give the words a "
                   "patent title would use, 1-2 words as an exact phrase, more as any-of. Returns "
                   "title, Espacenet link, number, date, abstract and parties per patent; 'no_data' "
                   "when the register has nothing. OAuth from EPO_CONSUMER_KEY + EPO_CONSUMER_SECRET.")

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
        term zonder quotes.

        KOPPELTEKENS EN SCHUINE STREPEN WORDEN SPATIES. "glue-free bio-based joining" (12 september)
        ging als één woordreeks met koppeltekens de CQL in; in een titel-index staat "glue free" of
        "adhesive-free" en een koppelteken is daar geen woordgrens. Uit elkaar halen kost niets en de
        losse woorden matchen wél."""
        import re as _re
        t = _re.split(r"\s+OR\s+", term or "", flags=_re.IGNORECASE)[0]
        t = t.replace('"', " ").replace("(", " ").replace(")", " ")
        t = _re.sub(r"\s+AND\s+", " ", t, flags=_re.IGNORECASE)
        t = _re.sub(r"[-/–]", " ", t)
        t = _re.sub(r"\s+", " ", t).strip()
        return t or (term or "").replace('"', " ").strip()

    @staticmethod
    def _clausules(term: str) -> list[str]:
        """De OR-clausules van een term, elk genormaliseerd (`_normalize_term`), lege weg, max
        `_MAX_OR_CLAUSES`. Geen ' OR ' → één clausule (het oude gedrag)."""
        import re as _re
        delen = _re.split(r"\s+OR\s+", term or "", flags=_re.IGNORECASE)
        uit = []
        for d in delen:
            n = EpoPatentsSkill._normalize_term(d)
            if n and n not in uit:
                uit.append(n)
        return uit[:_MAX_OR_CLAUSES]

    @staticmethod
    def _cql(clausule: str, term: str = "") -> str:
        """De CQL voor één (genormaliseerde) clausule. De vorm hangt af van de lengte: EPO's exacte
        titel-frase ti="a b" werkt tot ~2 woorden, maar 404't bij ≥3 (empirisch). ti any "…" (elk woord
        in de titel) werkt voor élke lengte zonder 404 — breder, maar levert kandidaten i.p.v. een
        doodloper. Zo blijft een korte query precies en rondt een lange query af i.p.v. eeuwig te falen.
        Eén plek voor de CQL, zodat `gezocht` in het resultaat precies is wat er naar OPS ging."""
        words = (clausule or "").split()
        inner = " ".join(words) or (term or "")
        return f'ti="{inner}"' if len(words) <= 2 else f'ti any "{inner}"'

    # ── search/biblio → (total, [patent-dicts]) via XML-parse ───────────────
    def _search(self, token, term, limit, *, _get=None):
        """Eén OPS-call voor één clausule (`term` is hier al genormaliseerd door `_clausules`, of een
        ruwe term — `_normalize_term` is idempotent)."""
        get = _get or (lambda u: self._default_get(u, token))
        cql = self._cql(self._normalize_term(term), term)
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
            if pub_no:
                # Deterministisch adres: Espacenet op publicatienummer. Zonder link toonde het
                # verslag "• titel (EP1234A1) — abstract" en kon een mens niet doorklikken.
                rec["url"] = f"{_ESPACENET_URL}{urllib.parse.quote(pub_no)}"
            if abstract:
                rec["abstract"] = abstract[:_ABSTRACT_MAX]
            if applicants:
                rec["applicants"] = applicants
            if inventors:
                rec["inventors"] = inventors
            patents.append(rec)
        return total, patents

    # ── run ─────────────────────────────────────────────────────────────────
    def run(self, payload: dict, context) -> dict:
        from nooch_village.sleutelmasker import masker
        term = str((payload or {}).get("term") or "").strip()
        if not term:
            return {"error": "geen term opgegeven", "patents": []}
        try:
            limit = max(1, min(int((payload or {}).get("limit", 5)), 10))
        except (TypeError, ValueError):
            limit = 5
        try:
            token = self._get_token(context)
        except Exception as exc:
            return {"error": masker(exc), "patents": []}       # fail-closed: geen creds/token
        clausules = self._clausules(term) or [term]
        gezocht = " | ".join(self._cql(c, term) for c in clausules)
        patents: list[dict] = []
        gezien: set[str] = set()
        fouten: list[str] = []
        total = 0
        for i, clausule in enumerate(clausules):
            try:
                deel_total, deel = self._search(token, clausule, limit)
            except Exception as exc:
                if _is_leeg(exc):
                    # OPS zegt "geen treffers" als 404/"No results found": een antwoord, geen storing.
                    log.info("EPO OPS: geen treffers voor %r (%s)", clausule, exc)
                    continue
                log.warning("EPO OPS search faalde (%s): %s", clausule, masker(exc))
                fouten.append(f"'{clausule}': {masker(exc)}")   # 403/timeout/parse → gat + error
                continue
            total += int(deel_total or 0)
            for p in deel:
                sleutel = p.get("publication_number") or p.get("title") or repr(p)
                if sleutel in gezien:
                    continue
                gezien.add(sleutel)
                patents.append(p)
            if i < len(clausules) - 1:
                time.sleep(0.5)                                  # fair use tussen deel-calls
        if not patents:
            if fouten:
                # Geen enkele clausule leverde iets én er ging er minstens één stuk: dan is "niets
                # gevonden" niet te claimen — het item blijft open (fail-closed).
                return {"error": "EPO OPS search: " + "; ".join(fouten), "patents": [],
                        "term": term, "gezocht": gezocht}
            return {"term": term, "total": 0, "patents": [], "no_data": True, "gezocht": gezocht,
                    "reason": f"geen patenten gevonden voor deze term (searched: {gezocht})"}
        patents = patents[:limit]
        uit = {"term": term, "total": total or len(patents), "patents": patents, "gezocht": gezocht,
               "text": _als_tekst(term, total or len(patents), patents, gezocht)}
        if fouten:
            uit["_fouten"] = fouten                              # deel-clausules die faalden: metadata
        return uit
