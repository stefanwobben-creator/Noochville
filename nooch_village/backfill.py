"""Handmatig backfill-mechanisme: haal historische dagwaarden op voor een flux-bron en schrijf ze per
periode idempotent naar de observatie-store — zodat de dashboards ook het verleden tonen (de live-collector
begint pas bij de activatiedatum van een bron).

Alleen bronnen die geverifieerd flux ÉN per-datum historisch bevraagbaar zijn (hun daily_values honoreert
de meegegeven datum) staan in BACKFILL_SOURCES. Snapshot-bronnen (OpenAlex, Semantic Scholar) kunnen niet
terug in de tijd en vallen structureel buiten scope. De schrijf loopt via dezelfde canonieke sleutel en
dezelfde idempotente record_daily als de collector, dus backfill-punten botsen nooit met live-punten en
herdraaien geeft geen duplicaten.
"""
from __future__ import annotations
import datetime
import logging
import time

from nooch_village.collector import _expected_period, _dimension_values
from nooch_village.observations import ObservationStore, dim_slug
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill

log = logging.getLogger("village.backfill")

# Whitelist: bron-id → skill-fabriek. Alleen flux + per-datum historisch bevraagbaar, geverifieerd met de
# contract-test in tests/test_backfill.py (daily_values stuurt de meegegeven datum écht mee). Uitbreiden
# (gsc/shopify/trends) = pas ná die contract-test hier toevoegen. Een runtime kind=="flux"-check is niet
# genoeg: een flux-skill die de datum negeert en altijd 'gisteren' teruggeeft, zou dezelfde waarde onder
# elke historische sleutel schrijven — de contract-test maakt dat een falende test i.p.v. stille vervuiling.
BACKFILL_SOURCES = {"plausible": PlausibleSkill, "gsc": GscPerformanceSkill}


class BackfillError(ValueError):
    """Backfill kan niet draaien zoals gevraagd (onbekende/niet-ondersteunde bron, ongeldige datum-range)."""


def _daily_periods(start: datetime.date, end: datetime.date):
    """Yield elke dag-datum-sleutel van start t/m end (inclusief) als ISO-string."""
    d = start
    while d <= end:
        yield d.isoformat()
        d += datetime.timedelta(days=1)


def _periods(frequency: str, start: datetime.date, end: datetime.date):
    """De canonieke periode-sleutels van start t/m end voor deze frequentie (zelfde math als de collector,
    zodat backfill-sleutels 1-op-1 op de live-sleutels vallen). Fase 1: alleen daily; weekly (maandagen) en
    monthly (eerste-van-de-maand) zijn een bewuste seam, nog niet gebouwd."""
    if frequency == "daily":
        yield from _daily_periods(start, end)
    else:
        raise BackfillError(
            f"backfill ondersteunt nu alleen daily-frequentie (fase 1); '{frequency}' komt later")


def backfill(source: str, start_iso: str, obs: ObservationStore, context,
             today: datetime.date | None = None, sleep: float = 0.3, on_progress=None) -> dict:
    """Loop de historische periodes van `source` af (start_iso t/m de laatste volledige periode) en schrijf
    per veld de historische waarde idempotent weg via record_daily. Geeft {written, skipped, lege_dagen,
    dagen} terug.

    - `today` in UTC (injecteerbaar voor tests) — anders schuift de dag-grens t.o.v. de live-punten.
    - `end` = de laatste volledige, beschikbare periode (today-1-lag voor daily), identiek aan wat de
      collector die dag zou schrijven → naadloze aansluiting op de live-reeks, dezelfde dedup-sleutel.
    - Fail-closed per veld (None = niet schrijven). Een dag waar ÁLLE velden None zijn telt als 'lege_dag'
      (verdacht: creds/fetch-fout); een losse None (bijv. visit_duration op een 0-bezoekers-dag) is normaal.
      `v == 0` is echte data en wordt geschreven.
    """
    if source not in BACKFILL_SOURCES:
        raise BackfillError(
            f"'{source}' is geen backfill-bron. Kies uit: {', '.join(sorted(BACKFILL_SOURCES))}. "
            f"Snapshot-bronnen (openalex, semanticscholar) kunnen niet terug in de tijd.")
    try:
        start = datetime.date.fromisoformat(start_iso)
    except ValueError:
        raise BackfillError(f"ongeldige startdatum '{start_iso}', verwacht YYYY-MM-DD")

    skill = BACKFILL_SOURCES[source]()
    if getattr(skill, "kind", "flux") != "flux":                 # belt-and-suspenders: whitelist + kind
        raise BackfillError(f"'{source}' is geen flux-bron — backfill is alleen voor flux")
    fields = list(skill.available_metrics(context))
    freqs = {skill.frequency(f) for f in fields}
    if len(freqs) != 1:
        raise BackfillError(f"'{source}' mengt frequenties {freqs} — fase 1 verwacht één (daily)")
    freq = freqs.pop()
    if freq != "daily":
        raise BackfillError(f"backfill ondersteunt nu alleen daily (fase 1); '{source}' is {freq}")

    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    end = datetime.date.fromisoformat(_expected_period(freq, today, getattr(skill, "lag_days", 0)))
    # Bron-horizon: bronnen met een beperkte historie (GSC ~16 maanden) klemmen de start af, zodat je
    # geen dagen bevraagt die de bron sowieso niet heeft (die zouden enkel als lege_dagen tellen).
    clamped = False
    horizon = getattr(skill, "backfill_history_days", None)
    if horizon:
        earliest = today - datetime.timedelta(days=int(horizon))
        if start < earliest:
            start, clamped = earliest, True
    if start > end:
        raise BackfillError(
            f"startdatum {start.isoformat()} ligt ná de laatste volledige dag {end.isoformat()} — niets te doen")

    written = skipped = lege_dagen = dagen = 0
    for datum in _periods(freq, start, end):
        dagen += 1
        try:
            vals = skill.daily_values(context, datum) or {}
        except Exception as exc:
            log.warning("backfill %s %s: daily_values faalde: %s", source, datum, exc)
            vals = {}
        got_any = False
        for field in fields:
            v = vals.get(field)
            if v is None:
                continue
            got_any = True
            if obs.record_daily(source, f"{source}_{field}_day", v, bron=source, datum=datum):
                written += 1
            else:
                skipped += 1
        if not got_any:
            lege_dagen += 1
        if on_progress:
            on_progress(datum, written, skipped, lege_dagen, dagen)
        if sleep:
            time.sleep(sleep)
    return {"written": written, "skipped": skipped, "lege_dagen": lege_dagen, "dagen": dagen,
            "start": start.isoformat(), "end": end.isoformat(), "clamped": clamped}


