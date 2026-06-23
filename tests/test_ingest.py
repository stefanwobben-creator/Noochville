"""Tests voor ingest_insights: mens-gecureerde insights in de kennislaag. Thread-vrij."""
from __future__ import annotations

from nooch_village.ingest import ingest_insights
from nooch_village.notes_store import NotesStore


def _items():
    return [
        {"id": "a", "claim": "Claim A", "source": "survey.xlsx",
         "source_date": "2025-10-01", "links_to": [], "tags": ["x"]},
        {"id": "b", "claim": "Claim B", "source": "survey.xlsx",
         "source_date": "2025-10-01", "links_to": ["a"], "tags": []},
    ]


def test_voegt_kaartjes_toe_en_legt_link(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    res = ingest_insights(notes, _items())
    assert set(res["added"]) == {"a", "b"}
    assert res["skipped"] == []
    assert res["linked"] == 1
    b = notes.get("b")
    assert b is not None and b.claim == "Claim B"
    assert b.links_to == ["a"]                      # link gelegd via notes.link
    assert notes.get("a").tags == ["x"]


def test_dedup_op_id_overschrijft_niet(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    ingest_insights(notes, _items())
    res = ingest_insights(notes, _items())          # tweede keer: alles bestaat al
    assert res["added"] == []
    assert set(res["skipped"]) == {"a", "b"}
    assert len(notes.all()) == 2                     # geen duplicaten


def test_link_naar_onbestaand_kaartje_wordt_overgeslagen(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    res = ingest_insights(notes, [
        {"id": "x", "claim": "C", "source": "s", "links_to": ["bestaat_niet"]},
    ])
    assert res["added"] == ["x"]
    assert res["linked"] == 0                        # fail-closed: geen dangling link
    assert notes.get("x").links_to == []


def test_kaartjes_komen_op_unresolved_binnen(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    ingest_insights(notes, _items())
    from nooch_village.insight import GroundingStatus
    assert notes.get("a").status == GroundingStatus.UNRESOLVED


def test_rijke_velden_worden_doorgegeven(tmp_path):
    """status/grounds/evidence_type uit het item komen op het kaartje terecht."""
    from nooch_village.insight import GroundingStatus, EvidenceType
    notes = NotesStore(str(tmp_path / "notes.json"))
    res = ingest_insights(notes, [{
        "id": "m", "claim": "Gemeten feit", "source": "KE",
        "status": "supported", "evidence_type": "measured",
        "grounds": "vol=33100 (GB, jun 2026)", "tags": ["seo"],
    }])
    assert res["added"] == ["m"]
    m = notes.get("m")
    assert m.status == GroundingStatus.SUPPORTED
    assert m.evidence_type == EvidenceType.MEASURED
    assert m.grounds == "vol=33100 (GB, jun 2026)"


def test_onbekende_sleutel_wordt_genegeerd(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    res = ingest_insights(notes, [
        {"id": "z", "claim": "C", "source": "s", "rommel": "negeer mij"},
    ])
    assert res["added"] == ["z"]
    assert notes.get("z") is not None
