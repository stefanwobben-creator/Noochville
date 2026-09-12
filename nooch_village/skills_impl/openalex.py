"""OpenAlexSkill — capability "openalex_evidence".

Zoekt academische werken op via de OpenAlex API.
Authenticatie via OPENALEX_API_KEY (vereist — `run` faalt bewust closed zonder key, en sinds scope 54
zegt `is_configured` hetzelfde: de skill staat zonder sleutel niet in de planner-catalogus, i.p.v.
"scherp" te heten en dan bij elke run te falen).
Polite pool: mailto-adres in de User-Agent voor hogere rate-limit.
Mailto komt uit context.settings["openalex_mailto"] (settings.ini of .env).

Segmentatie:
  Elke aanroep draagt een `locale`-sleutel door in de output.
  Resultaten gesorteerd op citaties (meest geciteerd eerst).
  `no_data: True` onderscheidt "API werkt, maar niets gevonden" van een echte fout.

Records (scope 54, skill-review 12-09-2026): elk werk draagt `url` (het OpenAlex work-id, een
klikbaar adres) en `doi`, en het abstract tot 2000 tekens — genoeg voor `leesextract` om er twee, drie
zinnen uit te halen die op het checklist-item slaan (de oude cap van 400 lag onder zijn drempel van
600, dus geen enkel OpenAlex-record werd ooit verrijkt). Een `text` vat de uitkomst samen voor de wall.

Rate-limit-gedrag:
  Bij HTTP 429: exponentiële backoff (2**attempt + jitter), max 4 pogingen.
  Daarna: raise (use_skill vangt dit op als {"error": ...}).

Fail-closed: ontbrekende key of definitieve fout → raise, nooit mock-data.
"""
from __future__ import annotations
import datetime
import logging
import os
import re
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import json
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_BASE   = "https://api.openalex.org/works"
_SELECT = ("id,doi,title,publication_year,cited_by_count,"
           "abstract_inverted_index,primary_topic,authorships")

# HET ABSTRACT WAS OP 400 TEKENS GEKAPT, en `leesextract` leest pas vanaf 600 (`LANG_TEKST`): geen
# enkel OpenAlex-record kreeg dus ooit een extract, en het verslag toonde de eerste 300 tekens van een
# afgebroken eerste alinea. 2000 is ruim voor een abstract (de meeste zijn 150-350 woorden) en klein
# genoeg om de note en de store niet te vullen.
_ABSTRACT_MAX = 2000

# OpenAlex' vrije `search=` kent GEEN boolean OR-operator (patent-bronnen als EPO/Google Patents wél).
# Een boolean-keten die als één exacte frase wordt gezocht (bv. `"a OR b OR c"`) matcht dus NOOIT — de
# 'OR' is een gewoon woord in de frase. Diagnose (Kroniek): OpenAlex 0× bevestigd op zulke ketens, terwijl
# de losse deelconcepten wél treffen. Daarom splitsen we op ' OR ' en zoeken elke deel-frase apart.
_MAX_OR_CLAUSES = 10          # dek-plafond: verhindert dat een enorme keten tientallen calls afvuurt

# TWEE ZOEKWIJZEN, EN DE LENGTE VAN DE TERM KIEST. Sinds 8 juli gaat een term als EXACTE frase
# (`"barefoot shoes"`: 204 on-topic werken i.p.v. 14.906 losse-woord-hits, gesorteerd op citaties).
# Dat was de goede fix voor een korte term — en de verkeerde voor een lange. Op 12 september zocht
# het lijmvrij-onderzoek op een onderzoeksvraag van vijf, zes woorden ("glue-free bio-based joining
# footwear"): die frase staat in geen enkel abstract letterlijk, dus nul, terwijl de losse begrippen
# (adhesives · footwear · bio-based) samen honderden relevante werken hebben.
#
# Daarom: tot en met drie woorden blijft het een frase met citatie-sortering (precisie); vanaf vier
# woorden gaat de term ongequote mee en sorteert OpenAlex op relevantie (zijn default bij `search`),
# want bij losse woorden is "meest geciteerd" precies de sortering die de off-topic klassiekers
# bovenaan zet. De uitkomst zegt welke van de twee het was (`zoekwijze`), zodat een lezer een
# relevantielijst niet leest als een frasematch.
_FRASE_MAX_WOORDEN = 3