def backfill_dimensions(source: str, start_iso: str, obs: ObservationStore, context,
                        today: datetime.date | None = None, sleep: float = 0.3, on_progress=None) -> dict:
    """Aparte, idempotente backfill van de GEDIMENSIONEERDE reeksen (bijv. Plausible per land) over de
    historie: per dag één `daily_dimension_values`-call, per (veld, dimensie-waarde) idempotent weg onder
    dezelfde `<source>_<veld>_day::<slug>`-sleutel + meta als de live-collector. Gaten blijven gaten, geen
    interpolatie. Zelfde dedup als de live-reeks → herdraaien geeft geen duplicaten, botst niet met live."""
    if source not in BACKFILL_SOURCES:
        raise BackfillError(f"'{source}' is geen backfill-bron. Kies uit: {', '.join(sorted(BACKFILL_SOURCES))}.")
    skill = BACKFILL_SOURCES[source]()
    dimension = getattr(skill, "DIMENSION", None)
    if not dimension:
        raise BackfillError(f"'{source}' heeft geen dimensie (DIMENSION) om te backfillen")
    try:
        start = datetime.date.fromisoformat(start_iso)
    except ValueError:
        raise BackfillError(f"ongeldige startdatum '{start_iso}', verwacht YYYY-MM-DD")
    values = _dimension_values(context, dimension)
    if not values:
        raise BackfillError(f"geen gecureerde dimensie-waarden voor '{dimension}' (leeg config/Library?)")

    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    end = datetime.date.fromisoformat(_expected_period("daily", today, getattr(skill, "lag_days", 0)))
    horizon = getattr(skill, "backfill_history_days", None)
    clamped = False
    if horizon:
        earliest = today - datetime.timedelta(days=int(horizon))
        if start < earliest:
            start, clamped = earliest, True
    if start > end:
        raise BackfillError(
            f"startdatum {start.isoformat()} ligt ná de laatste volledige dag {end.isoformat()} — niets te doen")

    written = skipped = lege_dagen = dagen = 0
    for datum in _daily_periods(start, end):
        dagen += 1
        try:
            dvals = skill.daily_dimension_values(context, datum, values) or {}
        except Exception as exc:
            log.warning("backfill_dim %s %s: daily_dimension_values faalde: %s", source, datum, exc)
            dvals = {}
        if not dvals:
            lege_dagen += 1
        for (field, val), v in dvals.items():
            if v is None:
                continue
            metric = f"{source}_{field}_day::{dim_slug(val)}"
            if obs.record_daily(source, metric, v, bron=source, datum=datum,
                                meta={"dimension": dimension, "value": val}):
                written += 1
            else:
                skipped += 1
        if on_progress:
            on_progress(datum, written, skipped, lege_dagen, dagen)
        if sleep:
            time.sleep(sleep)
    return {"written": written, "skipped": skipped, "lege_dagen": lege_dagen, "dagen": dagen,
            "start": start.isoformat(), "end": end.isoformat(), "clamped": clamped, "dimension": dimension}
