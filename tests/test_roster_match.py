"""Tests voor roster-match hulpfuncties — geen I/O, geen bus, geen threads."""
from __future__ import annotations
import pytest
from nooch_village.roster_match import gap_signature, role_signature, best_coverage
from nooch_village.models import Record, RoleDefinition, RecordType


def _rec(rid, purpose="", accs=None, domains=None, skills=None):
    return Record(
        id=rid, type=RecordType.ROLE, parent="root",
        definition=RoleDefinition(
            purpose=purpose,
            accountabilities=accs or [],
            domains=domains or [],
            skills=skills or [],
        ),
        source="seed",
    )


class _FakeRecords:
    def __init__(self, recs):
        self._recs = recs

    def all(self):
        return self._recs


# ── gap_signature ─────────────────────────────────────────────────────────────

def test_gap_signature_removes_stopwords():
    sig = gap_signature("de analyse van bezoekers per locale")
    assert "analyse" in sig
    assert "bezoekers" in sig
    assert "locale" in sig
    assert "de" not in sig and "van" not in sig and "per" not in sig


def test_gap_signature_min_length_four():
    sig = gap_signature("seo data kwartaal")
    assert "data" in sig       # 4 tekens: net goed
    assert "seo" not in sig    # 3 tekens: te kort


def test_gap_signature_dedup():
    sig = gap_signature("locale locale locale analyse")
    assert sig == {"locale", "analyse"}


def test_gap_signature_empty_string():
    assert gap_signature("") == frozenset()


def test_gap_signature_only_stopwords():
    assert gap_signature("de het een van") == frozenset()


# ── best_coverage ─────────────────────────────────────────────────────────────

def test_full_coverage_when_role_contains_all_gap_terms():
    recs = _FakeRecords([_rec("r", purpose="kwartaal analyse bezoekers locale")])
    gap = gap_signature("kwartaal analyse bezoekers locale")
    assert best_coverage(gap, recs) == pytest.approx(1.0)


def test_zero_coverage_when_no_overlap():
    recs = _FakeRecords([_rec("r", purpose="volledig andere domein woorden")])
    gap = gap_signature("kwartaal analyse bezoekers")
    assert best_coverage(gap, recs) == pytest.approx(0.0)


def test_archived_records_ignored():
    rec = _rec("r", purpose="kwartaal analyse bezoekers locale")
    rec.archived = True
    gap = gap_signature("kwartaal analyse bezoekers locale")
    assert best_coverage(gap, _FakeRecords([rec])) == pytest.approx(0.0)


def test_no_records_returns_zero():
    gap = gap_signature("kwartaal analyse")
    assert best_coverage(gap, _FakeRecords([])) == pytest.approx(0.0)


def test_none_records_returns_zero():
    gap = gap_signature("kwartaal analyse")
    assert best_coverage(gap, None) == pytest.approx(0.0)


