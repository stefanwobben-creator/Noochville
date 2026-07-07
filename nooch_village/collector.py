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


# Zaad-landenlijst voor de country-dimensie (config-bewerkbaar via plausible_dimension_countries). ISO
# 3166-1 alpha-2. Start = de waargenomen + doelmarkten van Nooch (NL dominant, dan ES/FR; + BE/DE/GB/US).
_DEFAULT_DIMENSION_COUNTRIES = ["NL", "BE", "DE", "FR", "ES", "GB", "US"]


def _dimension_values(context, dimension: str) -> list[str]:
    """De gecureerde selectie per dimensie (scope 2/4), afgekapt + gedropte GELOGD (geen stille truncatie):
      - 'query'   → Library-woorden met status 'approved' ÉN function 'doelwit' (rank-targets), cap
                    `gsc_dimension_max`;
      - 'country' → de config-landenlijst `plausible_dimension_countries` (ISO-codes), cap
                    `plausible_dimension_max`.
    Onbekende dimensie → lege lijst."""
    settings = getattr(context, "settings", {}) or {}
    if dimension == "query":
        lib = getattr(context, "library", None)
        values = sorted(w for w, e in lib.all().items()
                        if e.get("status") == "approved" and lib.function_of(w) == "doelwit") if lib else []
        cap_key = "gsc_dimension_max"
    elif dimension == "country":
        raw = settings.get("plausible_dimension_countries") or ",".join(_DEFAULT_DIMENSION_COUNTRIES)
        values = [c.strip().upper() for c in raw.split(",") if c.strip()]
        cap_key = "plausible_dimension_max"
    elif dimension == "concept":
        # De labels uit `openalex_concepts = C…:label, C…:label` (de gepinde ID's leven ernaast in de config;
        # de skill mapt label→ID en query't /concepts/<id> direct). De dimensie-waarde = het label.
        raw = settings.get("openalex_concepts", "") or ""
        values = [p.split(":", 1)[1].strip() for p in raw.split(",")
                  if ":" in p and p.split(":", 1)[1].strip()]
        cap_key = "openalex_dimension_max"
    else:
        return []
    try:
        cap = int(settings.get(cap_key, 50))
    except (TypeError, ValueError):
        cap = 50
    if len(values) > cap:
        dropped = values[cap:]
        log.warning("dimensie '%s' afgekapt op %d — %d waarde(n) gedropt: %s%s", dimension, cap,
                    len(dropped), ", ".join(dropped[:10]), "…" if len(dropped) > 10 else "")
        values = values[:cap]
    return values


def _dimension_keywords(context) -> list[str]:
    """Backward-compat alias voor de query-dimensie (scope 2a)."""
    return _dimension_values(context, "query")


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
        vals_sel = _dimension_values(context, dim) if dim else []
        if dim and metrics and vals_sel:
            ddat = _expected_period(skill.frequency(metrics[0]), today, getattr(skill, "lag_days", 0))
            if any(not _has_point(obs, f"{src}_{f}_day::{dim_slug(val)}", src, ddat)
                   for f in metrics for val in vals_sel):                 # iets nog niet geschreven?
                try:
                    dvals = skill.daily_dimension_values(context, ddat, vals_sel) or {}
                except Exception as exc:
                    log.warning("daily_dimension_values '%s' faalde: %s", src, exc)
                    dvals = {}
                for (field, val), v in dvals.items():
                    if v is None:
                        continue
                    metric = f"{src}_{field}_day::{dim_slug(val)}"
                    if obs.record_daily(src, metric, v, bron=src, datum=ddat,
                                        meta={"dimension": dim, "value": val}):
                        written.append((src, f"{field}::{dim_slug(val)}", ddat))
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
