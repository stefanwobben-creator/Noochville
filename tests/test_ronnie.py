"""Tests voor Ronnie de Reflector — thread-vrij.

Zeven scenario's:
1. Ronnie abonneert zich op dag_eindigt — na publish staat er werk in de inbox.
2. Op dag_eindigt schrijft Ronnie een bulletin (LLM gemockt, vier koppen aanwezig).
3. Lege dag (geen events) → bulletin wordt toch geschreven.
4. LLM-fout (returns None) → geen bestand, warning gelogd.
5. Ronnie luistert op de vier nieuwe event-typen (incl. means_gap_sensed).
6. Field Note wordt meegestuurd in de LLM-prompt.
7. Ontbrekende Field Note → geen crash, bulletin toch geschreven.
"""
from __future__ import annotations
import logging
import pytest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.roles import Ronnie
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill


def _make_ronnie(tmp_path):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    registry.register(BulletinSchrijvenSkill())
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        records=None,
    )
    record = Record(
        id="ronnie",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="Schrijft het dagelijkse dorpsbulletin",
            skills=["bulletin_schrijven"],
        ),
        source="seed",
    )
    ronnie = Ronnie(record, bus, registry, context)
    return ronnie, bus


_MOCK_BULLETIN = (
    "# Dorpsbulletin 2026-06-15\n"
    "## Wat ik vandaag zag\nEen rustige dag in het dorp.\n"
    "## Wie was actief\nDe tijdwachter.\n"
    "## Wat ik signaleer\nNiets bijzonders.\n"
    "## Tot morgen\nTot morgen!"
)


def test_ronnie_subscribes_to_dag_eindigt(tmp_path):
    ronnie, bus = _make_ronnie(tmp_path)
    assert ronnie.inbox.pending() == 0
    bus.publish(Event("dag_eindigt", {}, "test"))
    assert ronnie.inbox.pending() > 0


def test_ronnie_writes_bulletin_on_dag_eindigt(tmp_path):
    ronnie, bus = _make_ronnie(tmp_path)
    ronnie._events_today = [
        {"name": "dag_begint", "by": "timekeeper", "note": ""},
        {"name": "pulse_completed", "by": "analyst", "note": ""},
    ]

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN):
        ronnie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    files = list(bulletins_dir.iterdir())
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    for section in ("## Wat ik vandaag zag", "## Wie was actief",
                    "## Wat ik signaleer", "## Tot morgen"):
        assert section in content
    assert ronnie._events_today == []


def test_ronnie_handles_empty_run(tmp_path):
    ronnie, bus = _make_ronnie(tmp_path)

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN):
        ronnie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    files = list(bulletins_dir.iterdir())
    assert len(files) == 1


def test_ronnie_handles_llm_failure(tmp_path, caplog):
    ronnie, bus = _make_ronnie(tmp_path)
    ronnie._events_today = [{"name": "dag_begint", "by": "timekeeper", "note": ""}]

    with patch("nooch_village.llm.reason", return_value=None):
        with caplog.at_level(logging.WARNING):
            ronnie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    assert not bulletins_dir.exists() or len(list(bulletins_dir.iterdir())) == 0
    assert any(
        "llm" in r.message.lower() or "bulletin" in r.message.lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )


def _drain(ronnie) -> None:
    """Drain Ronnie's inbox: voer elke event-job uit op de huidige thread."""
    while ronnie.inbox.pending() > 0:
        job = ronnie.inbox.take(timeout=0.05)
        if job and callable(job):
            job()


def test_ronnie_listens_to_more_events(tmp_path):
    ronnie, bus = _make_ronnie(tmp_path)

    to_publish = [
        Event("tension_sensed",          {"by": "noochie",           "description": "spanning"}, "noochie"),
        Event("means_gap_sensed",         {"by": "kennis_scout",      "gap_key": "test_gap"},     "kennis_scout"),
        Event("pulse_completed",          {"by": "analyst"},                                       "analyst"),
        Event("tijdgeest_pulse_completed",{"by": "tijdgeest_wachter", "ok": True},                "tijdgeest_wachter"),
    ]
    for e in to_publish:
        bus.publish(e)

    _drain(ronnie)

    collected_names = {e["name"] for e in ronnie._events_today}
    assert "tension_sensed"           in collected_names
    assert "means_gap_sensed"         in collected_names
    assert "pulse_completed"          in collected_names
    assert "tijdgeest_pulse_completed" in collected_names


def test_ronnie_includes_field_note_in_prompt(tmp_path):
    ronnie, bus = _make_ronnie(tmp_path)

    output_dir = Path(tmp_path) / "output"
    output_dir.mkdir()
    today = date.today().isoformat()
    field_note_text = "## Groei-analyse\nBezoekers stabiel op 234 unieke bezoekers."
    (output_dir / f"field_note_{today}.md").write_text(field_note_text, encoding="utf-8")

    ronnie._events_today = [{"name": "dag_begint", "by": "timekeeper", "note": ""}]

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN) as mock_llm:
        ronnie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    assert mock_llm.called
    prompt = mock_llm.call_args[0][0]
    assert "Groei-analyse" in prompt
    assert "Bezoekers stabiel op 234" in prompt


def test_ronnie_handles_missing_field_note(tmp_path):
    ronnie, bus = _make_ronnie(tmp_path)
    ronnie._events_today = [{"name": "dag_begint", "by": "timekeeper", "note": ""}]

    with patch("nooch_village.llm.reason", return_value=_MOCK_BULLETIN):
        ronnie._on_dag_eindigt(Event("dag_eindigt", {}, "test"))

    bulletins_dir = Path(tmp_path) / "bulletins"
    assert len(list(bulletins_dir.iterdir())) == 1
