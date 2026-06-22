"""Tests voor Insight model en NotesStore."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from nooch_village.insight import Insight, GroundingStatus, EvidenceType
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
        evidence_type=EvidenceType.CERTIFIED,
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


# --- evidence_type tests ---

def test_evidence_type_and_reference_are_optional():
    note = Insight(id="x", claim="Een claim.", source="test")
    assert note.evidence_type is None
    assert note.reference is None


def test_verified_without_evidence_type_raises():
    with pytest.raises(ValidationError, match="evidence_type"):
        Insight(
            id="x", claim="Een claim.", source="test",
            status=GroundingStatus.VERIFIED,
            grounds="Studie A toont X aan.",
            warrant="Dit geldt wanneer populatie N > 1000.",
            rebuttal="Tenzij confounding factor Y aanwezig is.",
        )


def test_verified_with_claimed_raises():
    with pytest.raises(ValidationError, match="CLAIMED"):
        Insight(
            id="x", claim="Een claim.", source="test",
            status=GroundingStatus.VERIFIED,
            grounds="Studie A toont X aan.",
            warrant="Dit geldt wanneer populatie N > 1000.",
            rebuttal="Tenzij confounding factor Y aanwezig is.",
            evidence_type=EvidenceType.CLAIMED,
        )


def test_verified_with_certified_is_valid():
    note = Insight(
        id="x", claim="Een claim.", source="test",
        status=GroundingStatus.VERIFIED,
        grounds="Studie A toont X aan.",
        warrant="Dit geldt wanneer populatie N > 1000.",
        rebuttal="Tenzij confounding factor Y aanwezig is.",
        evidence_type=EvidenceType.CERTIFIED,
    )
    assert note.status == GroundingStatus.VERIFIED
    assert note.evidence_type == EvidenceType.CERTIFIED


# --- concept_id tests ---

def test_concept_id_is_optional():
    note = Insight(id="x", claim="Een claim.", source="test")
    assert note.concept_id is None


def test_concept_id_stored_on_note():
    note = Insight(id="x", claim="Een claim.", source="test", concept_id="plastic_free")
    assert note.concept_id == "plastic_free"


def test_by_concept_returns_matching_notes(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="a", claim="Claim A.", source="test", concept_id="plastic_free"))
    store.add(Insight(id="b", claim="Claim B.", source="test", concept_id="plastic_free"))
    store.add(Insight(id="c", claim="Claim C.", source="test", concept_id="vegan"))
    result = store.by_concept("plastic_free")
    assert len(result) == 2
    assert {n.id for n in result} == {"a", "b"}


def test_by_concept_excludes_notes_without_concept_id(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="x", claim="Claim.", source="test"))
    assert store.by_concept("plastic_free") == []


# --- relevant_for tests ---

def test_relevant_for_zeldzaam_woord_scoort_hoger(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="a", claim=".", source="test", word="vegan running shoes"))
    store.add(Insight(id="b", claim=".", source="test", word="barefoot shoes"))
    resultaat = store.relevant_for("vegan trail shoes")
    assert len(resultaat) >= 1
    # 'vegan' zit in 1 kaartje, 'shoes' in 2 — kaartje a scoort hoger
    assert resultaat[0].id == "a"


def test_relevant_for_sluit_exacte_match_uit(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="a", claim=".", source="test", word="vegan shoes"))
    store.add(Insight(id="b", claim=".", source="test", word="barefoot shoes"))
    resultaat = store.relevant_for("vegan shoes")
    ids = [n.id for n in resultaat]
    assert "a" not in ids  # exact zelfde word → niet relevant voor zichzelf


def test_relevant_for_geen_overlap_komt_niet_terug(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="a", claim=".", source="test", word="plastic gloves"))
    resultaat = store.relevant_for("leather boots")
    assert resultaat == []


def test_relevant_for_leeg_zoekwoord_en_lege_store(tmp_path):
    store = _store(tmp_path)
    assert store.relevant_for("") == []
    assert store.relevant_for("vegan shoes") == []


def test_relevant_for_kaartjes_zonder_word_doen_niet_mee(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="a", claim=".", source="test"))          # geen word
    store.add(Insight(id="b", claim=".", source="test", word="vegan shoes"))
    resultaat = store.relevant_for("vegan trail shoes")
    ids = [n.id for n in resultaat]
    assert "a" not in ids
    assert "b" in ids
