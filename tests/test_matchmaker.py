"""Integratietests voor Matchmaker — thread-vrij, echte EventBus."""
from __future__ import annotations
from types import SimpleNamespace
import pytest
from nooch_village.event_bus import EventBus, Event
from nooch_village.matchmaker import Matchmaker
from nooch_village.models import Task


class _StubInhabitant:
    def __init__(self, id: str, caps: list[str]):
        self.id = id
        self._caps = caps
        self.delivered: list[Task] = []
        self.inbox = SimpleNamespace(pending=lambda: len(self.delivered))

    def capabilities(self) -> list[str]:
        return self._caps

    def deliver(self, task: Task) -> None:
        self.delivered.append(task)


@pytest.fixture
def bus():
    return EventBus()


def test_routes_to_capable_inhabitant(bus):
    mm = Matchmaker(bus)
    worker = _StubInhabitant("worker", ["dooit"])
    mm.register(worker)

    bus.publish(Event("help_requested", {"capability": "dooit", "payload": {"x": 1}}, "test"))

    assert len(worker.delivered) == 1
    assert worker.delivered[0].capability == "dooit"
    assert worker.delivered[0].payload == {"x": 1}


def test_routes_to_least_loaded(bus):
    """Matchmaker kiest de inwoner met de kortste inbox."""
    mm = Matchmaker(bus)
    busy = _StubInhabitant("busy", ["dooit"])
    busy.inbox = SimpleNamespace(pending=lambda: 2)
    free = _StubInhabitant("free", ["dooit"])
    mm.register(busy)
    mm.register(free)

    bus.publish(Event("help_requested", {"capability": "dooit", "payload": {}}, "test"))

    assert len(free.delivered) == 1
    assert len(busy.delivered) == 0


def test_human_intervention_when_no_candidate(bus):
    mm = Matchmaker(bus)
    received: list[Event] = []
    bus.subscribe("human_intervention_needed", received.append)

    bus.publish(Event("help_requested", {"capability": "onbekend", "payload": {}}, "test"))

    assert len(received) == 1
    assert received[0].data["capability"] == "onbekend"
    assert "reason" in received[0].data


def test_no_cross_capability_routing(bus):
    """Een inwoner met capability 'a' ontvangt geen taak voor capability 'b'."""
    mm = Matchmaker(bus)
    worker_a = _StubInhabitant("a", ["skill_a"])
    mm.register(worker_a)
    received: list[Event] = []
    bus.subscribe("human_intervention_needed", received.append)

    bus.publish(Event("help_requested", {"capability": "skill_b", "payload": {}}, "test"))

    assert worker_a.delivered == []
    assert len(received) == 1
