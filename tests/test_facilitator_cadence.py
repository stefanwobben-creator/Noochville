"""Tests voor Facilitator.tick() — dagcyclus in productie op een VAST kloktijdstip (scope: TimeKeeper).

Thread-vrij: tick() wordt direct aangeroepen; geen village-start. De klok wordt gemockt
(nooch_village.roles.datetime.now) zodat de vaste-tijd-logica deterministisch te testen is.
"""
from __future__ import annotations
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.roles import Facilitator
from nooch_village.skills import SkillRegistry

D1 = date(2026, 3, 15)       # gewone dag
D2 = date(2026, 3, 16)       # volgende dag
D_Q_PRE = date(2026, 3, 31)  # dag vóór kwartaalgrens
D_Q = date(2026, 4, 1)       # kwartaalgrens


def _make_facilitator(tmp_path, heartbeat: str = "0", tz: str | None = None):
    bus = EventBus(name="test")
    settings = {"heartbeat_seconds": heartbeat, "reflect_interval_seconds": "0"}
    if tz is not None:
        settings["dag_begint_tz"] = tz
    context = SimpleNamespace(settings=settings, data_dir=str(tmp_path), records=None, library=None)
    record = Record(id="facilitator", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="dag-cadans + governance"), source="seed")
    return Facilitator(record, bus, SkillRegistry(), context), bus


def _capture(bus: EventBus) -> list[str]:
    log: list[str] = []
    for name in ("dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"):
        bus.subscribe(name, lambda e, n=name: log.append(n))
    return log


def _at(d, hh=5, mm=0):
    return datetime(d.year, d.month, d.day, hh, mm)


def test_vuurt_op_vast_tijdstip(tmp_path):
    fac, bus = _make_facilitator(tmp_path); log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D1)                 # 05:00 → voorbij 04:32
        fac.tick()
    assert log == ["dag_begint"] and fac._last_day == D1.isoformat()


def test_voor_het_tijdstip_vuurt_niet(tmp_path):
    fac, bus = _make_facilitator(tmp_path); log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D1, 4, 0)           # 04:00 < 04:32 → nog niet
        fac.tick()
    assert log == [] and fac._last_day is None


def test_tweede_tick_zelfde_dag_stil(tmp_path):
    fac, bus = _make_facilitator(tmp_path); log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D1); fac.tick(); log.clear()
        m.now.return_value = _at(D1, 6, 0); fac.tick()
    assert log == [] and fac._last_day == D1.isoformat()


def test_volgende_dag_volgorde(tmp_path):
    fac, bus = _make_facilitator(tmp_path); fac._last_day = D1.isoformat(); fac._first_ring = False
    log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D2); fac.tick()
    assert log == ["dag_eindigt", "dag_begint"] and fac._last_day == D2.isoformat()


def test_kwartaalgrens_volgorde(tmp_path):
    fac, bus = _make_facilitator(tmp_path); fac._last_day = D_Q_PRE.isoformat(); fac._first_ring = False
    log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D_Q); fac.tick()
    assert log == ["dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"]


def test_restart_vuurt_niet_dubbel(tmp_path):
    fac, _ = _make_facilitator(tmp_path)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D1); fac.tick()      # vuurt + persisteert
    fac2, bus2 = _make_facilitator(tmp_path); log2 = _capture(bus2)   # 'restart'
    assert fac2._last_day == D1.isoformat()           # laatst-gevuurde datum overleeft
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D1, 9, 0); fac2.tick()
    assert log2 == []                                 # zelfde dag na restart → geen dubbel


def test_interval_tak_vuurt_en_knijpt_af(tmp_path):
    fac, bus = _make_facilitator(tmp_path, heartbeat="5"); assert fac._interval == 5.0
    log = _capture(bus)
    with patch("nooch_village.roles.date") as md, patch("nooch_village.roles.time") as mt:
        md.today.return_value = D1
        mt.time.return_value = 1000.0; fac.tick()
        assert log == ["dag_begint"] and fac._last_beat == 1000.0
        log.clear(); mt.time.return_value = 1002.0; fac.tick(); assert log == []
        log.clear(); mt.time.return_value = 1006.0; fac.tick()
        assert log == ["dag_eindigt", "dag_begint"] and fac._last_beat == 1006.0


def test_ring_gebruikt_de_door_tick_gelezen_datum(tmp_path):
    fac, bus = _make_facilitator(tmp_path); fac._last_day = D_Q_PRE.isoformat(); fac._first_ring = False
    log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = _at(D_Q)                 # één keer gelezen; _ring gebruikt deze datum
        fac.tick()
    assert log == ["dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"]
    assert fac._last_day == D_Q.isoformat()


def test_tijdzone_default_europe_madrid(tmp_path):
    from zoneinfo import ZoneInfo
    fac, _ = _make_facilitator(tmp_path)                      # geen tz in settings → default Europe/Madrid
    assert fac._tz == ZoneInfo("Europe/Madrid")


def test_tick_rekent_tegen_geconfigureerde_tz(tmp_path):
    from zoneinfo import ZoneInfo
    fac, bus = _make_facilitator(tmp_path); log = _capture(bus)
    with patch("nooch_village.roles.datetime") as m:
        m.now.return_value = datetime(2026, 3, 15, 4, 35, tzinfo=ZoneInfo("Europe/Madrid"))  # 04:35 Madrid
        fac.tick()
    m.now.assert_called_once_with(fac._tz)                    # rekent tegen de config-tz, niet now() kaal
    assert log == ["dag_begint"] and fac._last_day == "2026-03-15"   # persist-datum = Madrid-datum


def test_ongeldige_tz_valt_terug_op_server_lokaal(tmp_path):
    fac, _ = _make_facilitator(tmp_path, tz="Onzin/Nergens")
    assert fac._tz is None                                    # fail-soft → datetime.now(None) = server-lokaal
