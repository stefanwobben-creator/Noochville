"""AlphaVantageIndexSkill — dagelijkse slotkoers van beursindices via Alpha Vantage TIME_SERIES_DAILY.

Vervangt StooqIndexSkill (Stooq zat achter een JS-challenge). UITSLUITEND vastlegging (geen KPI/analyse).

LET OP — ETF-proxy: Alpha Vantage dekt de ruwe indices (^GSPC/SPX/^AEX) NIET, alleen de tracking-ETF's.
Config koppelt daarom `spx→SPY` (S&P 500-ETF, USD) en `aex→IAEX.AMS` (iShares AEX UCITS ETF, EUR). De
vastgelegde slotkoers is de ETF-koers, die de index volgt maar niet het index-niveau zelf is. Dit staat
in de meta (`instrument`) en is een bewuste afwijking van "de index".

Regels: strikte JSON-validatie (`Time Series (Daily)` aanwezig, numerieke close), exacte-dag-keying (geen
rij voor die dag → None/gat), append-only, fail-closed. Alpha Vantage stopt fouten/limieten in de sleutels
`Note`/`Information`/`Error Message` → die tellen als fout (None). Symbolen + source_version uit de config.
API-key uit ALPHAVANTAGE_API_KEY (nooit in de meta/store).
"""
from __future__ import annotations
import datetime
import logging
import os
import time
import urllib.parse

import requests

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_ENDPOINT = "https://www.alphavantage.co/query"
_SPACING_SECONDS = 13.0        # gratis tier: 5 requests/minuut → per symbool spatiëren
_AV_ERROR_KEYS = ("Note", "Information", "Error Message")


class AlphaVantageIndexSkill(DataSourceSkill):
    name = "alphavantage_index"
    SOURCE = "alphavantage"
    cost = "rate_limited"      # gratis: 25/dag, 5/min
    kind = "flux"
    DEFAULT_FREQUENCY = "daily"
    required_env = ("ALPHAVANTAGE_API_KEY",)
    description = "Dagelijkse slotkoers van index-tracking-ETF's via Alpha Vantage TIME_SERIES_DAILY (strikt JSON)."

    def _symbols(self, context) -> dict:
        """{veld: symbool} uit `alphavantage_symbols='spx:SPY,aex:IAEX.AMS'`. Leeg → niets te doen."""
        raw = (getattr(context, "settings", {}) or {}).get("alphavantage_symbols", "") or ""
        out = {}
        for part in raw.split(","):
            if ":" in part:
                field, sym = part.split(":", 1)
                if field.strip() and sym.strip():
                    out[field.strip()] = sym.strip()
        return out

    def _key(self, context) -> str:
        return ((getattr(context, "settings", {}) or {}).get("ALPHAVANTAGE_API_KEY")
                or os.getenv("ALPHAVANTAGE_API_KEY") or "")

    def _source_version(self, context) -> int:
        try:
            return int((getattr(context, "settings", {}) or {}).get("alphavantage_source_version", "1"))
        except (TypeError, ValueError):
            return 1

    def available_metrics(self, context=None) -> list[str]:
        return list(self._symbols(context).keys()) if context is not None else []

    def is_configured(self, context) -> bool:
        return bool(self._key(context)) and bool(self._symbols(context))

    def _endpoint(self, symbol: str) -> str:
        """Endpoint-URL voor de meta — ZONDER apikey (nooit de key in de store lekken)."""
        q = urllib.parse.urlencode({"function": "TIME_SERIES_DAILY", "symbol": symbol})
        return f"{_ENDPOINT}?{q}"

    def _get(self, symbol: str, key: str) -> dict:
        r = requests.get(_ENDPOINT, params={"function": "TIME_SERIES_DAILY", "symbol": symbol,
                                             "apikey": key}, timeout=25)
        r.raise_for_status()
        return r.json()

    def _close_for(self, symbol: str, datum: str, key: str, *, _fetch=None) -> float | None:
        """Slotkoers voor EXACT `datum`, strikt geparsed. None bij fetch-fout, niet-JSON, AV-fout/limiet
        (Note/Information/Error Message), ontbrekende dagreeks, geen rij voor die dag, of niet-numerieke
        close (geen mock, geen schatting)."""
        try:
            data = _fetch(symbol) if _fetch else self._get(symbol, key)
        except Exception as exc:
            log.warning("AlphaVantage fetch faalde (%s): %s", symbol, exc)
            return None
        if not isinstance(data, dict):
            return None
        for k in _AV_ERROR_KEYS:
            if k in data:                                  # rate-limit/fout → fail-closed
                log.warning("AlphaVantage %s — %s: %s", symbol, k, str(data[k])[:100])
                return None
        series = data.get("Time Series (Daily)")
        if not isinstance(series, dict):
            log.warning("AlphaVantage onverwachte structuur voor %s (geen dagreeks)", symbol)
            return None
        row = series.get(datum)
        if not isinstance(row, dict) or "4. close" not in row:
            return None                                    # geen rij voor die dag → gat
        try:
            return float(row["4. close"])
        except (TypeError, ValueError):
            log.warning("AlphaVantage niet-numerieke close voor %s op %s", symbol, datum)
            return None

    def daily_values(self, context, datum: str, *, _sleep=None) -> dict:
        symbols = self._symbols(context)
        out = {field: None for field in symbols}
        key = self._key(context)
        if not key:
            return out
        sleep = _sleep if _sleep is not None else time.sleep
        for i, (field, symbol) in enumerate(symbols.items()):
            if i:
                sleep(_SPACING_SECONDS)                     # 5/min-limiet
            out[field] = self._close_for(symbol, datum, key)
        return out

    def observation_meta(self, context, datum: str, field: str) -> dict:
        symbol = self._symbols(context).get(field, "")
        return {"source_version": self._source_version(context),
                "endpoint": self._endpoint(symbol), "symbol": symbol,
                "instrument": "index-tracking-ETF"}        # koers van de ETF, niet het index-niveau zelf

    def run(self, payload: dict, context) -> dict:
        datum = payload.get("datum") or (
            datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
        return {"datum": datum, "values": self.daily_values(context, datum)}
