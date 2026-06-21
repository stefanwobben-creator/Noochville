"""Tests voor review_publication."""
from __future__ import annotations
from pathlib import Path
from nooch_village.insight import Insight, GroundingStatus, EvidenceType
from nooch_village.notes_store import NotesStore
from nooch_village.publication_check import review_publication, PublicationKind


def _store(tmp_path: Path) -> NotesStore:
    return NotesStore(path=str(tmp_path / "notes.json"))


def _add_verified(store: NotesStore, id: str) -> None:
    store.add(Insight(
        id=id,
        claim="Een geverifieerde claim.",
        source="studie_x",
        status=GroundingStatus.VERIFIED,
        grounds="Studie X toont dit aan.",
        warrant="Geldt voor populatie N > 1000.",
        rebuttal="Tenzij factor Y aanwezig is.",
        evidence_type=EvidenceType.CERTIFIED,
    ))


def test_sales_page_with_problems(tmp_path):
    store = _store(tmp_path)
    report = review_publication(
        text="Onze plastic zool houdt lang mee.",
        claim_insight_ids=["bestaat_niet"],
        kind=PublicationKind.SALES_PAGE,
        store=store,
    )
    assert report.ok is False
    assert "plastic" in report.forbidden_words
    assert len(report.claim_issues) == 1


def test_sales_page_clean(tmp_path):
    store = _store(tmp_path)
    _add_verified(store, "note_ok")
    report = review_publication(
        text="Gemaakt van acht planten.",
        claim_insight_ids=["note_ok"],
        kind=PublicationKind.SALES_PAGE,
        store=store,
    )
    assert report.ok is True
    assert report.forbidden_words == []
    assert report.claim_issues == []


def test_blog_lets_everything_through(tmp_path):
    store = _store(tmp_path)
    report = review_publication(
        text="Onze plastic zool houdt lang mee.",
        claim_insight_ids=["bestaat_niet"],
        kind=PublicationKind.BLOG,
        store=store,
    )
    assert report.ok is True
    assert report.forbidden_words == []
    assert report.claim_issues == []


def test_passport_with_problem(tmp_path):
    store = _store(tmp_path)
    report = review_publication(
        text="Bovenkant van leer.",
        claim_insight_ids=[],
        kind=PublicationKind.PASSPORT,
        store=store,
    )
    assert report.ok is False
    assert "leer" in report.forbidden_words
