"""Generieke dag-observatie-collector: de puls itereert over de ACTIEVE DataSourceSkills en schrijft
elk gedeclareerd veld (`available_metrics`) weg onder de canonieke sleutel `<SOURCE>_<field>_day`.
Niets is per bron of per veld hardcoded — een nieuwe bron activeren betekent dat de puls 'm ophaalt.

Per veld bepaalt de frequentie (uit de skill) de 'verwachte periode'; de collector haalt alleen op als
er nog GEEN datapunt is voor die periode (idempotent + zelfherstellend, zoals de TimeKeeper een gemiste
04:32 inhaalt) — niet op 'dagen sinds laatste ophaal'.
"""
from __future__ import annotations
import datetime
import logging
import os

from nooch_village.skills import DataSourceSkill
from nooch_village.observations import ObservationStore
from nooch_village.source_status import SourceStatusStore

log = logging.getLogger("village.collector")


def _expected_period(frequency: str, today: datetime.date, lag_days: int = 0) -> str:
    """De datum-sleutel van de verwachte periode. Fase 1: alleen 'daily' → de vorige volledige dag,
    `lag_days` dagen teruggeschoven voor bronnen met vertraging (GSC). Tragere frequenties volgen later;
    die vallen nu bewust terug op 'daily' zodat het contract al staat maar het gedrag niet verandert."""
    return (today - datetime.timedelta(days=1 + max(0, lag_days))).isoformat()


def _has_point(obs: ObservationStore, metric: str, bron: str, datum: str) -> bool:
    return any(r.get("datum") == datum for r in obs.daily_series(metric, bron=bron))


def collect_daily_observations(registry, sources: SourceStatusStore, obs: ObservationStore,
                               context, today: datetime.date | None = None) -> list:
    """Schrijf voor elke actieve DataSourceSkill de nog-ontbrekende dagvelden weg. Geeft de lijst van
    (source, field, datum) terug die daadwerkelijk geschreven is. Fail-closed: een onconfigureerbare
    of falende bron schrijft niets en laat de puls niet crashen."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    written = []
    for skill in registry.all():
        if not isinstance(skill, DataSourceSkill):
            continue
        src = skill.SOURCE
        if not sources.active(src):
            continue
        configured = skill.is_configured(context)
        sources.set_configured(src, configured)          # voedt de 'niet geconfigureerd'-status in de UI
        if not configured:
            log.warning("bron '%s' actief maar niet geconfigureerd — overslaan", src)
            continue
        # Welke velden zijn 'due' (nog geen datapunt voor de verwachte periode)?
        due = {}
        for field in skill.available_metrics():
            datum = _expected_period(skill.frequency(field), today, getattr(skill, "lag_days", 0))
            if not _has_point(obs, f"{src}_{field}_day", src, datum):
                due[field] = datum
        if not due:
            continue
        # Fase 1: alle velden zijn 'daily' → dezelfde datum; één fetch per bron.
        datum = next(iter(due.values()))
        try:
            vals = skill.daily_values(context, datum) or {}
        except Exception as exc:
            log.warning("daily_values '%s' faalde: %s", src, exc)
            continue
        for field, dtm in due.items():
            v = vals.get(field)
            if v is not None and obs.record_daily(src, f"{src}_{field}_day", v, bron=src, datum=dtm):
                written.append((src, field, dtm))
    return written


def migrate_data_sources(dd: str) -> None:
    """Eenmalige, idempotente migratie naar het nieuwe mechanisme:
    - legacy `visitors_day`/plausible → canoniek `plausible_visitors_day`/plausible.
    - Plausible in `sources.json` op ACTIEF zetten als het er nog niet in staat (het draait al) —
      zodat de default-alles-inactief de enige werkende bron niet stilzet. Een latere handmatige
      de-activatie blijft gerespecteerd (we zetten alleen bij een ontbrekende entry)."""
    obs = ObservationStore(os.path.join(dd, "observations.jsonl"))
    obs.rename_metric("visitors_day", "plausible_visitors_day", bron="plausible")
    sources = SourceStatusStore(os.path.join(dd, "sources.json"))
    if "plausible" not in sources.all():
        sources.set_active("plausible", True)
