"""TrendsSkill — haalt Google Trends-data op per geo/locale.

Locale-model:
  Elke geo wordt gemapped op een taal (bijv. NL → nl, GB/US → en).
  Woorden per geo komen bij voorkeur uit het Lexicon voor die taal.
  Valt terug op keywords.txt + Library-goedkeuringen.

Output: `rows` (locale-bewust) + `keywords` (backward compat, eerste geo).
  Elke row: {term, locale, geo, interest_latest, direction, top_related}
        of: {term, locale, geo, no_data: True, reason: str}
  "geen data" is expliciet onderscheiden van een echte nul of interest=0.

Fail-closed per geo×term: netwerk-/rate-limit-fout faalt alleen dat segment.
"""
from __future__ import annotations
import os, json, time, random, logging
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

# Een realistische browser-User-Agent vermindert 429's: de pytrends-default-UA
# wordt sneller geblokkeerd door Google.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── Anker-ratio-normalisatie (snapshot-delta-analoog voor relatieve interesse) ────────────────────
# Google Trends' 0-100 is relatief aan de piek binnen het venster; waarden uit verschillende queries
# of vensters zijn dus NIET vergelijkbaar. Oplossing: query elke term SAMEN met een vast anker en sla
# de RATIO op (term/anker × 100). Die ratio is invariant onder Trends' herschaling (anker en term
# schalen met dezelfde factor), dus vergelijkbaar tussen termen én over de tijd.
#
# EIS AAN HET ANKER (cruciaal): stabiel, hoog volume, NIET-trending. Kiest een curator een trending
# term als anker, dan weerspiegelt de ratio de ruis van het anker i.p.v. de trend van de term — stil
# onzin-data. Het anker komt uit config-sleutel `trends_anchor` — FAIL-CLOSED, GEEN code-default: een
# ontbrekend/leeg anker is een luide error, de bron levert dan niets (nooit een stille default-term).
_TIMEFRAME_DEFAULT = "today 5-y"        # vast lang venster: genoeg historie voor stabiele normalisatie
_TRENDS_BATCH = 4                       # pytrends vergelijkt max 5 termen/request → 4 termen + het anker


def _approved_library_terms(context) -> list[str]:
    """De teller-termen: de approved-set uit de Library (status 'approved') — DEZELFDE bron/query als de
    Library→Keywords-Everywhere-koppeling (zie keywords_everywhere._approved_keywords). Dynamisch: de
    discovery-lus voedt Trends automatisch, geen aparte config-termenlijst meer."""
    lib = getattr(context, "library", None) if context is not None else None
    if lib is None:
        return []
    return [w for w, e in lib.all().items() if e.get("status") == "approved"]


def _sanitize_field(term: str) -> str:
    """Term → veilige observatie-veldsleutel (trends_<veld>_day)."""
    return "".join(c if c.isalnum() else "_" for c in term.strip().lower()).strip("_") or "term"


def _ratio(anchor_recent, term_recent):
    """De genormaliseerde interesse: term/anker × 100. None als het anker 0 is (niet te normaliseren).
    Invariant onder Trends' herschaling: als de hele reeks met factor k schaalt, schalen anker én term
    mee → de ratio blijft gelijk. Dát maakt de waarde vergelijkbaar tussen termen en over de tijd."""
    if not anchor_recent or anchor_recent <= 0:
        return None
    return round(term_recent / anchor_recent * 100)


def rotate_window(items: list, cursor: int, size: int) -> tuple[list, int]:
    """Round-robin venster van maximaal `size` items vanaf `cursor`.

    Geeft (venster, volgende_cursor). Zo bevraagt elke puls maar een paar termen en
    rolt over meerdere pulsen door de hele set — dat begrenst de request-burst die
    Google Trends 429't, ongeacht hoe groot de woordenlijst wordt.

    Leeg → ([], 0). size <= 0 of size >= aantal → alle items (cursor terug naar 0).
    """
    n = len(items)
    if n == 0:
        return [], 0
    if size <= 0 or size >= n:
        return list(items), 0
    start = cursor % n
    window = [items[(start + i) % n] for i in range(size)]
    return window, (start + size) % n


