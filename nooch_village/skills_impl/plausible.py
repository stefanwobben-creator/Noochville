from __future__ import annotations
import os, requests
from nooch_village.skills import Skill


class PlausibleSkill(Skill):
    name = "plausible_stats"
    needs_secret = True
    description = "Haalt echte bezoekersdata uit de Plausible Stats API (geen mock)."

    def run(self, payload: dict, context) -> dict:
        key = context.settings.get("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_API_KEY")
        site = context.settings.get("PLAUSIBLE_SITE_ID") or os.getenv("PLAUSIBLE_SITE_ID")
        if not key or not site:
            raise RuntimeError("PLAUSIBLE_API_KEY/PLAUSIBLE_SITE_ID ontbreekt in .env -> skill faalt bewust closed")
        r = requests.get(
            "https://plausible.io/api/v1/stats/aggregate",
            headers={"Authorization": f"Bearer {key}"},
            params={"site_id": site, "period": payload.get("period", "7d"),
                    "metrics": "visitors,pageviews"},
            timeout=10)
        r.raise_for_status()
        return {"site": site, "period": payload.get("period", "7d"),
                "results": r.json().get("results", {})}
