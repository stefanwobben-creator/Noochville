"""Tests voor cadence_events — pure helper, thread-vrij, geen bus."""
from datetime import date
from nooch_village.roles import cadence_events


def test_1_januari():
    assert cadence_events(date(2026, 1, 1)) == ["dag_begint", "maand_begint", "kwartaal_begint"]


def test_1_maart():
    assert cadence_events(date(2026, 3, 1)) == ["dag_begint", "maand_begint"]


def test_15_maart():
    assert cadence_events(date(2026, 3, 15)) == ["dag_begint"]


def test_1_april():
    assert cadence_events(date(2026, 4, 1)) == ["dag_begint", "maand_begint", "kwartaal_begint"]


def test_alle_kwartaalstarts():
    for maand in (1, 4, 7, 10):
        events = cadence_events(date(2026, maand, 1))
        assert "kwartaal_begint" in events, f"maand {maand} zou kwartaal_begint moeten hebben"


def test_niet_kwartaalstart_maanden():
    for maand in (2, 3, 5, 6, 8, 9, 11, 12):
        events = cadence_events(date(2026, maand, 1))
        assert "kwartaal_begint" not in events
        assert "maand_begint" in events
