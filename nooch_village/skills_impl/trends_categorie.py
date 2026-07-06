"""TrendsCategorieSkill — dagelijkse Google-Trends-interesse voor een BEVROREN set categorietermen.

UITSLUITEND vastlegging (geen KPI/analyse/normalisatie). Aparte bron van de bestaande anker-ratio-
TrendsSkill (SOURCE='trends'); deze heeft SOURCE='trends_categorie'.

Bevriezing: de termenset, het timeframe en de geo komen bij runtime UITSLUITEND uit de config
(`trends_cat_terms`, `trends_cat_timeframe`, `trends_cat_geo`), nooit live uit de Library. Een wijziging
is een bewuste config-aanpassing plus ophogen van `trends_cat_source_version` — nooit stilzwijgend.

Query: alle termen SAMEN in één batch, timeframe standaard 'now 7-d'. Per term de waarde van de laatste
VOLLEDIGE dag (uur-data → dag-gemiddelde over de niet-partiële uren van die dag). 429 of ander pytrends-
falen → fail-closed (None), max 1 retry met backoff, geen retry-storm.
"""
from __future__ import annotations
import datetime
import logging
import re
import time

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_TIMEFRAME_DEFAULT = "now 7-d"


def _sanitize_field(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", term.strip().lower()).strip("_")


class TrendsCategorieSkill(DataSourceSkill):
    name = "trends_categorie"
    SOURCE = "trends_categorie"
    cost = "rate_limited"
    kind = "flux"
    DEFAULT_FREQUENCY = "daily"
    required_env = ()
    description = "Dagelijkse Google-Trends-interesse voor een bevroren set categorietermen (geen mock)."

    def _terms(self, context) -> list[str]:
        raw = (getattr(context, "settings", {}) or {}).get("trends_cat_terms", "") or ""
        return [t.strip() for t in raw.split(",") if t.strip()]

    def _timeframe(self, context) -> str:
        return ((getattr(context, "settings", {}) or {}).get("trends_cat_timeframe") or _TIMEFRAME_DEFAULT).strip()

    def _geo(self, context) -> str:
        return ((getattr(context, "settings", {}) or {}).get("trends_cat_geo") or "").strip()

    def _source_version(self, context) -> int:
        try:
            return int((getattr(context, "settings", {}) or {}).get("trends_cat_source_version", "1"))
        except (TypeError, ValueError):
            return 1

    def available_metrics(self, context=None) -> list[str]:
        return [_sanitize_field(t) for t in self._terms(context)] if context is not None else []

    def is_configured(self, context) -> bool:
        return bool(self._terms(context))                 # bevroren termen aanwezig?

    def _fetch(self, terms: list[str], timeframe: str, geo: str):
        """Eén batch-query naar pytrends → interest_over_time-DataFrame. Max 1 retry met backoff; daarna
        stoppen (geen retry-storm). Faalt closed (raise) → de caller zet alles op None."""
        from pytrends.request import TrendReq
        last_exc = None
        for attempt in range(2):                          # 1 poging + 1 retry
            try:
                py = TrendReq(hl="en-US", tz=0, timeout=(10, 25),
                              requests_args={"headers": {"User-Agent": _USER_AGENT}})
                py.build_payload(terms, cat=0, timeframe=timeframe, geo=geo, gprop="")
                return py.interest_over_time()
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(2.0)                        # één backoff, dan stoppen
        raise last_exc

    def daily_values(self, context, datum: str, *, _fetch=None) -> dict:
        terms = self._terms(context)
        out = {_sanitize_field(t): None for t in terms}
        if not terms:
            return out
        try:
            df = (_fetch or self._fetch)(terms, self._timeframe(context), self._geo(context))
        except Exception as exc:
            log.warning("Trends-categorie fetch faalde: %s", exc)
            return out                                    # alles None (fail-closed, geen retry-storm)
        if df is None or getattr(df, "empty", True):
            return out
        try:
            target = datetime.date.fromisoformat(datum)
            partial = df["isPartial"].astype(str).str.lower() == "true" if "isPartial" in df else None
            day_mask = [d.date() == target for d in df.index]
            for term in terms:
                if term not in df.columns:
                    continue
                sel = [i for i, m in enumerate(day_mask) if m]
                if not sel:
                    continue                              # geen data voor die dag → gat
                if partial is not None and any(bool(partial.iloc[i]) for i in sel):
                    continue                              # dag nog niet volledig → geen waarde
                vals = [float(df[term].iloc[i]) for i in sel]
                out[_sanitize_field(term)] = round(sum(vals) / len(vals), 2)
        except Exception as exc:
            log.warning("Trends-categorie parse faalde (%s): %s", datum, exc)
            return {_sanitize_field(t): None for t in terms}
        return out

    def observation_meta(self, context, datum: str, field: str) -> dict:
        return {"source_version": self._source_version(context),
                "endpoint": "pytrends interest_over_time",
                "timeframe": self._timeframe(context),
                "geo": self._geo(context) or "worldwide",
                "termenset": self._terms(context)}        # waardes zijn relatief binnen venster + set

    def run(self, payload: dict, context) -> dict:
        datum = payload.get("datum") or (
            datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
        return {"datum": datum, "values": self.daily_values(context, datum)}
