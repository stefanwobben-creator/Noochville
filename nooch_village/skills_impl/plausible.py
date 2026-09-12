from __future__ import annotations
import logging, os, requests
from nooch_village.skills import DataSourceSkill
from nooch_village.observations import dim_slug
from nooch_village.sleutelmasker import http_fout, masker

log = logging.getLogger(__name__)

_METRICS = ["visitors", "pageviews", "visit_duration", "bounce_rate"]
#: De perioden die `run` aanneemt — de Plausible Stats API v1 kent er meer (day, 6mo, custom), maar
#: die vragen een datum of geven de planner een keuze die hij niet nodig heeft. Een verzonnen periode
#: ("last 30 days") werd live een HTTP 400 op de wall, poging 3 (skill-review 12-09-2026); nu strandt
#: hij bij het plannen (`validate_payload`) en accepteert `_period` de voor de hand liggende aliassen.
PERIODS = ("7d", "30d", "month", "12mo")
_PERIOD_ALIAS = {
    "7d": "7d", "7days": "7d", "last7days": "7d", "week": "7d", "1w": "7d", "7": "7d",
    "30d": "30d", "30days": "30d", "last30days": "30d", "30": "30d", "1m": "30d",
    "month": "month", "thismonth": "month",
    "12mo": "12mo", "12months": "12mo", "12m": "12mo", "year": "12mo", "1y": "12mo", "lastyear": "12mo",
}
_PERIOD_LABEL = {"7d": "the last 7 days", "30d": "the last 30 days", "month": "this month",
                 "12mo": "the last 12 months"}
# page_path-dimensie: een pagina komt in de meetset zodra hij op één dag ≥ deze drempel bezoeken haalt.
_PAGE_THRESHOLD = 3


def _page_slug(page: str) -> str:
    """Page-path → veilige dimensie-slug; de homepage '/' (lege slug) → 'home'."""
    return dim_slug(page) or "home"
# Live-verzameling van bounce_rate start hier; er is GEEN historie vóór deze datum (de historische bounce
# komt via de aparte sweep, ronde 1b). De reeks-start staat als meta op elke bounce-observatie.
_BOUNCE_REEKS_START = "2026-07-07"

_BREAKDOWNS = [
    ("event:page",       "top_pages"),
    ("visit:source",     "sources"),
    ("visit:country",    "countries"),
    ("visit:utm_source", "utm_sources"),
]


