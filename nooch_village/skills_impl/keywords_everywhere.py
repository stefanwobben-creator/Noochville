from __future__ import annotations
import logging, os
import requests
from nooch_village.skills import Skill

log = logging.getLogger(__name__)

_VALID_DATA_SOURCES = {"gkp", "cli"}


class KeywordsEverywhereSkill(Skill):
    name = "keywords_everywhere"
    needs_secret = True
    cost = "credits"
    side_effect_free = True
    description = "Haalt echte search volume, CPC, competitie en 12-maands trend per keyword uit de Keywords Everywhere API (geen mock)."

    def run(self, payload: dict, context) -> dict:
        """Haal keyword-data op uit de Keywords Everywhere API.

        Input (payload):
          kw          list[str]  — verplicht, 1–100 termen; leeg → ValueError, >100 → ValueError
          country     str        — default "nl"
          currency    str        — default "eur"
          data_source str        — "gkp" (default) of "cli"; andere waarde → ValueError

        Output:
          source            str        — "keywords_everywhere"
          country           str
          currency          str
          data_source       str
          credits_consumed  int
          credits_remaining int
          keywords          list[dict] — keyword, vol (int), cpc (float), competition (float), trend (list)
        """
        key = context.settings.get("KEYWORDS_EVERYWHERE_API_KEY") or os.getenv("KEYWORDS_EVERYWHERE_API_KEY")
        if not key:
            raise RuntimeError("KEYWORDS_EVERYWHERE_API_KEY ontbreekt in .env — skill faalt bewust closed")

        kw: list[str] = payload.get("kw", [])
        if not kw:
            raise ValueError("payload['kw'] mag niet leeg zijn")
        if len(kw) > 100:
            raise ValueError(f"payload['kw'] bevat {len(kw)} termen — max 100 per request (caller batcht zelf)")

        country     = payload.get("country", "nl")
        currency    = payload.get("currency", "eur")
        data_source = payload.get("data_source", "gkp")
        if data_source not in _VALID_DATA_SOURCES:
            raise ValueError(f"Onbekende data_source '{data_source}' — kies 'gkp' of 'cli'")

        data = [("dataSource", data_source), ("country", country), ("currency", currency)]
        for term in kw:
            data.append(("kw[]", term))

        r = requests.post(
            "https://api.keywordseverywhere.com/v1/get_keyword_data",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            data=data,
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()

        keywords = [
            {
                "keyword":     item["keyword"],
                "vol":         int(item.get("vol") or 0),
                "cpc":         float((item.get("cpc") or {}).get("value") or 0),
                "competition": float(item.get("competition") or 0),
                "trend":       item.get("trend", []),
            }
            for item in raw.get("data", [])
        ]

        return {
            "source":             "keywords_everywhere",
            "country":            country,
            "currency":           currency,
            "data_source":        data_source,
            "credits_consumed":   int(raw.get("credits_consumed", 0)),
            "credits_remaining":  int(raw.get("credits", 0)),
            "keywords":           keywords,
        }
