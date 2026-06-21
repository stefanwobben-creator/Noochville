"""Tests voor unverified_claims."""
from __future__ import annotations
from pathlib import Path
from nooch_village.insight import Insight, GroundingStatus, EvidenceType
from nooch_village.notes_store import NotesStore
from nooch_village.publication_check import unverified_claims


def _store(tmp_path: Path) -> NotesStore:
    return NotesStore(path=str(tmp_path / "notes.json"))


def _verified_note(id: str) -> Insight:
    return Insight(
        id=id,
        claim="Een geverifieerde claim.",
        source="studie_x",
        status=GroundingStatus.VERIFIED,
        grounds="Studie X toont dit aan.",
        warrant="Geldt voor populatie N > 1000.",
        rebuttal="Tenzij factor Y aanwezig is.",
        evidence_type=EvidenceType.CERTIFIED,
    )


def test_verified_note_gives_no_issues(tmp_path):
    store = _store(tmp_path)
    store.add(_verified_note("note_a"))
    assert unverified_claims(["note_a"], store) == []


def test_unresolved_note_gives_issue(tmp_path):
    store = _store(tmp_path)
    store.add(Insight(id="note_b", claim="Een claim.", source="test"))
    issues = unverified_claims(["note_b"], store)
    assert len(issues) == 1
    assert issues[0].insight_id == "note_b"
    assert "unresolved" in issues[0].reason


def test_missing_id_gives_issue(tmp_path):
    store = _store(tmp_path)
    issues = unverified_claims(["bestaat_niet"], store)
    assert len(issues) == 1
    assert issues[0].insight_id == "bestaat_niet"
    assert "geen kaartje" in issues[0].reason


def test_mix_verified_and_unknown(tmp_path):
    store = _store(tmp_path)
    store.add(_verified_note("note_ok"))
    issues = unverified_claims(["note_ok", "onbekend"], store)
    assert len(issues) == 1
    assert issues[0].insight_id == "onbekend"