# Geo-code → taal (uitbreidbaar)
_GEO_LOCALE: dict[str, str] = {
    "NL": "nl",
    "BE": "nl",
    "GB": "en",
    "US": "en",
    "AU": "en",
    "CA": "en",
    "IE": "en",
    "": "en",      # lege string = worldwide discovery → EN (Engelse discovery-koers)
}


def _geo_to_locale(geo: str) -> str:
    return _GEO_LOCALE.get(geo.upper(), "en")


def _normalize_rising_value(raw):
    """rising-value is een int (stijgingspercentage) of de string 'Breakout'.
    Breakout = >5000% of vanuit nul; we behouden het signaal als hoge sentinel
    en markeren het apart, zodat het sterkste discovery-signaal niet wegvalt."""
    if isinstance(raw, str) and raw.strip().lower() == "breakout":
        return 10000, True
    try:
        return int(raw), False
    except (TypeError, ValueError):
        return 0, False


def _keywords_for_locale(locale: str, context) -> list[str]:
    """Woorden voor een locale: Lexicon-taalvak heeft prioriteit, dan keywords.txt + Library.
    Bevestigde concurrenten (context.competitors) komen er als extra zaad bij, zodat de
    Trends-run hun gerelateerde zoektermen ophaalt en die via de Librarian-pijp lopen."""
    lexicon = getattr(context, "lexicon", None)
    base: list[str] = []
    if lexicon:
        base = list(lexicon.words_for_lang(locale, status_filter="approved"))

    if not base:
        # Fallback: keywords.txt + Library (taal-onbewust)
        path = os.path.join(os.path.dirname(context.data_dir), "config", "keywords.txt")
        kws: list[str] = []
        if os.path.exists(path):
            kws = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
        lib = getattr(context, "library", None)
        if lib:
            kws.extend(w for w, e in lib.all().items()
                       if e.get("status") == "approved" and w not in kws)
        base = kws or ["duurzame sneakers", "vegan schoenen", "plastic free shoes"]

    comp = getattr(context, "competitors", None)
    if comp is not None:
        for c in comp.confirmed():
            if c not in base:
                base.append(c)
    return base


def _read_keywords(context) -> list[str]:
    """Backward compat: geeft keywords voor de standaard geo terug."""
    return _keywords_for_locale(
        _geo_to_locale(context.settings.get("trends_geo", "NL")), context)


