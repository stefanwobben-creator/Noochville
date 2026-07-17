"""Puls-hartslag + watchdog (dead man's switch op niet-uitvoering). Offline, thread-vrij."""
from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from nooch_village.pulse_watchdog import HeartbeatStore, WatchdogState, run_watchdog, _yesterday


def _notifier():
    calls = []
    return calls, (lambda role, day: calls.append((role, day)))


# ── de hartslag-store ─────────────────────────────────────────────────────────

def test_heartbeat_idempotent_per_dag(tmp_path):
    hb = HeartbeatStore(str(tmp_path / "pulse_heartbeat.json"))
    hb.beat("harry_hemp", "2026-07-18", "2026-07-18T04:32:10")
    hb.beat("harry_hemp", "2026-07-18", "2026-07-18T04:32:44")   # zelfde dag → geen overschrijving-ruis
    assert hb.day_of("harry_hemp") == "2026-07-18"
    assert HeartbeatStore(str(tmp_path / "pulse_heartbeat.json")).day_of("harry_hemp") == "2026-07-18"


# ── de watchdog ───────────────────────────────────────────────────────────────

def test_rol_pulste_gisteren_geen_escalatie(tmp_path):
    dd = str(tmp_path)
    HeartbeatStore(f"{dd}/pulse_heartbeat.json").beat("harry_hemp", "2026-07-18", "x")
    # since op 07-18 zetten zodat 07-18 gecontroleerd wordt
    WatchdogState(f"{dd}/pulse_watchdog.json").ensure_since("2026-07-18")
    calls, notify = _notifier()
    gemist = run_watchdog(dd, ["harry_hemp"], "2026-07-19", notify)
    assert gemist == [] and calls == []


def test_verwachte_rol_zonder_hartslag_escaleert_een_keer(tmp_path):
    dd = str(tmp_path)
    WatchdogState(f"{dd}/pulse_watchdog.json").ensure_since("2026-07-18")
    calls, notify = _notifier()
    # 07-19 begint; gisteren=07-18; harry pulste NIET → één escalatie
    gemist = run_watchdog(dd, ["harry_hemp"], "2026-07-19", notify)
    assert gemist == ["harry_hemp"] and calls == [("harry_hemp", "2026-07-18")]
    # zelfde gemiste dag opnieuw checken → geen tweede melding (idempotent)
    calls2, notify2 = _notifier()
    assert run_watchdog(dd, ["harry_hemp"], "2026-07-19", notify2) == [] and calls2 == []


def test_bootstrap_geen_vals_alarm_voor_dag_voor_de_watchdog(tmp_path):
    dd = str(tmp_path)
    calls, notify = _notifier()
    # allereerste run: since wordt vandaag (07-18); gisteren (07-17) ligt vóór de vloer → niets
    gemist = run_watchdog(dd, ["harry_hemp"], "2026-07-18", notify)
    assert gemist == [] and calls == []
    assert WatchdogState(f"{dd}/pulse_watchdog.json").since() == "2026-07-18"


def test_nooit_gepulste_rol_wordt_gevangen_na_de_vloer(tmp_path):
    dd = str(tmp_path)
    # dag 1: bootstrap (since=07-18), geen alarm
    calls, notify = _notifier()
    run_watchdog(dd, ["harry_hemp"], "2026-07-18", notify)
    assert calls == []
    # dag 2: gisteren=07-18 >= since, harry pulste nooit → hook-niet-gewired wordt nu gevangen
    calls, notify = _notifier()
    run_watchdog(dd, ["harry_hemp"], "2026-07-19", notify)
    assert calls == [("harry_hemp", "2026-07-18")]


def test_niet_verwachte_rol_wordt_nooit_geescaleerd(tmp_path):
    dd = str(tmp_path)
    WatchdogState(f"{dd}/pulse_watchdog.json").ensure_since("2026-07-18")
    calls, notify = _notifier()
    # 'analyst' zit NIET in de verwachte set → nooit escaleren, ook zonder historie
    gemist = run_watchdog(dd, ["harry_hemp"], "2026-07-19", notify)
    assert "analyst" not in gemist


# ── de react-instrumentatie (hartslag zonder skill-specifieke code) ──────────

def test_react_op_dag_begint_laat_hartslag_na(tmp_path):
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.event_bus import EventBus, Event
    from nooch_village.skills import SkillRegistry
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p"), source="seed")
    inh = Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)
    ran = []
    inh.react("dag_begint", lambda e: ran.append(1))
    # vuur dag_begint met de Madrid-label, draai de inbox-jobs af
    inh.bus.publish(Event("dag_begint", {"label": "2026-07-18"}, "timekeeper"))
    while inh.inbox.pending() > 0:
        job = inh.inbox.take(timeout=0.05)
        if job and callable(job):
            job()
    assert ran                                              # de handler liep
    assert HeartbeatStore(str(tmp_path / "pulse_heartbeat.json")).day_of("harry_hemp") == "2026-07-18"


def test_hartslag_ook_als_handler_struikelt(tmp_path):
    """De puls BEREIKTE de rol (dat is wat de watchdog toetst) → hartslag ook bij een fout."""
    from nooch_village.inhabitant import Inhabitant
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.event_bus import EventBus, Event
    from nooch_village.skills import SkillRegistry
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"}, data_dir=str(tmp_path),
                          records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="p"), source="seed")
    inh = Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)

    def _boom(e):
        raise RuntimeError("handler kapot")
    inh.react("dag_begint", _boom)
    inh.bus.publish(Event("dag_begint", {"label": "2026-07-18"}, "tk"))
    while inh.inbox.pending() > 0:
        job = inh.inbox.take(timeout=0.05)
        if job and callable(job):
            try:
                job()
            except Exception:
                pass
    assert HeartbeatStore(str(tmp_path / "pulse_heartbeat.json")).day_of("harry_hemp") == "2026-07-18"
