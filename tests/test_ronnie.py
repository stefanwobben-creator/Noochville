"""Tests voor Ronnie de Reflector — thread-vrij.

Vier scenario's:
1. Ronnie abonneert zich op dag_eindigt — na publish staat er werk in de inbox.
2. Op dag_eindigt schrijft Ronnie een bulletin (LLM gemockt, vier koppen aanwezig).
3. Lege dag (geen events) → bulletin wordt toch geschreven.
4. LLM-fout (returns None) → geen bestand, warning gelogd.
"""
from __future__ import annotations
import logging
import pytest
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
