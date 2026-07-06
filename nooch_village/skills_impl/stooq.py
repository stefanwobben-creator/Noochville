"""StooqIndexSkill — dagelijkse slotkoers van beursindices via het per-symbool CSV-endpoint van Stooq.

UITSLUITEND vastlegging voor latere analyse: geen KPI, geen tegel, geen normalisatie. Per geconfigureerd
symbool één observatie per dag: de slotkoers van exact de gevraagde kalenderdag (de collector vraagt de
laatste volledige dag). Geen rij voor die dag → None (gat, geen backfill).

Strikte CSV-validatie: verwachte headers, numerieke close, geldige datum. HTML/redirect of afwijkend
formaat → fail-closed (None), niets wegschrijven — geen verzonnen data.

Symbolen zijn CONFIG-gedreven (`stooq_symbols` in settings, bijv. 'spx:^spx,aex:^aex'), NIET hardcoded in
de fetch — zodat het (onverifieerde) AEX-symbool bewust in de config vastligt en met `source_version`
meebeweegt.
"""
from __future__ import annotations
import csv as _csv
import datetime
import io
import logging
import urllib.parse

import requests

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_ENDPOINT = "https://stooq.com/q/d/l/"
_EXPECTED_HEADER = ["Date", "Open", "High", "Low", "Close", "Volume"]


class StooqIndexSkill(DataSourceSkill):
    name = "stooq_index"
    SOURCE = "stooq"
    cost = "free"
    kind = "flux"
    DEFAULT_FREQUENCY = "daily"
    required_env = ()
    description = "Dagelijkse slotkoers van beursindices via het Stooq CSV-endpoint (strikt geparsed, geen mock)."

    def _symbols(self, context) -> dict:
        """{veld: symbool} uit de config (`stooq_symbols='spx:^spx,aex:^aex'`). Leeg → niets te doen."""
        raw = (getattr(context, "settings", {}) or {}).get("stooq_symbols", "") or ""
        out = {}
        for part in raw.split(","):
            if ":" in part:
                field, sym = part.split(":", 1)
                if field.strip() and sym.strip():
                    out[field.strip()] = sym.strip()
        return out

    def _source_version(self, context) -> int:
        try:
            return int((getattr(context, "settings", {}) or {}).get("stooq_source_version", "1"))
        except (TypeError, ValueError):
            return 1

    def available_metrics(self, context=None) -> list[str]:
        return list(self._symbols(context).keys()) if context is not None else []

    def is_configured(self, context) -> bool:
        return bool(self._symbols(context))                 # publiek endpoint; 'geconfigureerd' = symbolen gezet

    def _endpoint(self, symbol: str) -> str:
        return f"{_ENDPOINT}?s={urllib.parse.quote(symbol)}&i=d"

    def _get(self, symbol: str) -> str:
        r = requests.get(self._endpoint(symbol), timeout=20)
        r.raise_for_status()
        return r.text

    def _close_for(self, symbol: str, datum: str, *, _fetch=None) -> float | None:
        """Slotkoers voor EXACT `datum`, strikt geparsed. None bij fetch-fout, HTML, afwijkende headers,
        niet-numerieke close, ongeldige datum, of geen rij voor die dag (geen mock, geen schatting)."""
        try:
            text = _fetch(symbol) if _fetch else self._get(symbol)
        except Exception as exc:
            log.warning("Stooq fetch faalde (%s): %s", symbol, exc)
            return None
        if not text or text.lstrip()[:1] == "<":            # HTML/redirect i.p.v. CSV → fail-closed
            log.warning("Stooq gaf geen CSV terug voor %s (HTML/leeg)", symbol)
            return None
        try:
            rows = list(_csv.reader(io.StringIO(text)))
        except Exception:
            return None
        if not rows or [h.strip() for h in rows[0]] != _EXPECTED_HEADER:
            log.warning("Stooq onverwachte header voor %s: %s", symbol, rows[0] if rows else None)
            return None
        di, ci = _EXPECTED_HEADER.index("Date"), _EXPECTED_HEADER.index("Close")
        for r in rows[1:]:
            if len(r) != len(_EXPECTED_HEADER) or r[di] != datum:
                continue
            try:
                datetime.date.fromisoformat(r[di])          # geldige datum
                return float(r[ci])                          # numerieke close
            except (ValueError, TypeError):
                log.warning("Stooq niet-numerieke close/ongeldige datum voor %s op %s", symbol, datum)
                return None
        return None                                          # geen rij voor die dag → gat

    def daily_values(self, context, datum: str) -> dict:
        syms = self._symbols(context)
        return {field: self._close_for(symbol, datum) for field, symbol in syms.items()}

    def observation_meta(self, context, datum: str, field: str) -> dict:
        symbol = self._symbols(context).get(field, "")
        return {"source_version": self._source_version(context),
                "endpoint": self._endpoint(symbol), "symbol": symbol}

    def run(self, payload: dict, context) -> dict:
        """Ad-hoc: de dagwaarden voor een datum (default de vorige volledige UTC-dag). Voor de sandbox-check."""
        datum = payload.get("datum") or (
            datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
        return {"datum": datum, "values": self.daily_values(context, datum)}
