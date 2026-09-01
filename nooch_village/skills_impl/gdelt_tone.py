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

from nooch_village.bron_ophalen import Uitkomst, haal_met_retry
from nooch_village.skills import DataSourceSkill

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
_TIMESPAN = "2d"
# GDELT staat ~1 request/5s toe en verbreekt daarboven de VERBINDING (geen 429). 6 seconden bleek te
# krap: de tweede term kreeg systematisch een reset, elf dagen lang, en dat las als "geen data".
# 15 is beleefdheid — de RETRY vangt de drift. Leun op het getal en je bouwt opnieuw iets dat
# stilletjes verschuift; zie nooch_village/bron_ophalen.py.
_SPACING_SECONDS = 15.0


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

    def tone_uitkomst(self, term: str, datum: str, *, _fetch=None, _sleep=None) -> Uitkomst:
        """Gemiddelde toon voor EXACT `datum`, met het ONDERSCHEID dat hier ontbrak.

        "opgehaald maar leeg" en "niet kunnen ophalen" zijn twee verschillende dingen, en ze werden
        allebei `None`. Daardoor stond `vegan_footwear` elf dagen als dode bron terwijl de ruwe
        respons gewoon 200 gaf: de tweede van twee calls kreeg een `ConnectionResetError`, en de
        `except` eromheen las dat als afwezigheid. Zie `bron_ophalen` — no_data ≠ nul, één laag
        lager."""
        res = haal_met_retry(lambda: (_fetch(term) if _fetch else self._get(term)),
                             naam=f"gdelt/{term}", sleep=_sleep)
        if res.status == "ophaalfout":
            return res
        data, _pog = res.waarde, res.pogingen
        # strikte structuur-validatie. Een afwijkende structuur is een INHOUDELIJKE fout, geen
        # transportfout: opnieuw proberen helpt niet, en het is ook geen leegte.
        if not isinstance(data, dict):
            return Uitkomst("ophaalfout", None, "antwoord is geen JSON-object", _pog)
        timeline = data.get("timeline")
        if not isinstance(timeline, list) or not timeline or not isinstance(timeline[0], dict):
            log.warning("GDELT onverwachte structuur (geen timeline) voor %s", term)
            return Uitkomst("ophaalfout", None, "geen timeline in het antwoord", _pog)
        points = timeline[0].get("data")
        if not isinstance(points, list):
            log.warning("GDELT onverwachte structuur (geen data-lijst) voor %s", term)
            return Uitkomst("ophaalfout", None, "geen data-lijst in de timeline", _pog)
        want = datum.replace("-", "")                     # 'YYYY-MM-DD' → 'YYYYMMDD'
        vals = []
        for p in points:
            if not isinstance(p, dict) or "date" not in p or "value" not in p:
                return Uitkomst("ophaalfout", None, "afwijkend datapunt", _pog)
            d = str(p["date"])
            if len(d) < 8 or not d[:8].isdigit():
                return Uitkomst("ophaalfout", None, "onleesbare datum in een datapunt", _pog)
            if d[:8] != want:
                continue
            try:
                vals.append(float(p["value"]))
            except (TypeError, ValueError):
                return Uitkomst("ophaalfout", None, "niet-numerieke waarde", _pog)
        if not vals:
            # OPGEHAALD EN LEEG: dat is een feit over de wereld, geen storing bij ons.
            return Uitkomst("leeg", None, f"geen datapunten voor {datum}", _pog)
        return Uitkomst("ok", round(sum(vals) / len(vals), 4), "", _pog)

    def _tone_for(self, term: str, datum: str, *, _fetch=None) -> float | None:
        """De oude vorm, voor aanroepers die alleen de waarde willen. `None` betekent hier "geen
        waarde" en zegt bewust NIET waarom — wie het verschil nodig heeft neemt `tone_uitkomst`."""
        return self.tone_uitkomst(term, datum, _fetch=_fetch).waarde

    def daily_values(self, context, datum: str, *, _sleep=None) -> dict:
        """Per term één observatie. GDELT staat max 1 request/5s toe → spatieer tussen de per-term-calls
        (injecteerbare `_sleep` voor tests)."""
        sleep = _sleep if _sleep is not None else time.sleep
        out = {}
        for i, term in enumerate(self._terms(context)):
            if i:
                sleep(_SPACING_SECONDS)
            res = self.tone_uitkomst(term, datum, _sleep=sleep)
            # HET ONDERSCHEID IN HET LOG, want dat is waar een mens het leest. "leeg" is een
            # waarneming over de wereld; "ophaalfout" is onwetendheid over onszelf, en die twee
            # dezelfde regel geven maakt een levende bron elf dagen lang dood.
            if res.status == "ophaalfout":
                log.warning("GDELT %s: OPHAALFOUT (%s) — geen waarneming, niet 'leeg'",
                            term, res.reden)
            elif res.status == "leeg":
                log.info("GDELT %s: leeg voor %s — opgehaald, er was niets", term, datum)
            out[_sanitize_field(term)] = res.waarde
        return out

    def observation_meta(self, context, datum: str, field: str) -> dict:
        term = next((t for t in self._terms(context) if _sanitize_field(t) == field), "")
        return {"source_version": self._source_version(context),
                "endpoint": self._endpoint(term), "term": term, "timespan": _TIMESPAN}

    def run(self, payload: dict, context) -> dict:
        datum = payload.get("datum") or (
            datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=1)).isoformat()
        return {"datum": datum, "values": self.daily_values(context, datum)}