class TrendsSkill(DataSourceSkill):
    name = "google_trends"
    SOURCE = "trends"
    # Flux-bron: relatieve interesse is een niveau op een moment (geen cumulatieve stand) → de tegel
    # toont de waarde/lijn zelf. Weekly: Trends-data is niet dagvers genoeg voor daily.
    kind = "flux"
    DEFAULT_FREQUENCY = "weekly"
    cost = "rate_limited"
    description = (
        "Haalt Google Trends-data op per geo/locale "
        "(interesse + gerelateerde zoekopdrachten). "
        "Woorden per geo komen uit het meertalige Lexicon. "
        "Fail-closed per geo×term."
    )

    def available_metrics(self, context=None) -> list[str]:
        """DYNAMISCHE velden: de approved Library-termen als veilige sleutels (zoals KE de Library volgt).
        Zonder context (bv. het koppelscherm) → leeg, want de termen komen uit de Library, niet vast in de skill."""
        return [_sanitize_field(t) for t in _approved_library_terms(context)]

    def is_configured(self, context) -> bool:
        """Keyless (pytrends). 'Geconfigureerd' = de pytrends-dependency is importeerbaar. Een pytrends
        die wél importeert maar bij de CALL breekt (Google wijzigt z'n endpoint) valt fail-closed naar
        None per term → verschijnt als 'dood', niet als crash of 'niet geconfigureerd'."""
        try:
            import pytrends.request  # noqa: F401
            return True
        except Exception:
            return False

    def daily_values(self, context, datum: str, *, _fetch=None) -> dict:
        """Genormaliseerde interesse per approved Library-term via de anker-ratio. Batcht de termen in
        groepjes van 4 met het anker als 5e term in ELKE request (pytrends-max = 5), zodat term én anker
        binnen dezelfde request/normalisatie zitten; ratio = term_recent / anker_recent × 100.

        Fail-closed:
          - geen Library-termen → alles None (niets te doen).
          - `trends_anchor` ontbreekt/leeg → ERROR-log, bron levert niets (GEEN code-default).
          - een batch die faalt/leeg terugkomt → die termen blijven een GAT (None) + ERROR-log.
          - anker 0 of afwezig in een batch-respons → hele batch geskipt + ERROR-log (deel-door-nul-guard;
            een anker hoort nooit 0 te zijn).
        Een term die 0 teruggeeft is een ECHTE observatie → als 0 weggeschreven, geen gat.
        `_fetch(payload, timeframe, geo) -> df` injecteerbaar (geen netwerk in tests)."""
        terms = _approved_library_terms(context)
        out = {_sanitize_field(t): None for t in terms}
        if not terms:
            return out
        settings = getattr(context, "settings", {}) or {}
        anchor = (settings.get("trends_anchor") or "").strip()
        if not anchor:
            log.error("Trends anker-ratio: config 'trends_anchor' ontbreekt of is leeg — bron levert niets "
                      "(fail-closed, geen default-anker).")
            return out
        geo = (settings.get("trends_geo") or "NL").strip()
        timeframe = (settings.get("trends_timeframe") or _TIMEFRAME_DEFAULT).strip()
        hl = settings.get("trends_hl", "nl-NL")
        real = _fetch is None
        if real:
            try:
                from pytrends.request import TrendReq
            except ImportError:
                return out                                  # dependency ontbreekt → alles None
            try:
                pytrends = TrendReq(hl=hl, tz=60, timeout=(10, 25),
                                    requests_args={"headers": {"User-Agent": _USER_AGENT}})
            except Exception as exc:
                log.error("Trends init faalde: %s — bron levert niets.", exc)
                return out

            def _fetch(payload, tf, g):
                pytrends.build_payload(payload, cat=0, timeframe=tf, geo=g, gprop="")
                return pytrends.interest_over_time()
        for i in range(0, len(terms), _TRENDS_BATCH):
            batch = terms[i:i + _TRENDS_BATCH]
            b = i // _TRENDS_BATCH
            try:
                df = _fetch([anchor] + batch, timeframe, geo)
            except Exception as exc:
                log.error("Trends batch %d faalde: %s — geen write voor deze batch (gat).", b, exc)
                continue
            if df is None or getattr(df, "empty", True) or anchor not in df:
                log.error("Trends: anker '%s' ontbreekt in respons van batch %d — batch geskipt.", anchor, b)
                continue
            a_recent = int(df[anchor].tolist()[-1])
            if a_recent == 0:
                log.error("Trends: anker '%s' geeft 0 in batch %d — batch geskipt (anker hoort nooit 0 te "
                          "zijn; iets mis met de request).", anchor, b)
                continue
            for term in batch:
                if term not in df:
                    continue                                # term afwezig in respons → gat (None blijft)
                out[_sanitize_field(term)] = _ratio(a_recent, int(df[term].tolist()[-1]))   # 0 → 0 (echte obs)
            if real:
                time.sleep(1.0)                             # beleefd (onofficieel endpoint)
        return out

    def _select_window(self, keywords: list[str], context) -> list[str]:
        """Beperk tot een roterend venster (default 3) en bewaar de cursor, zodat de
        request-burst begrensd blijft en de set over meerdere pulsen toch rondkomt."""
        size = int(context.settings.get("trends_keywords_per_pulse", "3"))
        path = os.path.join(context.data_dir, "trends_cursor.json")
        try:
            cursor = int(json.load(open(path)).get("cursor", 0))
        except Exception:
            cursor = 0
        window, nxt = rotate_window(keywords, cursor, size)
        try:
            with open(path, "w") as f:
                json.dump({"cursor": nxt}, f)
        except Exception:
            pass
        return window

    def _fetch(self, pytrends, keyword, geo, timeframe="today 12-m", max_retries=4, base_delay=8):
        """Exponentiele backoff bij 429."""
        retries = 0
        while retries < max_retries:
            try:
                pytrends.build_payload([keyword], cat=0,
                                       timeframe=timeframe, geo=geo, gprop="")
                return pytrends.interest_over_time(), pytrends.related_queries()
            except Exception as e:
                if "429" in str(e):
                    delay = min(base_delay * (2 ** retries) + random.uniform(1, 3), 90)
                    time.sleep(delay)
                    retries += 1
                else:
                    raise
        raise RuntimeError(f"max retries voor '{keyword}' (geo={geo})")

    def run(self, payload: dict, context) -> dict:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return {"error": "pytrends niet geinstalleerd (pip install pytrends)",
                    "keywords": {}, "rows": []}

        # Welke geo's worden bevraagd?
        geos_raw = payload.get("geos") or [context.settings.get("trends_geo", "NL")]
        if isinstance(geos_raw, str):
            geos_raw = [geos_raw]
        geos: list[str] = list(dict.fromkeys(geos_raw))  # dedup, volgorde behouden
        timeframe = payload.get("timeframe", "today 12-m")
        hl        = payload.get("hl", "nl-NL")

        pytrends = TrendReq(hl=hl, tz=60, timeout=(10, 25),
                            requests_args={"headers": {"User-Agent": _USER_AGENT}})

        rows: list[dict]  = []
        legacy: dict      = {}           # eerste geo → keywords-dict (backward compat)
        first_geo         = geos[0] if geos else ""

        for geo in geos:
            locale   = _geo_to_locale(geo)
            if payload.get("keywords"):
                keywords = payload["keywords"]          # expliciet meegegeven: respecteer volledig
            else:
                keywords = self._select_window(_keywords_for_locale(locale, context), context)

            for kw in keywords:
                try:
                    interest_df, related = self._fetch(pytrends, kw, geo, timeframe=timeframe)

                    if interest_df is not None and not interest_df.empty and kw in interest_df:
                        series  = interest_df[kw].tolist()
                        latest  = int(series[-1])
                        prev    = int(series[-2]) if len(series) > 1 else latest
                        direction = (
                            "stijgend" if latest > prev else
                            "dalend"   if latest < prev else
                            "vlak"
                        )
                        top_related: list = []
                        if kw in related and related[kw].get("top") is not None:
                            top_related = (related[kw]["top"][["query", "value"]]
                                           .head(5).to_dict("records"))
                        rising_related: list = []
                        if kw in related and related[kw].get("rising") is not None:
                            for rec in related[kw]["rising"][["query", "value"]].head(5).to_dict("records"):
                                val, is_breakout = _normalize_rising_value(rec.get("value"))
                                rising_related.append({
                                    "query": rec.get("query"),
                                    "value": val,
                                    "breakout": is_breakout,
                                })
                        row = {
                            "term":            kw,
                            "locale":          locale,
                            "geo":             geo,
                            "interest_latest": latest,
                            "direction":       direction,
                            "top_related":     top_related,
                            "rising_related":  rising_related,
                        }
                        if geo == first_geo:
                            legacy[kw] = {
                                "interest_latest": latest,
                                "direction":       direction,
                                "top_related":     top_related,
                                "rising_related":  rising_related,
                            }
                    else:
                        row = {
                            "term":    kw,
                            "locale":  locale,
                            "geo":     geo,
                            "no_data": True,
                            "reason":  "geen data voor deze geo",
                        }
                        if geo == first_geo:
                            legacy[kw] = {"no_data": True}
                    rows.append(row)

                except Exception as e:
                    row = {
                        "term":    kw,
                        "locale":  locale,
                        "geo":     geo,
                        "no_data": True,
                        "reason":  str(e),
                    }
                    rows.append(row)
                    if geo == first_geo:
                        legacy[kw] = {"error": str(e)}

                time.sleep(1)   # vriendelijk voor Google

        return {
            "rows":     rows,          # locale-bewust (nieuw)
            "keywords": legacy,        # backward compat (eerste geo)
            "geos":     geos,
            "geo":      first_geo,     # backward compat veld
        }
