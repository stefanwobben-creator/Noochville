"""Tests voor Facilitator.tick() — orkestratie in productie-cadans (_interval=0).

Thread-vrij: tick() wordt direct aangeroepen; geen village-start.
Bus-events worden via een synchrone subscriber gevangen.
"""
from __future__ import annotations
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.roles import Facilitator
from nooch_village.skills import SkillRegistry

D1 = date(2026, 3, 15)   # gewone dag
D2 = date(2026, 3, 16)   # volgende dag
D_Q_PRE = date(2026, 3, 31)  # dag vóór kwartaalgrens
D_Q = date(2026, 4, 1)   # eerste kwartaalgrens na D_Q_PRE


def _make_facilitator(heartbeat: str = "0"):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(
        settings={"heartbeat_seconds": heartbeat, "reflect_interval_seconds": "0"},
        data_dir="/tmp",
        records=None,
        library=None,
    )
    record = Record(
        id="facilitator",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="bewaart de dag-cadans en toetst governance"),
        source="seed",
    )
    return Facilitator(record, bus, registry, context), bus


def _capture(bus: EventBus) -> list[str]:
    """Registreert gepubliceerde event-namen in volgorde van publicatie."""
    log: list[str] = []
    for name in ("dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"):
        bus.subscribe(name, lambda e, n=name: log.append(n))
    return log


def test_eerste_tick_d1():
    """Eerste tick op D1: ringt, publiceert dag_begint, GEEN dag_eindigt; _last_day=D1."""
    fac, bus = _make_facilitator()
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D1
        fac.tick()

    assert log == ["dag_begint"]
    assert fac._last_day == D1.isoformat()


def test_tweede_tick_zelfde_dag():
    """Tweede tick met date.today() nog steeds D1: geen ring, geen events, _last_day onveranderd."""
    fac, bus = _make_facilitator()
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D1
        fac.tick()       # eerste tick → ringt
        log.clear()
        fac.tick()       # tweede tick, zelfde dag → stil

    assert log == []
    assert fac._last_day == D1.isoformat()


def test_tick_volgende_dag_volgorde():
    """Tick op D2: dag_eindigt gepubliceerd VÓÓR dag_begint."""
    fac, bus = _make_facilitator()
    fac._last_day = D1.isoformat()
    fac._first_ring = False
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D2
        fac.tick()

    assert log == ["dag_eindigt", "dag_begint"]
    assert fac._last_day == D2.isoformat()


def test_tick_kwartaalgrens_volgorde():
    """Tick op 1 april: dag_eindigt, dag_begint, maand_begint, kwartaal_begint op volgorde."""
    fac, bus = _make_facilitator()
    fac._last_day = D_Q_PRE.isoformat()
    fac._first_ring = False
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.return_value = D_Q
        fac.tick()

    assert log == ["dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"]


def test_interval_tak_vuurt_en_knijpt_af():
    """De _interval>0-tak (lokaal `run`-pad, heartbeat>0) vuurt een puls en knijpt af binnen het interval.

    Dit pad is live via `python -m nooch_village.village run` (settings.ini: heartbeat_seconds=5),
    maar werd niet getest — de overige tests draaien op heartbeat=0 (kalender-tak).
    """
    fac, bus = _make_facilitator(heartbeat="5")
    assert fac._interval == 5.0  # settings → _interval-wiring
    log = _capture(bus)

    with patch("nooch_village.roles.date") as mock_date, \
         patch("nooch_village.roles.time") as mock_time:
        mock_date.today.return_value = D1

        # Eerste tick: ruim voorbij het interval (_last_beat start op 0.0) → vuurt
        mock_time.time.return_value = 1000.0
        fac.tick()
        assert log == ["dag_begint"]        # cadence van D1; eerste ring → geen dag_eindigt
        assert fac._last_beat == 1000.0

        # Tweede tick binnen het interval (2s later) → afgeknepen, geen nieuwe events
        log.clear()
        mock_time.time.return_value = 1002.0
        fac.tick()
        assert log == []
        assert fac._last_beat == 1000.0

        # Derde tick voorbij het interval (6s na de eerste) → vuurt opnieuw, nu mét dag_eindigt
        log.clear()
        mock_time.time.return_value = 1006.0
        fac.tick()
        assert log == ["dag_eindigt", "dag_begint"]
        assert fac._last_beat == 1006.0


def test_ring_gebruikt_de_door_tick_gelezen_datum():
    """Middernacht-vangnet: _ring gebruikt de datum die tick() las, niet een herlezen datum.

    De klok springt over de middernachtgrens: date.today() geeft eerst D_Q (1 april,
    kwartaal- én maandgrens), daarna D_NA (2 april, gewone dag). tick() mag de klok
    maar één keer lezen en die datum doorgeven aan _ring. Leest _ring de klok opnieuw
    (de oude bug), dan ziet hij 2 april en vervallen maand_begint + kwartaal_begint.
    """
    fac, bus = _make_facilitator()
    fac._last_day = D_Q_PRE.isoformat()
    fac._first_ring = False
    log = _capture(bus)

    D_NA = date(2026, 4, 2)  # gewone dag; zou opduiken als _ring herleest

    with patch("nooch_village.roles.date") as mock_date:
        mock_date.today.side_effect = [D_Q, D_NA]
        fac.tick()

    # 1 april-events aanwezig => _ring gebruikte de door tick gelezen datum, niet 2 april
    assert log == ["dag_eindigt", "dag_begint", "maand_begint", "kwartaal_begint"]
    assert fac._last_day == D_Q.isoformat()