class PlausibleSkill(DataSourceSkill):
    name = "plausible_stats"
    SOURCE = "plausible"
    CATALOG_LABEL = "Plausible (web-analytics)"
    cost = "free"
    needs_secret = True
    required_env = ("PLAUSIBLE_API_KEY", "PLAUSIBLE_SITE_ID")
    DIMENSION = "country"        # scope 4: reeksen per land via de native visit:country-breakdown
    description = (
        "Real visitor numbers for nooch.earth from the Plausible Stats API: unique visitors, pageviews, "
        "visit duration and bounce rate over a period, plus the top-10 pages, sources, countries and "
        "UTM sources and yesterday's visitor count. Returns `rows` (headline figures first, then the "
        "breakdowns) and a one-line `text`. Needs PLAUSIBLE_API_KEY and PLAUSIBLE_SITE_ID."
    )
    input_schema = ("period: '7d' | '30d' | 'month' | '12mo' (optional, default '7d'; aliases such as "
                    "'week', '30 days', 'year' are accepted)")
    output_schema = ("site, period, text, rows[{period, metric, waarde, text} for the headline figures and "
                     "visitors_day, then {period, metric: 'visitors', dimension, name, waarde, text} per "
                     "breakdown row], results{visitors|pageviews|visit_duration|bounce_rate: {value}}, "
                     "top_pages[], sources[], countries[], utm_sources[], visitors_day{date, value} | error")

    def available_metrics(self, context=None) -> list[str]:
        """Menukaart: de metrics die deze skill kan leveren. Geen API-call nodig."""
        return list(_METRICS)

    def daily_values(self, context, datum: str) -> dict:
        """Dagwaarde per gedeclareerd veld (visitors/pageviews/visit_duration) voor `datum`, in één
        aggregate-call. Fail-closed per veld: None bij ontbrekende creds of API-fout (geen mock)."""
        out = {m: None for m in _METRICS}
        key = context.settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = context.settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not key or not site:
            return out
        try:
            r = requests.get(
                "https://plausible.io/api/v1/stats/aggregate",
                headers={"Authorization": f"Bearer {key}"},
                params={"site_id": site, "period": "day", "date": datum, "metrics": ",".join(_METRICS)},
                timeout=10)
            r.raise_for_status()
            res = r.json().get("results", {})
            for m in _METRICS:
                out[m] = (res.get(m) or {}).get("value")
        except Exception as exc:
            log.warning("Plausible daily_values faalde (%s): %s", datum, masker(exc))
        return out

    def observation_meta(self, context, datum: str, field: str) -> dict:
        # bounce_rate is een nieuwe reeks vanaf nu: de reeks-start markeert dat er vóór deze datum geen
        # bounce-data is (geen backfill in deze ronde). visitors/pageviews/visit_duration: geen meta (ongewijzigd).
        if field == "bounce_rate":
            return {"reeks_start": _BOUNCE_REEKS_START}
        return {}

    def daily_dimension_values(self, context, datum: str, countries, *, _get=None) -> dict:
        """Per land de dagwaarden (visitors/pageviews/visit_duration/bounce_rate) voor `datum`, via ÉÉN
        breakdown-call (property=visit:country). `countries` = de gecureerde config-selectie (ISO-codes).
        Exacte match op de landcode; een land dat die dag niet in de respons zit → géén entry → gat.
        Fail-closed → lege dict. `_get(params)` injecteerbaar zodat de contract-test datum + property kan
        bewijzen."""
        want = {c.upper() for c in (countries or [])}
        out = {}
        key = context.settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = context.settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not want or not key or not site:
            return out
        params = {"site_id": site, "period": "day", "date": datum, "property": "visit:country",
                  "metrics": ",".join(_METRICS), "limit": 1000}
        if _get is None:
            def _get(p):
                r = requests.get("https://plausible.io/api/v1/stats/breakdown",
                                 headers={"Authorization": f"Bearer {key}"}, params=p, timeout=10)
                r.raise_for_status()
                return r.json().get("results", [])
        try:
            rows = _get(params)
        except Exception as exc:
            log.warning("Plausible daily_dimension_values faalde (%s): %s", datum, masker(exc))
            return out
        for row in rows:
            c = str(row.get("country", "")).upper()
            if c not in want:
                continue                        # land hoort niet bij de gecureerde selectie
            for field in _METRICS:
                v = row.get(field)
                if v is not None:
                    out[(field, c)] = v
        return out

    def collect_extra_series(self, context, today, obs, *, _get=None):
        """page_path-dimensie (drempel-gebaseerd, persistent), ADDITIEF naast de country-dimensie + totalen.
        Een pagina komt in de meetset zodra hij op één dag ≥ _PAGE_THRESHOLD bezoeken haalt; **daarna** wordt
        zijn VOLLEDIGE dagreeks vastgelegd (ook lagere dagen / 0 = echte waarde, geen gat). Opslag = per
        pagina (`plausible_page_visitors_day::<slug>`, meta `page_path`); een top-10 is een AFGELEIDE view,
        niet de opslag (stabiel/terugleesbaar per pagina). De reeds gekwalificeerde set = de pagina's die al
        een reeks in de store hebben; die worden altijd doorgemeten, ook onder de drempel.
        Fail-closed: geen creds / API-fout → geen write, geen interpolatie. `_get(params)` injecteerbaar."""
        from datetime import timedelta
        datum = (today - timedelta(days=1)).isoformat()           # laatst-complete dag (lag 0)
        key = context.settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = context.settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not key or not site:
            return []
        params = {"site_id": site, "period": "day", "date": datum, "property": "event:page",
                  "metrics": "visitors", "limit": 1000}
        if _get is None:
            def _get(p):
                r = requests.get("https://plausible.io/api/v1/stats/breakdown",
                                 headers={"Authorization": f"Bearer {key}"}, params=p, timeout=10)
                r.raise_for_status()
                return r.json().get("results", [])
        try:
            rows = _get(params)
        except Exception as exc:
            log.warning("Plausible page_path-breakdown faalde (%s): %s", datum, masker(exc))
            return []
        today_pages = {}
        for row in rows:
            p, v = row.get("page"), row.get("visitors")
            if p is not None and v is not None:
                today_pages[p] = int(v)
        already = set(obs.dimensioned_series("plausible_page_visitors_day", bron="plausible").keys())
        collect = already | {p for p, v in today_pages.items() if v >= _PAGE_THRESHOLD}
        written = []
        for page in sorted(collect):
            v = today_pages.get(page, 0)                          # niet in respons = 0 bezoeken (echte waarde)
            metric = f"plausible_page_visitors_day::{_page_slug(page)}"
            if obs.record_daily("plausible", metric, v, bron="plausible", datum=datum,
                                meta={"dimension": "page_path", "value": page}):
                written.append(("plausible", f"page_visitors::{_page_slug(page)}", datum))
        return written

    def backfill_page_paths(self, context, obs, start_iso, end_iso, pages, *, _get=None):
        """Eenmalige backfill van de dagreeks per gekwalificeerde pagina over [start, end], via Plausible
        timeseries met filter `event:page==<page>`. Elk punt draagt meta `backfill: true` zodat het later
        herkenbaar is als inhaal. Idempotent (record_daily dedupt op datum); gaten blijven gaten (Plausible
        geeft 0 voor lege dagen = echte waarde, geen interpolatie). Fail-closed per pagina."""
        key = context.settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = context.settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not key or not site or not pages:
            return []
        if _get is None:
            def _get(p):
                r = requests.get("https://plausible.io/api/v1/stats/timeseries",
                                 headers={"Authorization": f"Bearer {key}"}, params=p, timeout=15)
                r.raise_for_status()
                return r.json().get("results", [])
        written = []
        for page in pages:
            params = {"site_id": site, "period": "custom", "date": f"{start_iso},{end_iso}",
                      "metrics": "visitors", "interval": "date", "filters": f"event:page=={page}"}
            try:
                rows = _get(params)
            except Exception as exc:
                log.warning("Plausible page-backfill '%s' faalde: %s", page, masker(exc))
                continue
            metric = f"plausible_page_visitors_day::{_page_slug(page)}"
            for row in rows:
                d, v = row.get("date"), row.get("visitors")
                if d is None or v is None:
                    continue
                if obs.record_daily("plausible", metric, int(v), bron="plausible", datum=d,
                                    meta={"dimension": "page_path", "value": page, "backfill": True}):
                    written.append(("plausible", f"page_visitors::{_page_slug(page)}", d))
        return written

    @staticmethod
    def _period(raw) -> str:
        """De gevraagde periode genormaliseerd naar een Plausible-periode, of de rauwe tekst als er
        geen alias bij past (dan zegt validate_payload/run wat er mis is). Leeg = 7d."""
        t = "".join(str(raw or "").lower().split())
        if not t:
            return "7d"
        return _PERIOD_ALIAS.get(t, str(raw).strip())

    def validate_payload(self, payload: dict, context) -> list:
        """Een verzonnen periode strandt bij het PLANNEN, niet als '400 Bad Request, poging 3' op de
        wall. Aliassen (week, 30 days, year) worden stil aanvaard; alleen wat nergens op past faalt."""
        raw = (payload or {}).get("period")
        if raw in (None, ""):
            return []
        if self._period(raw) not in PERIODS:
            return [f"'period' {str(raw)!r} is not a Plausible period; choose one of {', '.join(PERIODS)}"]
        return []

    def run(self, payload: dict, context) -> dict:
        payload = payload or {}
        settings = getattr(context, "settings", None) or {}
        key = settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not key or not site:
            # Geen sleutel is ALTIJD een fout (nooit no_data, nooit een lege lijst): de bron is niet
            # geraadpleegd. Als dict en niet als exceptie, zodat de drie uitkomsten hier één vorm hebben.
            return {"error": "PLAUSIBLE_API_KEY/PLAUSIBLE_SITE_ID missing in .env -> skill fails closed"}

        period = self._period(payload.get("period"))
        if period not in PERIODS:
            return {"error": f"unknown period {payload.get('period')!r}; choose one of {', '.join(PERIODS)}"}
        hdrs   = {"Authorization": f"Bearer {key}"}

        # Aggregate — het kritieke pad. Een HTTP-fout is een `error` (de bron faalde), gebouwd ZONDER
        # de URL: die draagt de site-id en bij andere API's de sleutel (sleutelmasker.http_fout).
        try:
            r = requests.get(
                "https://plausible.io/api/v1/stats/aggregate",
                headers=hdrs,
                params={"site_id": site, "period": period, "metrics": ",".join(_METRICS)},
                timeout=10)
            r.raise_for_status()
        except requests.HTTPError:
            return {"error": http_fout(r, "Plausible aggregate")}
        except Exception as exc:                          # noqa: BLE001 — netwerk, time-out, DNS
            return {"error": f"Plausible aggregate unreachable: {masker(exc)}"}
        try:
            results = r.json().get("results", {}) or {}
        except ValueError:
            return {"error": "Plausible aggregate returned no JSON"}
        out = {"site": site, "period": period, "results": results}

        # Breakdowns — verrijking, nooit kritiek pad
        for prop, key_name in _BREAKDOWNS:
            out[key_name] = self._breakdown(hdrs, site, period, prop)

        # Losse dagwaarde: bezoekers van de VORIGE volledige dag (period=day + date), naast de
        # 7d-call. Één schoon datapunt per dag voor de observatie-store. Extra en best-effort —
        # nooit het kritieke pad (mag None zijn zonder de 7d-note te blokkeren).
        out["visitors_day"] = self._daily_visitors(hdrs, site)

        # DE KOPCIJFERS EERST (skill-review 12-09-2026). De uitvoerlaag laat de grootste lijst winnen,
        # en dat was `top_pages`: de wall-note opende met tien paginapaden en het verslag rendeerde
        # ze als JSON — bezoekers en periode stonden nergens. `rows` is nu de grootste lijst (kop-
        # cijfers + dagwaarde + alle breakdown-regels) en `text` de leeswijzer; de bestaande sleutels
        # blijven staan voor roles.py (_extract_pulse_metrics, _surface_locale) en field_note.
        out["rows"] = self._rows(period, results, out["visitors_day"], out)
        out["text"] = self._tekst(period, results, out["visitors_day"], out)
        return out

    @staticmethod
    def _rows(period: str, results: dict, visitors_day: dict, out: dict) -> list:
        label = _PERIOD_LABEL.get(period, period)
        zinnen = {
            "visitors": lambda v: f"{v} unique visitors in {label}",
            "pageviews": lambda v: f"{v} pageviews in {label}",
            "visit_duration": lambda v: f"average visit of {v} s in {label}",
            "bounce_rate": lambda v: f"bounce rate {v}% in {label}",
        }
        rows = []
        for m in _METRICS:
            v = (results.get(m) or {}).get("value")
            if v is None:
                continue
            rows.append({"period": period, "metric": m, "waarde": v, "text": zinnen[m](v)})
        vd = visitors_day or {}
        if vd.get("value") is not None:
            rows.append({"period": "day", "metric": "visitors_day", "waarde": vd["value"], "date": vd.get("date", ""),
                         "text": f"{vd['value']} unique visitors on {vd.get('date', '?')} (the last complete day)"})
        # Per breakdown-regel: `name` is het titelveld (de verslag-renderer kent geen `country` of
        # `source` als titel, en `metric` zou anders elke regel 'visitors' noemen); `dimension` zegt
        # waar de naam bij hoort.
        frase = {"page": "on {}", "source": "from source {}", "country": "from {}", "utm_source": "via utm_source {}"}
        for prop, key_name in _BREAKDOWNS:
            dim = prop.split(":", 1)[-1]
            for r in out.get(key_name) or []:
                if not isinstance(r, dict) or r.get(dim) is None or r.get("visitors") is None:
                    continue
                naam = str(r[dim])
                rows.append({"period": period, "metric": "visitors", "dimension": dim, "name": naam,
                             "waarde": r["visitors"],
                             "text": f"{r['visitors']} visitors {frase[dim].format(naam)} in {label}"})
        return rows

    @staticmethod
    def _tekst(period: str, results: dict, visitors_day: dict, out: dict) -> str:
        """Eén tot drie zinnen met de kerncijfers — de leeswijzer boven de records."""
        label = _PERIOD_LABEL.get(period, period)
        w = lambda m: (results.get(m) or {}).get("value")
        delen = []
        if w("visitors") is not None:
            kop = f"{w('visitors')} unique visitors"
            if w("pageviews") is not None:
                kop += f" and {w('pageviews')} pageviews"
            kop += f" in {label}"
            extra = []
            if w("visit_duration") is not None:
                extra.append(f"avg. visit {w('visit_duration')} s")
            if w("bounce_rate") is not None:
                extra.append(f"bounce rate {w('bounce_rate')}%")
            delen.append(kop + (f" ({', '.join(extra)})" if extra else "") + ".")
        else:
            delen.append(f"Plausible returned no visitor total for {label}.")
        vd = visitors_day or {}
        if vd.get("value") is not None:
            delen.append(f"Yesterday ({vd.get('date', '?')}): {vd['value']} visitors.")
        toppen = []
        for prop, key_name, woord in (("event:page", "top_pages", "page"), ("visit:source", "sources", "source"),
                                       ("visit:country", "countries", "country")):
            dim = prop.split(":", 1)[-1]
            eerste = next((r for r in (out.get(key_name) or []) if isinstance(r, dict) and r.get(dim) is not None), None)
            if eerste is not None:
                toppen.append(f"top {woord} {eerste[dim]} ({eerste.get('visitors', '?')})")
        if toppen:
            zin = ", ".join(toppen)
            delen.append(zin[0].upper() + zin[1:] + ".")     # geen .capitalize(): dat verlaagt 'NL' tot 'nl'
        return " ".join(delen)

    def _daily_visitors(self, hdrs: dict, site: str) -> dict:
        """Bezoekers van de vorige volledige (UTC-)dag. {date, value} of {date, value:None, error}."""
        from datetime import datetime, timezone, timedelta
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        try:
            r = requests.get(
                "https://plausible.io/api/v1/stats/aggregate",
                headers=hdrs,
                params={"site_id": site, "period": "day", "date": day, "metrics": "visitors"},
                timeout=10)
            r.raise_for_status()
            value = (r.json().get("results", {}).get("visitors") or {}).get("value")
            return {"date": day, "value": value}
        except Exception as exc:
            log.warning("Plausible dagwaarde faalde: %s", masker(exc))
            return {"date": day, "value": None, "error": masker(exc)}

    def _breakdown(self, hdrs: dict, site: str, period: str, prop: str) -> list:
        try:
            r = requests.get(
                "https://plausible.io/api/v1/stats/breakdown",
                headers=hdrs,
                params={"site_id": site, "period": period,
                        "property": prop, "metrics": "visitors", "limit": 10},
                timeout=10)
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as exc:
            log.warning("Plausible breakdown '%s' faalde: %s", prop, masker(exc))
            return []
