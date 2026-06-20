"""Tests voor TimeKeeper.tick() — orkestratie in productie-cadans (_interval=0).

Thread-vrij: tick() wordt direct aangeroepen; geen village-start.
Bus-events worden via een synchrone subscriber gevangen.
"""
from __future__ import annotations
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.roles import TimeKeeper
from nooch_village.skills import SkillRegistry

D1 = date(2026, 3, 15)   # gewone dag
D2 = date(2026, 3, 16)   # volgende dag
D_Q_PRE = date(2026, 3, 31)  # dag vóór kwartaalgrens
D_Q = date(2026, 4, 1)   # eerste kwartaalgrens na D_Q_PRE


def _make_timekeeper():
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(
        settings={"heartbeat_seconds": "0", "reflect_interval_seconds": "0"},
        data_dir="/tmp",
        records=None,
        library=None,
    )
    record = Record(
        id="timekeeper",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="bewaart de dag-cadans van het dorp"),
        source="seed",
    )
    return TimeKeeper(record, bus, registry, context), bus


def _capture(bus: EventBus) -> list[str]:
    """Registreert gepubliceerde event-namen in volgorde van publicatie."""
    log: list[str] = []
    for name in ("dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"):
        bus.subscribe(name, lambda e, n=name: log.append(n))
    return log


def test_eerste_tick_d1():
    """Eerste tick op D1: ringt, publiceert dag_begint, GEEN dag_eindigt; _last_day=D1."""
    tk, bus = _make_timekeeper()
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D1
        tk.tick()

    assert log == ["dag_begint"]
    assert tk._last_day == D1.isoformat()


def test_tweede_tick_zelfde_dag():
    """Tweede tick met date.today() nog steeds D1: geen ring, geen events, _last_day onveranderd."""
    tk, bus = _make_timekeeper()
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D1
        tk.tick()        # eerste tick → ringt
        log.clear()
        tk.tick()        # tweede tick, zelfde dag → stil

    assert log == []
    assert tk._last_day == D1.isoformat()


def test_tick_volgende_dag_volgorde():
    """Tick op D2: dag_eindigt gepubliceerd VÓÓR dag_begint."""
    tk, bus = _make_timekeeper()
    tk._last_day = D1.isoformat()
    tk._first_ring = False
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D2
        tk.tick()

    assert log == ["dag_eindigt", "dag_begint"]
    assert tk._last_day == D2.isoformat()


def test_tick_kwartaalgrens_volgorde():
    """Tick op 1 april: dag_eindigt, dag_begint, maand_begint, kwartaal_begint op volgorde."""
    tk, bus = _make_timekeeper()
    tk._last_day = D_Q_PRE.isoformat()
    tk._first_ring = False
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D_Q
        tk.tick()

    assert log == ["dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"]
