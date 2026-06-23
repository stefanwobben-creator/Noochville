"""Tests voor Librarian._write_child_card (Fase 1 brokje 6). Thread-vrij.

Het kind-kaartje uit waaróm-onderzoek is een NIEUW atomair kaartje (Ahrens),
gekoppeld aan de trend-kaart via een geboren-uit-link (kind -> trend). Dezelfde
vraag opnieuw verrijkt het kind in plaats van te dupliceren. Het trend-kaartje
zelf blijft ongemoeid (atomariteit). Geen assessment betekent niets schrijven.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.roles import Librarian
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


def _make_librarian(tmp_path):
    bus = EventBus(name="test")
    notes = NotesStore(str(tmp_path / "notes.json"))
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(status=lambda w: None),
        lexicon=SimpleNamespace(concept_for_word=lambda w: None),
        notes=notes,
        observations=None,
    )
    record = Record(
        id="librarian", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="test"), source="seed",
    )
    lib = Librarian(record, bus, SkillRegistry(), context)
    return lib, notes


_VRAAG = "Welke voordelen drijven de opkomst van barefoot schoenen?"
_ASSESSMENT = "Onderzoek koppelt barefoot lopen aan sterkere voetspieren."
_EVIDENCE = [{"title": "Foot strength study", "year": 2021}]


def _trend(notes):
    notes.add(Insight(id="trend1", claim="barefoot schoenen stijgen",
                      source="trend", word="barefoot shoes"))


def test_nieuw_kind_kaartje_met_link(tmp_path):
    lib, notes = _make_librarian(tmp_path)
    _trend(notes)
    kind = lib._write_child_card("trend1", _VRAAG, _EVIDENCE, _ASSESSMENT)
    assert kind is not None
    assert kind.claim == _ASSESSMENT
    # geboren-uit: het touwtje wijst van het kind naar de trend
    assert "trend1" in notes.get(kind.id).links_to
    assert len(notes.all()) == 2  # trend + kind


def test_trend_kaartje_blijft_ongemoeid(tmp_path):
    """Atomair: het kind is een eigen kaartje; de trend-kaart wordt niet verdikt."""
    lib, notes = _make_librarian(tmp_path)
    _trend(notes)
    lib._write_child_card("trend1", _VRAAG, _EVIDENCE, _ASSESSMENT)
    trend = notes.get("trend1")
    assert trend.claim == "barefoot schoenen stijgen"  # claim onveranderd
    assert trend.links_to == []                         # link zit op het kind


def test_zelfde_vraag_verrijkt_niet_dupliceert(tmp_path):
    lib, notes = _make_librarian(tmp_path)
    _trend(notes)
    lib._write_child_card("trend1", _VRAAG, _EVIDENCE, _ASSESSMENT)
    kind = lib._write_child_card("trend1", _VRAAG, _EVIDENCE, _ASSESSMENT)
    assert kind.grounding_count == 2               # verrijkt, niet gedupliceerd
    assert len(notes.all()) == 2                   # nog steeds trend + één kind
    assert notes.get(kind.id).links_to == ["trend1"]  # link precies één keer


def test_geen_assessment_schrijft_niets(tmp_path):
    lib, notes = _make_librarian(tmp_path)
    _trend(notes)
    assert lib._write_child_card("trend1", _VRAAG, _EVIDENCE, "") is None
    assert len(notes.all()) == 1                   # alleen de trend
