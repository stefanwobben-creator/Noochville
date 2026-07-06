"""GdeltToneSkill — dagelijkse gemiddelde nieuwstoon voor een BEVROREN set categorietermen (GDELT DOC 2.0).

UITSLUITEND vastlegging (geen KPI/analyse/normalisatie). Keyless GET op de GDELT DOC-API
(mode=timelinetone). Per term één observatie per dag: de gemiddelde toon van de laatste VOLLEDIGE dag.

Bevriezing: de termen komen bij runtime UITSLUITEND uit de config (`gdelt_terms`), nooit live uit de
Library. Een wijziging is een bewuste config-aanpassing plus ophogen van `gdelt_source_version`.

Strikte JSON-validatie: verwachte `timeline[].data[].{date,value}`-structuur. Onverwachte structuur, HTML
of niet-JSON → fail-closed (None), niets wegschrijven.
"""
from __future__ import annotations
import datetime
import logging
import re
import time
import urllib.parse

import requests

from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
_TIMESPAN = "2d"
_SPACING_SECONDS = 6.0        # GDELT: max 1 request / 5s → per term netjes spatiëren


def _sanitize_field(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", term.strip().lower()).strip("_")


class GdeltToneSkill(DataSourceSkill):
    name = "gdelt_tone"
    SOURCE = "gdelt_tone"
    cost = "rate_limited"
    kind = "flux"
    DEFAULT_FREQUENCY = "daily"
    required_env = ()
    description = "Dagelijkse GDELT-nieuwstoon voor een bevroren set categorietermen (strikt JSON, geen mock)."

    def _terms(self, context) -> list[str]:
        raw = (getattr(context, "settings", {}) or {}).get("gdelt_terms", "") or ""
        return [t.strip() for t in raw.split(",") if t.strip()]

    def _source_version(self, context) -> int:
        try:
            return int((getattr(context, "settings", {}) or {}).get("gdelt_source_version", "1"))
        except (TypeError, ValueError):
            return 1

    def available_metrics(self, context=None) -> list[str]:
        return [_sanitize_field(t) for t in self._terms(context)] if context is not None else []

    def is_configured(self, context) -> bool:
        return bool(self._terms(context))

    def _endpoint(self, term: str) -> str:
        q = urllib.parse.urlencode({"query": term, "mode": "timelinetone",
                                    "timespan": _TIMESPAN, "format": "json"})
        return f"{_ENDPOINT}?{q}"

    def _get(self, term: str) -> dict:
        r = requests.get(self._endpoint(term), timeout=25)
        r.raise_for_status()
        return r.json()                                   # niet-JSON → raise → fail-closed in _tone_for

    def _tone_for(self, term: str, datum: str, *, _fetch=None) -> float | None:
        """Gemiddelde toon voor EXACT `datum`, strikt geparsed. None bij fetch-fout, niet-JSON, afwijkende
        structuur, niet-numerieke waarde, of geen data voor die dag (geen mock, geen schatting)."""
        try:
            data = _fetch(term) if _fetch else self._get(term)
        except Exception as exc:
            log.warning("GDELT fetch faalde (%s): %s", term, exc)
            return None
        # strikte structuur-validatie
        if not isinstance(data, dict):
            return None
        timeline = data.get("timeline")
        if not isinstance(timeline, list) or not timeline or not isinstance(timeline[0], dict):
            log.warning("GDELT onverwachte structuur (geen timeline) voor %s", term)
            return None
        points = timeline[0].get("data")
        if not isinstance(points, list):
            log.warning("GDELT onverwachte structuur (geen data-lijst) voor %s", term)
            return None
        want = datum.replace("-", "")                     # 'YYYY-MM-DD' → 'YYYYMMDD'
        vals = []
        for p in points:
            if not isinstance(p, dict) or "date" not in p or "value" not in p:
                return None                               # afwijkend punt → fail-closed
            d = str(p["date"])
            if len(d) < 8 or not d[:8].isdigit():
                return None
            if d[:8] != want:
                continue
            try:
                vals.append(float(p["value"]))
            except (TypeError, ValueError):
                return None                               # niet-numerieke waarde → fail-closed
        if not vals:
            return None                                   # geen data voor die dag → gat
        return round(sum(vals) / len(vals), 4)

    def daily_values(self, context, datum: str, *, _sleep=None) -> dict:
        """Per term één observatie. GDELT staat max 1 request/5s toe → spatieer tussen de per-term-calls
        (injecteerbare `_sleep` voor tests)."""
        sleep = _sleep if _sleep is not None else time.sleep
        out = {}
        for i, term in enumerate(self._terms(context)):
            if i:
                sleep(_SPACING_SECONDS)
            out[_sanitize_field(term)] = self._tone_for(term, datum)
        return out

    def observation_meta(self, context, datum: str, field: str) -> dict:
        term = next((t for t in self._terms(context) if _sanitize_field(t) == field), "")
        return {"source_version": self._source_version(context),
                "endpoint": self._endpoint(term), "term": term, "timespan": _TIMESPAN}

    def run(self, payload: dict, context) -> dict:
        datum = payload.get("datum") or (
            datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
        return {"datum": datum, "values": self.daily_values(context, datum)}
