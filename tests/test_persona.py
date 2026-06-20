"""Tests voor Record.persona en Inhabitant.display_name."""
from __future__ import annotations
from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry


def _make_inhabitant(role_id: str, persona: str | None = None) -> Inhabitant:
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(settings={}, data_dir="/tmp", records=None)
    record = Record(
        id=role_id,
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="test", skills=[]),
        source="seed",
        persona=persona,
    )
    return Inhabitant(record, bus, registry, context)


def test_record_persona_stored():
    """Record.persona bewaart de doorgegeven waarde."""
    rec = Record(
        id="website_watcher",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="test", skills=[]),
        persona="Corry Coconut",
    )
    assert rec.persona == "Corry Coconut"


def test_record_persona_default_none():
    """Record.persona is standaard None als niet opgegeven."""
    rec = Record(
        id="librarian",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="test", skills=[]),
    )
    assert rec.persona is None


def test_display_name_returns_persona():
    """display_name geeft de persona-naam terug als die gezet is."""
    inh = _make_inhabitant("website_watcher", persona="Corry Coconut")
    assert inh.display_name == "Corry Coconut"


def test_display_name_fallback_to_role_id():
    """display_name valt terug op de rol-id als persona None is."""
    inh = _make_inhabitant("website_watcher", persona=None)
    assert inh.display_name == "website_watcher"


def test_display_name_not_classname():
    """display_name geeft nooit de Python-klassenaam terug."""
    inh = _make_inhabitant("website_watcher", persona=None)
    assert inh.display_name != type(inh).__name__