def _zoekwijze(clause: str) -> str:
    """'frase' (≤ 3 woorden: exact, citaties) of 'relevantie' (langer: losse woorden, relevantie)."""
    return "frase" if len((clause or "").split()) <= _FRASE_MAX_WOORDEN else "relevantie"


def _split_or(term: str) -> list[str]:
    """Splits een boolean-keten op ' OR ' (het patent-conventie-woord, hoofdletters) in losse deel-frases.
    Geen ' OR ' → één-element-lijst (ongewijzigd gedrag). Lege delen vallen weg."""
    parts = re.split(r"\s+OR\s+", (term or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _parse_year_groups(data: dict) -> dict[int, int]:
    """Zet een OpenAlex group_by=publication_year-respons om naar {jaar: aantal}.
    Niet-numerieke sleutels ('unknown'/None) worden overgeslagen."""
    out: dict[int, int] = {}
    for g in (data.get("group_by") or []):
        try:
            year = int(g.get("key"))
        except (TypeError, ValueError):
            continue
        out[year] = int(g.get("count", 0))
    return out


def relative_attention(term_counts: dict[int, int],
                       total_counts: dict[int, int]) -> dict[int, float]:
    """Relatieve academische aandacht per jaar: aandeel van de term in álle werken dat jaar.
    Analoog aan ngram's relatieve frequentie, dus vergelijkbaar. Jaren zonder totaal worden
    overgeslagen (geen deling door nul). Gesorteerd op jaar."""
    out: dict[int, float] = {}
    for year, c in term_counts.items():
        tot = total_counts.get(year, 0)
        if tot > 0:
            out[year] = c / tot
    return dict(sorted(out.items()))


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """Reconstrueer abstracttekst vanuit OpenAlex inverted index."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[p] for p in sorted(words.keys()))[:_ABSTRACT_MAX]


def _als_tekst(term: str, total: int, hits: list, zoekwijze: str) -> str:
    """De leeswijzer voor de wall en het verslag: hoeveel werken, op welke term, en het meest
    geciteerde erbij — de kerncijfers in één zin, Engels zoals de hele inhoudslaag."""
    hoe = "exact phrase, most-cited first" if zoekwijze == "frase" else "relevance search on the loose words"
    kop = f"{total} work(s) on OpenAlex for '{term}' ({hoe})"
    top = hits[0] if hits else None
    if not top:
        return kop + "."
    detail = f"“{str(top.get('title') or '').strip()[:120]}”"
    if top.get("year"):
        detail += f", {top['year']}"
    detail += f", {int(top.get('citations') or 0)} citations"
    return f"{kop}; top cited: {detail}."


_WORKS = "https://api.openalex.org/works"


def _sanitize_concept(name: str) -> str:
    """Conceptnaam → veilige dimensie-slug (openalex_works_90d::<slug>)."""
    return "".join(c if c.isalnum() else "_" for c in name.strip().lower()).strip("_") or "concept"


def _parse_concepts(raw: str):
    """Parse `openalex_concepts` = 'naam:ID, naam:ID' → [(naam, ID), ...]. FAIL-CLOSED: None bij leeg, of
    bij één paar zonder geldig concept-ID (moet 'C'+cijfers zijn) — geen default, geen partial parse."""
    raw = (raw or "").strip()
    if not raw:
        return None
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            return None
        name, cid = (x.strip() for x in part.rsplit(":", 1))
        if not name or not (cid.startswith("C") and cid[1:].isdigit()):
            return None
        out.append((name, cid))
    return out or None


def _window(today: datetime.date):
    """90/30-telvenster (identiek voor alle concepten, voor vergelijkbaarheid). R = einde laatste COMPLETE
    week (zaterdag; zelfde weekgrens-logica als Trends). eind = R−30 (buffer voor indexeer-lag), start =
    R−120 (90 dagen breed). Label = venster-eind. Geeft (start_iso, end_iso, label_iso)."""
    dss = (today.weekday() + 1) % 7                                  # ma=0..zo=6 → zondag=0
    last_complete_sunday = today - datetime.timedelta(days=dss + 7)  # start (zo) van de laatste complete week
    R = last_complete_sunday + datetime.timedelta(days=6)           # zaterdag = einde laatste complete week
    end = R - datetime.timedelta(days=30)
    start = R - datetime.timedelta(days=120)
    return start.isoformat(), end.isoformat(), end.isoformat()


def _yr(v) -> int | None:
    """Parse een jaar (int of str) naar een 4-cijferig jaartal; anders None (veld valt weg)."""
    try:
        y = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return y if 1000 <= y <= 9999 else None


def _build_filter(payload: dict) -> tuple[str, str | None]:
    """Bouw de OpenAlex `filter=`-string uit de optionele payload-velden — DE ENIGE plek waar de mapping
    veld→filter leeft (reference, don't copy). Een leeg/afwezig veld laat zijn filter WEG; geen enkel
    filter-veld → lege string (= huidige zoekopdracht, alleen search=). Returnt (filter_string, error):
    is `error` niet None, dan is de combinatie ongeldig en moet de caller WEIGEREN vóór de API-call.

    Grens: OR (pipe) mag ALLEEN binnen één filter staan (bv. `abstract.search:a|b|c`). Twee verschillende
    filters met een pipe verbinden (`type:x|is_retracted:false`) geeft een API-fout — dat weigeren we hier
    deterministisch, vóór de call. Een komma in een waarde zou eveneens een tweede filter fabriceren."""
    clauses: list[tuple[str, str]] = []
    wt = str(payload.get("work_type") or "").strip()
    if wt:
        clauses.append(("type", wt))
    if payload.get("journal_only"):
        clauses.append(("primary_location.source.type", "journal"))
    if payload.get("exclude_retracted"):
        clauses.append(("is_retracted", "false"))
    terms = [str(t).strip() for t in (payload.get("abstract_terms") or []) if str(t).strip()]
    if terms:
        clauses.append(("abstract.search", "|".join(terms)))       # OR BINNEN één filter (pipe)
    fy = _yr(payload.get("from_year"))
    if fy is not None:
        clauses.append(("from_publication_date", f"{fy:04d}-01-01"))
    ty = _yr(payload.get("to_year"))
    if ty is not None:
        clauses.append(("to_publication_date", f"{ty:04d}-12-31"))
    mc = payload.get("min_citations")
    if mc not in (None, "", 0, "0"):
        try:
            clauses.append(("cited_by_count", f">{int(mc)}"))
        except (TypeError, ValueError):
            pass
    # Validatie vóór assemblage: een komma in een waarde zou de filter-grammatica breken (tweede filter).
    for k, v in clauses:
        if "," in v:
            return "", f"filterwaarde voor '{k}' bevat een komma — zou twee filters mengen"
    fs = ",".join(f"{k}:{v}" for k, v in clauses)
    # Een pipe direct gevolgd door een nieuwe filter-key (bv. '|type:') = OR tussen twee filters → ongeldig.
    if re.search(r"\|[A-Za-z_.]+:", fs):
        return "", "OR (pipe) verbindt twee filters — pipe mag alleen binnen één filter"
    return fs, None


class OpenalexSkill(DataSourceSkill):
    name = "openalex_evidence"
    input_schema = (
        "term: str (required — an ENGLISH search term. Up to 3 words = exact phrase, most-cited first — "
        "the precise form, e.g. 'adhesives footwear'; 4+ words = relevance search on the loose words. "
        "Join alternatives with ' OR ' (each clause is searched separately and the results merged). "
        "Never a whole research question as one term). "
        "Optional (an empty field drops its filter): "
        "work_type: str (OpenAlex type filter; 'article' recommended for peer-reviewed work; empty = all "
        "types) · journal_only: bool (journals only: primary_location.source.type:journal) · "
        "exclude_retracted: bool (drop retracted works: is_retracted:false; recommended true) · "
        "abstract_terms: list[str] (words that must occur in the abstract — OR within one filter: "
        "abstract.search:a|b|c) · from_year: int / to_year: int (publication-year bounds) · "
        "min_citations: int (cited_by_count:>n) · limit: int (default 5) · locale: str (echoed back)"
    )
    required_payload = ("term",)
    output_schema = ("list: total: int, hits: list[{title, url (OpenAlex work id), doi, authors, year, "
                     "citations, topic, abstract (up to 2000 chars)}], text (summary for the wall), "
                     "filter: str (the OpenAlex filter used — empty when unfiltered), zoekwijze "
                     "(frase|relevantie) | no_data + reason | error")
    SOURCE = "openalex"
    CATALOG_LABEL = "OpenAlex (academische tellers)"
    # Flow-bron: per puls tellen we de works die in een 90-daags publicatievenster VERSCHENEN (niet de
    # cumulatieve voorraad). De tegel toont het niveau zelf — geen eerste-verschillen nodig.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    needs_secret = True
    cost = "rate_limited"
    required_env = ("OPENALEX_API_KEY",)
    optional_env = ("openalex_mailto",)
    # De planner leest de eerste 160 tekens: daar moet staan WAT de bron is en HOE je hem vraagt.
    description = (
        "Academic papers via OpenAlex: give an English term of 1-3 words (exact phrase, most-cited "
        "first) or 4+ words (relevance search). Returns title, link, DOI, authors, year, citations and "
        "the abstract per work; 'no_data' when the corpus has nothing on the term. Also the weekly "
        "works-flow per pinned concept for the observation store (collect_series)."
    )

    def available_metrics(self, context=None) -> list[str]:
        """Eén nominaal veld; de echte reeksen (openalex_works_90d::<concept>) schrijft collect_series zelf."""
        return ["works_90d"]

    # `is_configured` is bewust NIET overschreven (scope 54). Hij zei "altijd True, keyless", terwijl
    # `required_env` de sleutel eist en `run` er zonder faalt. Twee waarheden over dezelfde vraag: het
    # opstartrapport en de bronnen-view meldden "scherp", en de configuratiepoort van scope 53 liet de
    # skill in de planner-catalogus staan om hem daarna bij elke run te zien falen. Nu geldt de
    # generieke regel van DataSourceSkill: geconfigureerd = de sleutel staat in settings of env.

    def daily_values(self, context, datum: str) -> dict:
        """OpenAlex schrijft via collect_series (eigen pad met custom venster/label/meta), niet via het
        generieke totaal-pad. Hier dus niets."""
        return {"works_90d": None}

    def collect_series(self, context, today, obs, *, _fetch=None):
        """FLOW-collectie per gepind concept: het aantal works dat in een 90-daags publicatievenster
        VERSCHEEN — `works?filter=concepts.id:<ID>,from_publication_date:<start>,to_publication_date:<end>`
        → `meta.count`. Vervangt de BEVROREN `/concepts/<id>.works_count`-aggregaat (counts_by_year
        2023-2025 = 0). Dit is een FLOW (niveau per venster), GEEN cumulatieve stand → analyse direct op
        niveau, geen eerste-verschillen nodig.

        Venster (identiek voor alle concepten → vergelijkbaar): 90d breed, eindigend 30d vóór R (= einde
        laatste complete week, zelfde weekgrens als Trends). De 30d-buffer dekt de OpenAlex-indexeer-lag.
        Label = venster-eind (de meetperiode, niet de pulsdatum). Meta draagt from/to_publication_date zodat
        elk punt reproduceerbaar is en de buffer later herzien kan worden zonder de reeks weg te gooien.

        Fail-closed: `openalex_concepts` leeg/ontbrekend/paar-zonder-geldig-ID → ERROR + niets (geen default).
        API-fout/timeout/lege meta → gat + ERROR (geen write, geen interpolatie). meta.count=0 bij een
        geldige respons → 0 wegschrijven (echte observatie, bv. ecodesign in dunne weken). Idempotent: label
        al aanwezig voor een veld → niet opnieuw fetchen. `_fetch(url)` injecteerbaar voor tests."""
        concepts = _parse_concepts((getattr(context, "settings", {}) or {}).get("openalex_concepts", ""))
        if concepts is None:
            log.error("OpenAlex: config 'openalex_concepts' ontbreekt, is leeg of bevat een paar zonder "
                      "geldig concept-ID (verwacht 'naam:C123, naam:C456') — bron levert niets "
                      "(fail-closed, geen default).")
            return []
        start, end, label = _window(today)
        settings = getattr(context, "settings", {}) or {}
        mailto = settings.get("openalex_mailto", "info@nooch.earth")
        key = settings.get("OPENALEX_API_KEY") or os.getenv("OPENALEX_API_KEY")   # optioneel (polite pool)
        ua = f"NoochVillage/1.0 (nooch.earth; mailto:{mailto})"
        written = []
        for name, cid in concepts:
            slug = _sanitize_concept(name)
            metric = f"openalex_works_90d::{slug}"
            if any(r.get("datum") == label for r in obs.daily_series(metric, bron="openalex")):
                continue                                          # idempotent → geen refetch
            url = (f"{_WORKS}?filter=concepts.id:{urllib.parse.quote(cid)},"
                   f"from_publication_date:{start},to_publication_date:{end}"
                   f"&per_page=1&mailto={urllib.parse.quote(mailto)}")
            if key:
                url += f"&api_key={urllib.parse.quote(key)}"
            try:
                data = (_fetch(url) if _fetch else
                        self._fetch_with_backoff(urllib.request.Request(url, headers={"User-Agent": ua})))
                cnt = (data.get("meta") or {}).get("count")
            except Exception as exc:
                log.error("OpenAlex concept '%s' (%s) venster %s..%s faalde: %s — gat.",
                          name, cid, start, end, exc)
                continue
            if cnt is None:
                log.error("OpenAlex concept '%s' (%s): geldige respons maar lege meta.count — gat.", name, cid)
                continue
            meta = {"dimension": "concept", "value": name,
                    "from_publication_date": start, "to_publication_date": end}
            if obs.record_daily("openalex", metric, int(cnt), bron="openalex", datum=label, meta=meta):
                written.append(("openalex", f"works_90d::{slug}", label))
            if _fetch is None:
                time.sleep(0.5)
        return written

    def run(self, payload: dict, context) -> dict:
        key = (getattr(context, "settings", {}).get("OPENALEX_API_KEY")
               or os.getenv("OPENALEX_API_KEY"))
        if not key:
            raise RuntimeError(
                "OPENALEX_API_KEY ontbreekt in .env — openalex_evidence faalt bewust closed"
            )

        term   = payload.get("term", "").strip()
        locale = payload.get("locale", "")
        if not term:
            return {"error": "geen term opgegeven", "hits": [], "locale": locale, "filter": ""}

        limit  = int(payload.get("limit", 5))
        mailto = getattr(context, "settings", {}).get("openalex_mailto", "info@nooch.earth")
        ua     = f"NoochVillage/1.0 (nooch.earth; mailto:{mailto})"

        # Jaar-aandeel-modus: relatieve academische aandacht per jaar (voor de lange-boog-
        # voortzetting voorbij de ngram-cutoff). Zelfde bron/capaciteit, andere query.
        if payload.get("mode") == "yearly":
            return self._yearly(term, locale, mailto, key, ua)

        # Deterministische filters uit de optionele velden (één plek: _build_filter). Ongeldige combinatie
        # (bv. een pipe tussen twee filters) → WEIGER vóór de call i.p.v. de API te laten falen.
        filter_str, ferr = _build_filter(payload)
        if ferr:
            return {"error": ferr, "term": term, "locale": locale, "hits": [], "filter": ""}

        # Boolean-keten? OpenAlex kent geen OR in search=, dus splitsen we op ' OR ' en zoeken elke
        # deel-frase apart, elk nog steeds als EXACTE frase (de 8-juli-fix: `"barefoot shoes"` → 204
        # on-topic i.p.v. 14.906 losse-woord-hits). De unie (dedup op work-id, meest geciteerd eerst)
        # is het antwoord. Eén clause → precies het oude gedrag (één call, één frase-zoek).
        clauses = _split_or(term)
        zoekwijze = _zoekwijze(clauses[0] if clauses else term)
        if len(clauses) <= 1:
            results, total = self._search_results(clauses[0] if clauses else term,
                                                  limit, filter_str, mailto, key, ua)
            time.sleep(0.5)
        else:
            seen: dict = {}
            merged: list = []
            for clause in clauses[:_MAX_OR_CLAUSES]:
                part, _tot = self._search_results(clause, limit, filter_str, mailto, key, ua)
                for w in part:
                    wid = w.get("id")
                    if wid and wid not in seen:
                        seen[wid] = w
                        merged.append(w)
                time.sleep(0.2)                                   # kleine pauze tussen deel-calls
            merged.sort(key=lambda w: w.get("cited_by_count", 0), reverse=True)
            results = merged[:limit]
            total = len(results)
            zoekwijze = "frase" if all(_zoekwijze(c) == "frase" for c in clauses) else "relevantie"

        if total == 0 or not results:
            return {"term": term, "locale": locale, "total": 0, "zoekwijze": zoekwijze,
                    "no_data": True, "reason": "geen werken gevonden voor deze term",
                    "hits": [], "filter": filter_str}

        hits = []
        for work in results:
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in (work.get("authorships") or [])[:3]
            ]
            topic    = (work.get("primary_topic") or {}).get("display_name", "")
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            # Het adres: het work-id (https://openalex.org/W…) is klikbaar en stabiel; de DOI erbij
            # als die er is. Zonder adres toonde het verslag "• titel — abstract" zonder link.
            hits.append({
                "source":    "openalex",
                "locale":    locale,
                "title":     work.get("title") or "",
                "url":       str(work.get("id") or ""),
                "doi":       str(work.get("doi") or ""),
                "authors":   [a for a in authors if a],
                "year":      work.get("publication_year"),
                "citations": work.get("cited_by_count", 0),
                "topic":     topic,
                "abstract":  abstract,
            })

        time.sleep(0.5)
        return {"term": term, "locale": locale, "total": total, "hits": hits, "filter": filter_str,
                "zoekwijze": zoekwijze, "text": _als_tekst(term, total, hits, zoekwijze)}

    def _search_results(self, phrase: str, limit: int, filter_str: str,
                        mailto: str, key: str, ua: str):
        """Eén zoekopdracht op OpenAlex → (results-lijst, meta-count). Tot drie woorden als EXACTE
        frase tussen aanhalingstekens met citatie-sortering (de 8-juli-fix tegen off-topic
        losse-woord-hits); langer ongequote op relevantie (zie `_zoekwijze`). Fail-soft: een lege
        respons geeft ([], 0). DE plek waar de search-URL wordt gebouwd — één bron van waarheid."""
        if _zoekwijze(phrase) == "frase":
            q = urllib.parse.quote(f'"{phrase}"')
            sortering = "&sort=cited_by_count:desc"
        else:
            q = urllib.parse.quote(phrase)
            sortering = ""                                  # geen sort = OpenAlex' relevantie-score
        url = (f"{_BASE}?search={q}"
               f"&per_page={limit}"
               f"{sortering}"
               f"&select={_SELECT}")
        if filter_str:                                            # leeg = filterloos = huidige zoekopdracht
            url += f"&filter={urllib.parse.quote(filter_str, safe=':|,><.-')}"
        url += (f"&mailto={urllib.parse.quote(mailto)}"
                f"&api_key={urllib.parse.quote(key)}")
        req  = urllib.request.Request(url, headers={"User-Agent": ua})
        data = self._fetch_with_backoff(req)
        return data.get("results", []), data.get("meta", {}).get("count", 0)

    def _yearly(self, term: str, locale: str, mailto: str, key: str, ua: str) -> dict:
        """Twee group_by=publication_year-calls (term + totaal) → relatief aandeel per jaar."""
        creds = (f"&mailto={urllib.parse.quote(mailto)}"
                 f"&api_key={urllib.parse.quote(key)}")
        q = urllib.parse.quote(term)
        term_url  = f"{_BASE}?search={q}&group_by=publication_year{creds}"
        total_url = f"{_BASE}?group_by=publication_year{creds}"

        term_data  = self._fetch_with_backoff(
            urllib.request.Request(term_url, headers={"User-Agent": ua}))
        total_data = self._fetch_with_backoff(
            urllib.request.Request(total_url, headers={"User-Agent": ua}))

        series = relative_attention(_parse_year_groups(term_data),
                                    _parse_year_groups(total_data))
        time.sleep(0.5)
        if not series:
            return {"term": term, "locale": locale, "mode": "yearly",
                    "no_data": True, "reason": "geen jaardata gevonden", "series": {}}
        return {"term": term, "locale": locale, "mode": "yearly", "series": series}

    def _fetch_with_backoff(self, req, timeout: int = 12, max_retries: int = 4) -> dict:
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
                    continue
                raise
        raise RuntimeError("OpenAlex rate-limit overschreden na 4 pogingen")
