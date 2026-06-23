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
import os, json, time, random
from nooch_village.skills import Skill

# Een realistische browser-User-Agent vermindert 429's: de pytrends-default-UA
# wordt sneller geblokkeerd door Google.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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
    """Woorden voor een locale: Lexicon-taalvak heeft prioriteit, dan keywords.txt + Library."""
    lexicon = getattr(context, "lexicon", None)
    if lexicon:
        words = lexicon.words_for_lang(locale, status_filter="approved")
        if words:
            return words

    # Fallback: keywords.txt + Library (taal-onbewust)
    path = os.path.join(os.path.dirname(context.data_dir), "config", "keywords.txt")
    kws: list[str] = []
    if os.path.exists(path):
        kws = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]
    lib = getattr(context, "library", None)
    if lib:
        kws.extend(w for w, e in lib.all().items()
                   if e.get("status") == "approved" and w not in kws)
    return kws or ["duurzame sneakers", "vegan schoenen", "plastic free shoes"]


def _read_keywords(context) -> list[str]:
    """Backward compat: geeft keywords voor de standaard geo terug."""
    return _keywords_for_locale(
        _geo_to_locale(context.settings.get("trends_geo", "NL")), context)


class TrendsSkill(Skill):
    name = "google_trends"
    cost = "rate_limited"
    description = (
        "Haalt Google Trends-data op per geo/locale "
        "(interesse + gerelateerde zoekopdrachten). "
        "Woorden per geo komen uit het meertalige Lexicon. "
        "Fail-closed per geo×term."
    )

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
