"""SerpapiTrendsSkill — Google Trends via SerpApi (betrouwbaar, betaald).

pytrends wordt door Google hard geblokkeerd (429). SerpApi haalt dezelfde Trends-data
betrouwbaar op. Per keyword twee searches: TIMESERIES (interest over time) en
RELATED_QUERIES (top + rising). Output is identiek genormaliseerd aan TrendsSkill, zodat
de Field Note en _propose_related ongewijzigd blijven werken.

Zuinig: een roterend venster bevraagt maar een paar keywords per run; de cadans (wekelijks)
zit in de aanroeper. Faalt closed zonder SERPAPI_API_KEY.
"""
from __future__ import annotations
import os, json
import requests
from nooch_village.skills import Skill
from nooch_village.skills_impl.trends import _keywords_for_locale, _geo_to_locale
from nooch_village.keyword_scheduler import SeedScheduler

_ENDPOINT = "https://serpapi.com/search.json"


def _parse_timeseries(resp: dict) -> tuple[int | None, str]:
    """Haal de laatste interesse-waarde en de richting uit een TIMESERIES-respons."""
    td = (resp.get("interest_over_time") or {}).get("timeline_data") or []
    vals: list[int] = []
    for point in td:
        values = point.get("values") or []
        if values and values[0].get("extracted_value") is not None:
            try:
                vals.append(int(values[0]["extracted_value"]))
            except (TypeError, ValueError):
                pass
    if not vals:
        return None, "vlak"
    latest = vals[-1]
    prev = vals[-2] if len(vals) > 1 else latest
    direction = "stijgend" if latest > prev else "dalend" if latest < prev else "vlak"
    return latest, direction


def _series_from_timeseries(resp: dict) -> list[int]:
    """De volledige interesse-reeks (chronologisch) uit een TIMESERIES-respons."""
    td = (resp.get("interest_over_time") or {}).get("timeline_data") or []
    vals: list[int] = []
    for point in td:
        values = point.get("values") or []
        if values and values[0].get("extracted_value") is not None:
            try:
                vals.append(int(values[0]["extracted_value"]))
            except (TypeError, ValueError):
                pass
    return vals


def _parse_related(resp: dict) -> tuple[list[dict], list[dict]]:
    """Haal top- en rising-gerelateerde queries uit een RELATED_QUERIES-respons."""
    rq = resp.get("related_queries") or {}
    top = [
        {"query": r["query"], "value": int(r.get("extracted_value") or 0)}
        for r in (rq.get("top") or [])[:5] if r.get("query")
    ]
    rising = []
    for r in (rq.get("rising") or [])[:5]:
        if not r.get("query"):
            continue
        is_breakout = str(r.get("value", "")).strip().lower() == "breakout"
        rising.append({
            "query":    r["query"],
            "value":    int(r.get("extracted_value") or 0),
            "breakout": is_breakout,
        })
    return top, rising


