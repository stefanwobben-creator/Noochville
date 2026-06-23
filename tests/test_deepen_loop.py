"""Tests voor de verdiep-lus montage (Fase 1 brokje 7b-i). Thread-vrij.

Harry._deepen_trends kiest bevestigde trends (select_for_deepening), leidt per
trend een waaróm-vraag af, onderzoekt die, en publiceert child_evidence.
Librarian._on_child_evidence schrijft daaruit het kind-kaartje plus de link.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.roles import HarryHemp, Librarian
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


class _Stub(Skill):
    def __init__(self, name, result):
        self.name = name
        self.description = f"stub:{name}"
        self._result = result

    def run(self, payload, context):
        return self._result


def _make_harry(tmp_path, notes, budget="5"):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    registry.register(_Stub("onderzoeksvraag", {"vraag": "Waarom stijgt deze trend?"}))
    registry.register(_Stub("openalex_evidence", {"hits": [{"title": "Werk", "source": "openalex"}]}))
    registry.register(_Stub("semscholar_tldr", {"no_data": True}))
    context = SimpleNamespace(
        settings={"tijdgeest_interval_seconds": "0", "reflect_interval_seconds": "0",
                  "deepen_budget": budget},
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(status=lambda w: None),
        notes=notes,
    )
    record = Record(
        id="harry_hemp", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(
            purpose="scientist",
            skills=["onderzoeksvraag", "openalex_evidence", "semscholar_tldr"],
        ),
        source="seed",
    )
    record.persona = "Harry Hemp"
    return HarryHemp(record, bus, registry, context), bus


def _make_librarian(tmp_path, notes):
    bus = EventBus(name="test")
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(status=lambda w: None),
        lexicon=SimpleNamespace(concept_for_word=lambda w: None),
        notes=notes,
        observations=None,
    )
    record = Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="test"), source="seed")
    return Librarian(record, bus, SkillRegistry(), context)


def _trend(notes, kid, word, count=3):
    notes.add(Insight(id=kid, claim=f"{word} stijgt", source="trend",
                      word=word, grounding_count=count))


# ── Harry: kiezen + onderzoeken + publiceren ──────────────────────────────────

def test_deepen_publiceert_child_evidence_voor_bevestigde_trends(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    _trend(notes, "t1", "barefoot shoes", count=4)
    _trend(notes, "t2", "vegan shoes", count=3)
    _trend(notes, "vers", "eendagsvlieg", count=1)   # niet bevestigd
    harry, bus = _make_harry(tmp_path, notes, budget="5")

    events = []
    bus.subscribe("child_evidence", lambda e: events.append(dict(e.data)))
    with patch("nooch_village.llm.reason", return_value="Een duiding."):
        harry._deepen_trends()

    assert {e["parent_id"] for e in events} == {"t1", "t2"}  # niet 'vers'
    for e in events:
        assert e["vraag"]
        assert e["assessment"] == "Een duiding."


def test_deepen_respecteert_budget(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    _trend(notes, "t1", "barefoot shoes", count=9)
    _trend(notes, "t2", "vegan shoes", count=8)
    harry, bus = _make_harry(tmp_path, notes, budget="1")

    events = []
    bus.subscribe("child_evidence", lambda e: events.append(dict(e.data)))
    with patch("nooch_village.llm.reason", return_value="x"):
        harry._deepen_trends()

    assert len(events) == 1                # budget = 1
    assert events[0]["parent_id"] == "t1"  # sterkste trend eerst (count 9)


def test_deepen_zonder_vraag_publiceert_niet(tmp_path):
    """Geen waaróm-vraag (skill geeft None) → geen child_evidence."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    _trend(notes, "t1", "barefoot shoes", count=5)
    harry, bus = _make_harry(tmp_path, notes)
    harry.registry.register(_Stub("onderzoeksvraag", {"vraag": None}))  # overschrijf

    events = []
    bus.subscribe("child_evidence", lambda e: events.append(dict(e.data)))
    with patch("nooch_village.llm.reason", return_value="x"):
        harry._deepen_trends()
    assert events == []


# ── Librarian: kind-kaartje schrijven uit child_evidence ──────────────────────

def test_librarian_schrijft_kind_op_child_evidence(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="t1", claim="barefoot stijgt", source="trend", word="barefoot shoes"))
    lib = _make_librarian(tmp_path, notes)

    lib._on_child_evidence(Event("child_evidence", {
        "parent_id": "t1",
        "vraag": "Welke voordelen drijven barefoot?",
        "evidence": [{"title": "Foot study"}],
        "assessment": "Barefoot versterkt voetspieren.",
        "from": "harry_hemp",
    }, "harry_hemp"))

    kinderen = [n for n in notes.all() if n.id != "t1"]
    assert len(kinderen) == 1
    assert kinderen[0].claim == "Barefoot versterkt voetspieren."
    assert "t1" in kinderen[0].links_to


def test_librarian_negeert_child_evidence_zonder_parent(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    lib = _make_librarian(tmp_path, notes)
    lib._on_child_evidence(Event("child_evidence", {"vraag": "x"}, "harry"))  # geen parent_id
    assert notes.all() == []
