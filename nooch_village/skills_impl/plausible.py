from __future__ import annotations
import logging, os, requests
from nooch_village.skills import Skill

log = logging.getLogger(__name__)

_METRICS = ["visitors", "pageviews", "visit_duration"]

_BREAKDOWNS = [
    ("event:page",       "top_pages"),
    ("visit:source",     "sources"),
    ("visit:country",    "countries"),
    ("visit:utm_source", "utm_sources"),
]


class PlausibleSkill(Skill):
    name = "plausible_stats"
    cost = "free"
    needs_secret = True
    description = "Haalt echte bezoekersdata uit de Plausible Stats API (geen mock)."

    def available_metrics(self) -> list[str]:
        """Menukaart: de metrics die deze skill kan leveren. Geen API-call nodig."""
        return list(_METRICS)

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

        return out

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