class SerpapiTrendsSkill(Skill):
    name = "serpapi_trends"
    needs_secret = True
    cost = "credits"
    required_env = ("SERPAPI_API_KEY",)
    description = (
        "Google Trends via SerpApi (betrouwbaar, betaald): interest-over-time + "
        "top/rising related queries per keyword. Roterend venster, fail-closed zonder key."
    )

    def _get(self, params: dict) -> dict:
        """Eén SerpApi-search. Geïsoleerd zodat tests dit kunnen vervangen."""
        r = requests.get(_ENDPOINT, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def series(self, term: str, context, *, geo: str | None = None,
               timeframe: str = "today 5-y") -> list[int]:
        """Eén TIMESERIES-call: de meerjarige interesse-reeks voor één term (voor trend-toestand).
        Faalt closed: lege lijst bij geen key of API-fout."""
        import os as _os
        key = (getattr(context, "settings", {}) or {}).get("serpapi_api_key") \
            or _os.environ.get("SERPAPI_API_KEY")
        if not key or not term:
            return []
        geo = geo or (getattr(context, "settings", {}) or {}).get("trends_geo", "NL")
        try:
            resp = self._get({"engine": "google_trends", "q": term, "geo": geo,
                              "date": timeframe, "data_type": "TIMESERIES", "api_key": key})
            return _series_from_timeseries(resp)
        except Exception:
            return []

    def _scheduler(self, context) -> SeedScheduler:
        budget = int(context.settings.get("serpapi_keywords_per_run", "5"))
        max_int = int(context.settings.get("trends_max_interval", "8"))
        return SeedScheduler(os.path.join(context.data_dir, "serpapi_seed_scheduler.json"),
                             budget=budget, max_interval=max_int)

    @staticmethod
    def _produced_new(top_related, rising_related, lib) -> bool:
        """Leverde dit zaadwoord minstens één NIEUWE, schoen-relevante gerelateerde term op?
        Off-domein ruis (regenerative medicine, vegan food, ...) telt NIET als productief: die
        sneuvelt later toch in het domeinfilter, dus een breed ruis-zaadwoord mag wegzakken naar
        een langer interval. Zonder bibliotheek: elke schoen-relevante term telt als 'nieuw'."""
        from nooch_village.intent import _is_schoen_domein
        queries = []
        for r in (top_related or []) + (rising_related or []):
            queries.append(r.get("query") if isinstance(r, dict) else r)
        on_domain = [q for q in queries if q and _is_schoen_domein(q.lower())]
        if not on_domain:
            return False
        if lib is None:
            return True
        return any(lib.status(q) is None for q in on_domain)

    def run(self, payload: dict, context) -> dict:
        key = context.settings.get("SERPAPI_API_KEY") or os.getenv("SERPAPI_API_KEY")
        if not key:
            raise RuntimeError("SERPAPI_API_KEY ontbreekt in .env — skill faalt bewust closed")

        geos_raw = payload.get("geos") or [context.settings.get("trends_geo", "NL")]
        if isinstance(geos_raw, str):
            geos_raw = [geos_raw]
        geos = list(dict.fromkeys(geos_raw))
        date = payload.get("date") or payload.get("timeframe", "today 12-m")
        first_geo = geos[0] if geos else ""

        rows: list[dict] = []
        legacy: dict = {}
        lib = getattr(context, "library", None)

        # Spaced-repetition-scheduler bepaalt welke zaadwoorden deze run aan de beurt zijn
        # (nieuw/productief vaak, uitgekauwd zelden). Bij een vaste keywords-payload niet.
        sched = None
        if not payload.get("keywords"):
            sched = self._scheduler(context)
            sched.tick()

        for geo in geos:
            locale = _geo_to_locale(geo)
            if payload.get("keywords"):
                keywords = payload["keywords"]
            else:
                keywords = sched.select(_keywords_for_locale(locale, context))

            for kw in keywords:
                base = {"engine": "google_trends", "q": kw, "geo": geo,
                        "date": date, "api_key": key}
                try:
                    ts_resp = self._get({**base, "data_type": "TIMESERIES"})
                    rq_resp = self._get({**base, "data_type": "RELATED_QUERIES"})
                    latest, direction = _parse_timeseries(ts_resp)
                    top_related, rising_related = _parse_related(rq_resp)

                    if latest is None:
                        row = {"term": kw, "locale": locale, "geo": geo,
                               "no_data": True, "reason": "geen interesse-data"}
                        if geo == first_geo:
                            legacy[kw] = {"no_data": True}
                        if sched is not None:
                            sched.record(kw, False)         # geen data → interval verlengen
                    else:
                        row = {
                            "term": kw, "locale": locale, "geo": geo,
                            "interest_latest": latest, "direction": direction,
                            "top_related": top_related, "rising_related": rising_related,
                        }
                        if geo == first_geo:
                            legacy[kw] = {
                                "interest_latest": latest, "direction": direction,
                                "top_related": top_related, "rising_related": rising_related,
                            }
                        if sched is not None:
                            sched.record(kw, self._produced_new(top_related, rising_related, lib))
                    rows.append(row)
                except Exception as e:
                    rows.append({"term": kw, "locale": locale, "geo": geo,
                                 "no_data": True, "reason": str(e)})
                    if geo == first_geo:
                        legacy[kw] = {"error": str(e)}
                    # Fout = transiënt, niet 'saai': geen record → volgende run opnieuw proberen.

        if sched is not None:
            sched.save()
        return {"rows": rows, "keywords": legacy, "geos": geos,
                "geo": first_geo, "source": "serpapi"}
