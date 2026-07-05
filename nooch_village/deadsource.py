"""Dode-bron-sensor: senst één spanning op de OVERGANG van 'recente data' naar 'dood' (het stale-
signaal uit indicator_freshness), niet op de toestand. Dedup via de vorige-status per indicator
(deadsource_state.json), zodat een dood-overgang precies één keer sena en een gezonde bron zwijgt.

Haakt aan op de bestaande indicator_freshness-status (geen tweede detectie-mechanisme). Alleen de
echte dood-overgang (fresh→stale) senst; 'niet geconfigureerd' (unconfigured) en 'nooit gevoed' (none)
sensen niet. Leeft een bron weer op (fresh) en valt hij later opnieuw uit, dan senst hij opnieuw — de
overgang telt, niet een permanente vlag. De kind-aware drempel zit al in indicator_freshness, dus een
gezonde trage bron (weekly 10d, monthly 45d) senst niet.
"""
from __future__ import annotations
import datetime
import json
import types

from nooch_village.skills import DataSourceSkill
from nooch_village.util import atomic_write_json

_CADANS_NL = {"daily": "dagelijks", "weekly": "wekelijks", "monthly": "maandelijks"}


class DeadSourceState:
    """`data/deadsource_state.json`: {"<source>:<field>": "<vorige_freshness>"}. Onthoudt de laatst-
    geziene vers-status per indicator, zodat de sensor de fresh→stale-overgang detecteert i.p.v. elke
    puls opnieuw op de toestand te sensen."""

    def __init__(self, path: str):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self._d = json.load(f) or {}
        except Exception:
            self._d = {}

    def previous(self, key: str):
        return self._d.get(key)

    def set(self, key: str, state) -> None:
        self._d[key] = state

    def save(self) -> None:
        atomic_write_json(self.path, self._d)


def _last_datum(obs, source: str, field: str):
    from nooch_village.views.metrics import _obs_key_for_indicator
    metric, bron = _obs_key_for_indicator(source, field)
    rows = obs.daily_series(metric, bron=bron) if metric else []
    return rows[-1].get("datum") if rows else None


def sense_dead_sources(registry, context, state: DeadSourceState, emit, today=None) -> list:
    """Detecteer dood-overgangen (fresh→stale) voor de velden van ACTIEVE DataSourceSkills en roep
    `emit(source, field, last_datum, days_ago, cadans)` per overgang. Alleen fresh→stale senst; de
    vorige-status-dedup voorkomt herhaling binnen een episode en een tension-storm bij deploy (een bron
    die al dood was — geen vorige 'fresh' — senst niet). Geeft de lijst geëmitte (source, field) terug."""
    from nooch_village.views.metrics import indicator_freshness, _source_frequency
    obs = getattr(context, "observations", None)
    sources = getattr(context, "sources", None)
    if obs is None or sources is None:
        return []
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    shim = types.SimpleNamespace(observations=obs, sources=sources)
    emitted = []
    for skill in registry.all():
        if not isinstance(skill, DataSourceSkill):
            continue
        src = skill.SOURCE
        if not sources.active(src):
            continue
        cadans = _CADANS_NL.get(_source_frequency(src), _source_frequency(src))
        for field in skill.available_metrics(context):
            key = f"{src}:{field}"
            cur = indicator_freshness(shim, src, field, today=today)     # HERGEBRUIK, geen tweede mechanisme
            if state.previous(key) == "fresh" and cur == "stale":       # de OVERGANG levend→dood
                last_datum = _last_datum(obs, src, field)
                days_ago = None
                if last_datum:
                    try:
                        days_ago = (today - datetime.date.fromisoformat(last_datum)).days
                    except (TypeError, ValueError):
                        pass
                emit(src, field, last_datum, days_ago, cadans)
                emitted.append((src, field))
            state.set(key, cur)
    state.save()
    return emitted
