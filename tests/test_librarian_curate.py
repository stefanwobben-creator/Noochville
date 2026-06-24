"""Test: de Librarian cureert insight_proposed-input en schrijft kaartjes weg. Thread-vrij."""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.roles import Librarian
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.notes_store import NotesStore


class _FakeCurate(Skill):
    """Nep-curate: retourneert vaste, goedgevormde kaart-dicts (geen LLM)."""
    name = "curate"
    description = "nep"
    def run(self, payload, context):
        return {"cards": [
            {"id": "consumer_declines", "claim": "Consumer declines", "grounds": "ngram",
             "source": payload.get("source", "x"), "source_date": "2026-06-24",
             "status": "supported", "links_to": [], "tags": ["framing"]},
        ]}


def _librarian(tmp_path):
    bus = EventBus(name="t")
    registry = SkillRegistry()
    registry.register(_FakeCurate())
    notes = NotesStore(str(tmp_path / "notes.json"))
    rec = Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["curate"]), source="seed")
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path), records=None,
                          library=SimpleNamespace(status=lambda w: None),
                          lexicon=SimpleNamespace(concept_for_word=lambda w: None),
                          notes=notes)
    return Librarian(rec, bus, registry, ctx), bus, notes


def test_insight_proposed_schrijft_gecureerd_kaartje(tmp_path):
    lib, bus, notes = _librarian(tmp_path)
    curated = []
    bus.subscribe("cards_curated", lambda e: curated.append(e.data))
    lib._on_insight_proposed(Event("insight_proposed",
        {"fuzzy": "consument daalt", "source": "harry"}, "harry"))
    assert notes.get("consumer_declines") is not None
    assert curated and curated[0]["added"] == ["consumer_declines"]


def test_lege_input_doet_niets(tmp_path):
    lib, bus, notes = _librarian(tmp_path)
    lib._on_insight_proposed(Event("insight_proposed", {"fuzzy": "   "}, "x"))
    assert notes.all() == []


def test_curate_in_class_map_registry():
    from nooch_village.village import Village
    v = Village(heartbeat_seconds=86400)
    assert v.registry.get("curate") is not None