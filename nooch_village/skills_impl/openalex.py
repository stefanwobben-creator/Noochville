"""OpenAlexSkill — capability "openalex_evidence".

Zoekt academische werken op via de OpenAlex API.
Authenticatie via OPENALEX_API_KEY (vereist — skill faalt bewust closed zonder key).
Polite pool: mailto-adres in de User-Agent voor hogere rate-limit.
Mailto komt uit context.settings["openalex_mailto"] (settings.ini of .env).

Segmentatie:
  Elke aanroep draagt een `locale`-sleutel door in de output.
  Resultaten gesorteerd op citaties (meest geciteerd eerst).
  `no_data: True` onderscheidt "API werkt, maar niets gevonden" van een echte fout.

Rate-limit-gedrag:
  Bij HTTP 429: exponentiële backoff (2**attempt + jitter), max 4 pogingen.
  Daarna: raise (use_skill vangt dit op als {"error": ...}).

Fail-closed: ontbrekende key of definitieve fout → raise, nooit mock-data.
"""
from __future__ import annotations
import datetime
import logging
import os
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import json
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_BASE   = "https://api.openalex.org/works"
_SELECT = ("id,title,publication_year,cited_by_count,"
           "abstract_inverted_index,primary_topic,authorships")


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
    return " ".join(words[p] for p in sorted(words.keys()))[:400]


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


class OpenalexSkill(DataSourceSkill):
    name = "openalex_evidence"
    input_schema = "term: str (zoekterm, wordt als exacte frase gezocht). optioneel: limit: int, locale: str"
    output_schema = "lijst: total: int, hits: list[{title, authors, year, citations, topic, abstract}] | no_data | error"
    SOURCE = "openalex"
    # Flow-bron: per puls tellen we de works die in een 90-daags publicatievenster VERSCHENEN (niet de
    # cumulatieve voorraad). De tegel toont het niveau zelf — geen eerste-verschillen nodig.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    needs_secret = True
    cost = "rate_limited"
    required_env = ("OPENALEX_API_KEY",)
    optional_env = ("openalex_mailto",)
    description = (
        "Academische evidentie via OpenAlex (polite pool, backoff bij 429, fail-closed) + wekelijkse "
        "works-flow per gepind concept in een 90/30-venster (collect_series)."
    )

    def available_metrics(self, context=None) -> list[str]:
        """Eén nominaal veld; de echte reeksen (openalex_works_90d::<concept>) schrijft collect_series zelf."""
        return ["works_90d"]

    def is_configured(self, context) -> bool:
        """OpenAlex is keyless (polite pool via mailto) → altijd oproepbaar."""
        return True

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
            return {"error": "geen term opgegeven", "hits": [], "locale": locale}

        limit  = int(payload.get("limit", 5))
        mailto = getattr(context, "settings", {}).get("openalex_mailto", "info@nooch.earth")
        ua     = f"NoochVillage/1.0 (nooch.earth; mailto:{mailto})"

        # Jaar-aandeel-modus: relatieve academische aandacht per jaar (voor de lange-boog-
        # voortzetting voorbij de ngram-cutoff). Zelfde bron/capaciteit, andere query.
        if payload.get("mode") == "yearly":
            return self._yearly(term, locale, mailto, key, ua)

        # Exacte frase (aanhalingstekens om de term): het brede search= matcht anders losse woorden en
        # de citatie-sort surfacet dan hoog-geciteerde off-topic papers (diagnose 2026-07-08:
        # "barefoot shoes" gaf 14.906 hits, top-5 diabetes/vaatlijden; met frase → 204, top-5 on-topic).
        # Enkelwoord-termen zijn met quotes neutraal. `term` is hier gegarandeerd niet-leeg (guard hierboven).
        q   = urllib.parse.quote(f'"{term}"')
        url = (f"{_BASE}?search={q}"
               f"&per_page={limit}"
               f"&sort=cited_by_count:desc"
               f"&select={_SELECT}"
               f"&mailto={urllib.parse.quote(mailto)}"
               f"&api_key={urllib.parse.quote(key)}")

        req  = urllib.request.Request(url, headers={"User-Agent": ua})
        data = self._fetch_with_backoff(req)

        results = data.get("results", [])
        total   = data.get("meta", {}).get("count", len(results))

        if total == 0 or not results:
            time.sleep(0.5)
            return {"term": term, "locale": locale, "total": 0,
                    "no_data": True, "reason": "geen werken gevonden voor deze term",
                    "hits": []}

        hits = []
        for work in results:
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in (work.get("authorships") or [])[:3]
            ]
            topic    = (work.get("primary_topic") or {}).get("display_name", "")
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            hits.append({
                "source":    "openalex",
                "locale":    locale,
                "title":     work.get("title") or "",
                "authors":   [a for a in authors if a],
                "year":      work.get("publication_year"),
                "citations": work.get("cited_by_count", 0),
                "topic":     topic,
                "abstract":  abstract,
            })

        time.sleep(0.5)
        return {"term": term, "locale": locale, "total": total, "hits": hits}

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
