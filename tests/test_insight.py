"""Tests voor Insight model en NotesStore."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from nooch_village.insight import Insight, GroundingStatus
from nooch_village.notes_store import NotesStore


def _store(tmp_path: Path) -> NotesStore:
    return NotesStore(path=str(tmp_path / "notes.json"))


def test_create_note():
    note = Insight(
        id="mother_earth_ceo_69pct",
        claim="69% van Fortune-500-CEO's noemt klimaat een topprioriteit (2024).",
        source="gesprek_stefan_2026-06-16",
    )
    assert note.id == "mother_earth_ceo_69pct"
    assert "69%" in note.claim
    assert note.source_date is None
    assert note.created_at is not None
    assert note.links_to == []
    assert note.tags == []


def test_store_add_and_get(tmp_path):
    store = _store(tmp_path)
    note = Insight(
        id="plastic_free_rising",
        claim="Plastic-free schoeisel stijgt in EU-beleidstaal (ngram slope +0.4, 2010-2019).",
        source="ngram_culture_skill",
        source_date="2026-06-16",
        tags=["plastic", "trend"],
    )
    store.add(note)
    retrieved = store.get("plastic_free_rising")
    assert retrieved is not None
    assert retrieved.id == note.id
    assert retrieved.claim == note.claim
    assert retrieved.source_date == "2026-06-16"
    assert retrieved.tags == ["plastic", "trend"]


def test_store_persists_to_disk(tmp_path):
    store = _store(tmp_path)
    note = Insight(
        id="burger_frame_avoid",
        claim="'Burger' versterkt passiviteit; burgerframe heeft voorkeur boven consumentframe.",
        source="lexicon_seed",
    )
    store.add(note)

    raw = json.loads((tmp_path / "notes.json").read_text(encoding="utf-8"))
    assert "burger_frame_avoid" in raw
    assert raw["burger_frame_avoid"]["claim"] == note.claim
    assert "created_at" in raw["burger_frame_avoid"]


def test_duplicate_id_raises(tmp_path):
    store = _store(tmp_path)
    note = Insight(id="dup", claim="Eerste claim.", source="test")
    store.add(note)

    with pytest.raises(ValueError, match="bestaat al"):
        store.add(Insight(id="dup", claim="Tweede claim.", source="test"))


# --- grounding-validator tests ---

def test_default_status_is_unresolved():
    note = Insight(id="x", claim="Een claim.", source="test")
    assert note.status == GroundingStatus.UNRESOLVED


def test_supported_requires_grounds():
    with pytest.raises(ValidationError, match="grounds"):
        Insight(id="x", claim="Een claim.", source="test", status=GroundingStatus.SUPPORTED)
    note = Insight(
        id="x", claim="Een claim.", source="test",
        status=GroundingStatus.SUPPORTED,
        grounds="Studie A toont X aan.",
    )
    assert note.status == GroundingStatus.SUPPORTED


def test_verified_requires_grounds_warrant_rebuttal():
    with pytest.raises(ValidationError, match="warrant|rebuttal"):
        Insight(
            id="x", claim="Een claim.", source="test",
            status=GroundingStatus.VERIFIED,
            grounds="Studie A toont X aan.",
        )
    note = Insight(
        id="x", claim="Een claim.", source="test",
        status=GroundingStatus.VERIFIED,
        grounds="Studie A toont X aan.",
        warrant="Dit geldt wanneer populatie N > 1000.",
        rebuttal="Tenzij confounding factor Y aanwezig is.",
    )
    assert note.qualifier is None
    assert note.status == GroundingStatus.VERIFIED


def test_old_card_loads_with_unresolved_default():
    old_fields = {
        "id": "oud_kaartje",
        "claim": "Een oude claim.",
        "source": "archief",
    }
    note = Insight(**old_fields)
    assert note.status == GroundingStatus.UNRESOLVED
    assert note.grounds is None
