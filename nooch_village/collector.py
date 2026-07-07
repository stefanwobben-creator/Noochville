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
from nooch_village.observations import ObservationStore, dim_slug
from nooch_village.source_status import SourceStatusStore

log = logging.getLogger("village.collector")


def _expected_period(frequency: str, today: datetime.date, lag_days: int = 0) -> str:
    """De datum-sleutel van de verwachte periode voor deze frequentie, `lag_days` teruggeschoven voor
    bronnen met vertraging (GSC). Snapshot-bronnen (weekly/monthly) leggen per periode één stand vast:
      - daily   → de vorige volledige dag (flux)
      - weekly  → de maandag van de (lag-)week (snapshot, één meting/week)
      - monthly → de eerste van de (lag-)maand (snapshot, één meting/maand)
    De due-check 'is er al een datapunt voor deze sleutel' maakt het idempotent + zelfherstellend."""
    ref = today - datetime.timedelta(days=max(0, lag_days))
    if frequency == "weekly":
        return (ref - datetime.timedelta(days=ref.weekday())).isoformat()   # maandag van de week
    if frequency == "monthly":
        return ref.replace(day=1).isoformat()                               # eerste van de maand
    return (ref - datetime.timedelta(days=1)).isoformat()                   # daily: vorige volledige dag


def _has_point(obs: ObservationStore, metric: str, bron: str, datum: str) -> bool:
    return any(r.get("datum") == datum for r in obs.daily_series(metric, bron=bron))


def _dimension_keywords(context) -> list[str]:
    """De gecureerde selectie voor dimensie-reeksen (scope 2): uit de Library de woorden met
    status 'approved' ÉN function 'doelwit' (rank-targets; 'volg'-seeds tellen niet mee). Afgekapt op
    `gsc_dimension_max` (default 50); gedropte woorden worden GELOGD — geen stille truncatie.
    (Sortering nu alfabetisch/stabiel; later op impressies/prioriteit.)"""
    lib = getattr(context, "library", None)
    if lib is None:
        return []
    words = sorted(w for w, e in lib.all().items()
                   if e.get("status") == "approved" and lib.function_of(w) == "doelwit")
    try:
        cap = int((getattr(context, "settings", {}) or {}).get("gsc_dimension_max", 50))
    except (TypeError, ValueError):
        cap = 50
    if len(words) > cap:
        dropped = words[cap:]
        log.warning("dimensie-selectie afgekapt op %d — %d keyword(s) gedropt: %s%s", cap, len(dropped),
                    ", ".join(dropped[:10]), "…" if len(dropped) > 10 else "")
        words = words[:cap]
    return words


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
        for field in skill.available_metrics(context):
            datum = _expected_period(skill.frequency(field), today, getattr(skill, "lag_days", 0))
            if not _has_point(obs, f"{src}_{field}_day", src, datum):
                due[field] = datum
        # Fase 1: alle velden zijn 'daily' → dezelfde datum; één fetch per bron (alleen als er iets due is).
        if due:
            datum = next(iter(due.values()))
            try:
                vals = skill.daily_values(context, datum) or {}
            except Exception as exc:
                log.warning("daily_values '%s' faalde: %s", src, exc)
                vals = {}
            for field, dtm in due.items():
                v = vals.get(field)
                if v is None:
                    continue
                try:
                    meta = skill.observation_meta(context, dtm, field) or None
                except Exception:
                    meta = None
                if obs.record_daily(src, f"{src}_{field}_day", v, bron=src, datum=dtm, meta=meta):
                    written.append((src, field, dtm))

        # Scope 2 — gedimensioneerde reeksen (bijv. GSC per Library-doelwit-keyword). Onafhankelijk van de
        # totaal-velden: één extra fetch met de dimensie, gefilterd op de gecureerde selectie + cap. Gaten
        # blijven gaten (record_daily dedupliceert incl. de ::slug). Zie ARCHITECTUUR: de due-scan + write
        # is lineair per (veld×keyword) — vóór een TWEEDE dimensie-bron is een store-index vereist.
        dim = getattr(skill, "DIMENSION", None)
        metrics = skill.available_metrics(context) if dim else []
        kws = _dimension_keywords(context) if dim else []
        if dim and metrics and kws:
            ddat = _expected_period(skill.frequency(metrics[0]), today, getattr(skill, "lag_days", 0))
            if any(not _has_point(obs, f"{src}_{f}_day::{dim_slug(kw)}", src, ddat)
                   for f in metrics for kw in kws):                       # iets nog niet geschreven?
                try:
                    dvals = skill.daily_dimension_values(context, ddat, kws) or {}
                except Exception as exc:
                    log.warning("daily_dimension_values '%s' faalde: %s", src, exc)
                    dvals = {}
                for (field, kw), v in dvals.items():
                    if v is None:
                        continue
                    metric = f"{src}_{field}_day::{dim_slug(kw)}"
                    if obs.record_daily(src, metric, v, bron=src, datum=ddat,
                                        meta={"dimension": dim, "keyword": kw}):
                        written.append((src, f"{field}::{dim_slug(kw)}", ddat))
    return written


def migrate_data_sources(dd: str) -> None:
    """Eenmalige, idempotente migratie naar het nieuwe mechanisme:
    - legacy `visitors_day`/plausible → canoniek `plausible_visitors_day`/plausible.
    - Plausible in `sources.json` op ACTIEF zetten als het er nog niet in staat (het draait al) —
      zodat de default-alles-inactief de enige werkende bron niet stilzet. Een latere handmatige
      de-activatie blijft gerespecteerd (we zetten alleen bij een ontbrekende entry)."""
    obs = ObservationStore(os.path.join(dd, "observations.jsonl"))
    obs.rename_metric("visitors_day", "plausible_visitors_day", bron="plausible")
    res = obs.normalize_source_role_ids()          # cross-rol-dedup: legacy role_id → canoniek (==bron)
    if res["dropped"] or res["renamed"] or res["conflicts"]:
        log.info("observatie-rol-normalisatie: %s gedropt, %s hernoemd, %s conflict(en)",
                 res["dropped"], res["renamed"], res["conflicts"])
    sources = SourceStatusStore(os.path.join(dd, "sources.json"))
    if "plausible" not in sources.all():
        sources.set_active("plausible", True)
