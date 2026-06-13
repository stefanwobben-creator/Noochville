from __future__ import annotations
import os, time, random
from nooch_village.skills import Skill


def _read_keywords(context) -> list[str]:
    path = os.path.join(os.path.dirname(context.data_dir), "config", "keywords.txt")
    kws: list[str] = []
    if os.path.exists(path):
        kws = [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]

    # Goedgekeurde bibliotheekwoorden vergroten de verkenning automatisch
    lib = getattr(context, "library", None)
    if lib:
        kws.extend(w for w, e in lib.all().items() if e.get("status") == "approved" and w not in kws)

    return kws if kws else ["duurzame sneakers", "vegan schoenen", "plastic free shoes"]


class TrendsSkill(Skill):
    name = "google_trends"
    description = "Haalt echte Google Trends-data op (interesse + gerelateerde zoekopdrachten)."

    def _fetch(self, pytrends, keyword, geo, max_retries=4, base_delay=8):
        """Geport uit trends_analyst.py: exponentiele backoff bij 429."""
        retries = 0
        while retries < max_retries:
            try:
                pytrends.build_payload([keyword], cat=0, timeframe="today 12-m", geo=geo, gprop="")
                return pytrends.interest_over_time(), pytrends.related_queries()
            except Exception as e:
                if "429" in str(e):
                    delay = min(base_delay * (2 ** retries) + random.uniform(1, 3), 90)
                    time.sleep(delay)
                    retries += 1
                else:
                    raise
        raise RuntimeError(f"max retries voor '{keyword}'")

    def run(self, payload: dict, context) -> dict:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            return {"error": "pytrends niet geinstalleerd (pip install pytrends)", "keywords": {}}

        keywords = payload.get("keywords") or _read_keywords(context)
        geo = payload.get("geo", context.settings.get("trends_geo", "NL"))
        pytrends = TrendReq(hl="nl-NL", tz=60, timeout=(10, 25))

        out = {}
        for kw in keywords:
            try:
                interest_df, related = self._fetch(pytrends, kw, geo)
                latest, prev, direction = None, None, "onbekend"
                if interest_df is not None and not interest_df.empty:
                    series = interest_df[kw].tolist()
                    latest = int(series[-1])
                    prev = int(series[-2]) if len(series) > 1 else latest
                    direction = "stijgend" if latest > prev else "dalend" if latest < prev else "vlak"
                top_related = []
                if kw in related and related[kw].get("top") is not None:
                    top_related = (related[kw]["top"][["query", "value"]]
                                   .head(5).to_dict("records"))
                out[kw] = {"interest_latest": latest, "direction": direction, "top_related": top_related}
            except Exception as e:
                out[kw] = {"error": str(e)}
            time.sleep(1)  # vriendelijk voor Google
        return {"geo": geo, "keywords": out}
