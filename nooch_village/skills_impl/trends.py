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

# ── Stemming-paren (ratio A/B, geen gedeeld anker) ────────────────────────────────────────────────
# Google Trends' 0-100 is relatief aan de zwaarste term per request; naast een dominant anker comprimeert
# elke niche naar 0-1 (gemeten 2026-07-08, iteratie 1: docs/trends_sentiment_termset_meting_2026-07-08.md).
# Herontwerp: PAREN van tegengestelde stemming met vergelijkbare grootte. Per paar één request [A, B];
# ratio per datapunt = waarde_A / waarde_B uit dezelfde response — geen gedeeld anker, geen schaling.
#
# ORIËNTATIE (meetconstante — paren omdraaien breekt de reeks): A = zuinigheid/behoud-kant, B =
# toegeeflijkheid/nieuw-kant. Ratio A/B stijgt = versobering-stemming stijgt (socionomics). De paren komen
# uit config-sleutel `trends_pairs` — FAIL-CLOSED, GEEN default, GEEN partial parse: ontbrekend/leeg/één
# misvormd paar → luide error, bron levert niets.
_TIMEFRAME_DEFAULT = "today 5-y"        # weekly resolutie; de ratio gebruikt het recente (laatste) punt


def _parse_pairs(raw: str):
    """Parse `trends_pairs` ('A:B, A:B') → [(A, B), ...]. FAIL-CLOSED: None bij leeg, of bij één misvormd
    paar (geen ':' of lege A/B) — liever luid stuk dan stil half. Termen mogen spaties bevatten; whitespace
    rond termen en scheiders wordt getrimd."""
    raw = (raw or "").strip()
    if not raw:
        return None
    pairs = []
    for part in raw.split(","):
        part = part.strip()
        if part.count(":") != 1:                # geen of meerdere ':' → misvormd
            return None
        a, b = (x.strip() for x in part.split(":", 1))
        if not a or not b:
            return None
        pairs.append((a, b))
    return pairs or None


def _pair_field(a: str, b: str) -> str:
    """Veldsleutel per paar → metric `trends_ratio_<A>_<B>_day` (bijv. trends_ratio_second_hand_brand_new_day)."""
    return f"ratio_{_sanitize_field(a)}_{_sanitize_field(b)}"


def _sanitize_field(term: str) -> str:
    """Term → veilige observatie-veldsleutel (trends_<veld>_day)."""
    return "".join(c if c.isalnum() else "_" for c in term.strip().lower()).strip("_") or "term"


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
        """DYNAMISCHE velden: één ratio-veld per stemming-paar uit `trends_pairs`. Zonder context, of bij een
        ongeldige/lege config → leeg (de paren staan in de config, niet vast in de klasse)."""
        pairs = _parse_pairs((getattr(context, "settings", {}) or {}).get("trends_pairs", "")) if context else None
        return [_pair_field(a, b) for a, b in pairs] if pairs else []

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
        """Stemming-ratio per paar uit `trends_pairs`: per paar één request [A, B]; ratio = waarde_A /
        waarde_B uit dezelfde response (float, ONGESCHAALD, niet naar int afronden). Oriëntatie A =
        zuinigheid/behoud, B = toegeeflijkheid/nieuw (meetconstante; paren omdraaien breekt de reeks).
        Veld/metric = trends_ratio_<A>_<B>_day.

        Fail-closed:
          - `trends_pairs` ontbreekt/leeg/één misvormd paar → ERROR-log, bron levert niets (geen default,
            geen partial parse).
          - NUL-GUARD op de noemer: B == 0 of afwezig op het recente punt → dat punt NIET schrijven + ERROR
            (scope 0 mat 100% niet-nul voor alle B; een 0 daar is een verdachte response, geen observatie).
          - A == 0 bij geldige B → ratio 0 wegschrijven (echte observatie).
          - mislukte/lege request → gat (None) + ERROR (geen interpolatie).
        `_fetch(payload, timeframe, geo) -> df` injecteerbaar (geen netwerk in tests)."""
        settings = getattr(context, "settings", {}) or {}
        pairs = _parse_pairs(settings.get("trends_pairs", ""))
        if pairs is None:
            log.error("Trends stemming-paren: config 'trends_pairs' ontbreekt, is leeg of bevat een misvormd "
                      "paar (verwacht 'A:B, A:B') — bron levert niets (fail-closed, geen partial parse).")
            return {}
        out = {_pair_field(a, b): None for a, b in pairs}
        geo = (settings.get("trends_geo") or "").strip()          # leeg = worldwide (zoals de scope-0-meting)
        timeframe = (settings.get("trends_timeframe") or _TIMEFRAME_DEFAULT).strip()
        hl = settings.get("trends_hl", "en-US")
        real = _fetch is None
        if real:
            try:
                from pytrends.request import TrendReq
            except ImportError:
                return out                                        # dependency ontbreekt → alles None
            try:
                pytrends = TrendReq(hl=hl, tz=0, timeout=(10, 25),
                                    requests_args={"headers": {"User-Agent": _USER_AGENT}})
            except Exception as exc:
                log.error("Trends init faalde: %s — bron levert niets.", exc)
                return out

            def _fetch(payload, tf, g):
                pytrends.build_payload(payload, cat=0, timeframe=tf, geo=g, gprop="")
                return pytrends.interest_over_time()
        for a, b in pairs:
            field = _pair_field(a, b)
            try:
                df = _fetch([a, b], timeframe, geo)
            except Exception as exc:
                log.error("Trends paar '%s÷%s' request faalde: %s — gat.", a, b, exc)
                continue
            if df is None or getattr(df, "empty", True) or a not in df or b not in df:
                log.error("Trends paar '%s÷%s': lege/incomplete respons — gat.", a, b)
                continue
            b_recent = df[b].tolist()[-1]
            if not b_recent:                                      # noemer 0/afwezig → verdacht (scope 0: 100% niet-nul)
                log.error("Trends paar '%s÷%s': noemer B=%r op het recente punt — punt geskipt "
                          "(verdachte respons).", a, b, b_recent)
                continue
            out[field] = round(df[a].tolist()[-1] / b_recent, 4)  # float, ongeschaald; A=0 → 0 (echte obs)
            if real:
                time.sleep(1.0)                                   # beleefd tussen paar-requests
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
