from __future__ import annotations
import logging, os, requests
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_METRICS = ["visitors", "pageviews", "visit_duration", "bounce_rate"]
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
    cost = "free"
    needs_secret = True
    required_env = ("PLAUSIBLE_API_KEY", "PLAUSIBLE_SITE_ID")
    DIMENSION = "country"        # scope 4: reeksen per land via de native visit:country-breakdown
    description = "Haalt echte bezoekersdata uit de Plausible Stats API (geen mock)."

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
            log.warning("Plausible daily_values faalde (%s): %s", datum, exc)
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
            log.warning("Plausible daily_dimension_values faalde (%s): %s", datum, exc)
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

    def run(self, payload: dict, context) -> dict:
        key = context.settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = context.settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not key or not site:
            raise RuntimeError("PLAUSIBLE_API_KEY/PLAUSIBLE_SITE_ID ontbreekt in .env -> skill faalt bewust closed")

        period = payload.get("period", "7d")
        hdrs   = {"Authorization": f"Bearer {key}"}

        # Aggregate — kritiek pad, mag falen (raise_for_status)
        r = requests.get(
            "https://plausible.io/api/v1/stats/aggregate",
            headers=hdrs,
            params={"site_id": site, "period": period, "metrics": ",".join(_METRICS)},
            timeout=10)
        r.raise_for_status()
        out = {"site": site, "period": period, "results": r.json().get("results", {})}

        # Breakdowns — verrijking, nooit kritiek pad
        for prop, key_name in _BREAKDOWNS:
            out[key_name] = self._breakdown(hdrs, site, period, prop)

        # Losse dagwaarde: bezoekers van de VORIGE volledige dag (period=day + date), naast de
        # 7d-call. Één schoon datapunt per dag voor de observatie-store. Extra en best-effort —
        # nooit het kritieke pad (mag None zijn zonder de 7d-note te blokkeren).
        out["visitors_day"] = self._daily_visitors(hdrs, site)

        return out

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
            log.warning("Plausible dagwaarde faalde: %s", exc)
            return {"date": day, "value": None, "error": str(exc)}

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
            log.warning("Plausible breakdown '%s' faalde: %s", prop, exc)
            return []
