from __future__ import annotations
import logging
import pytest
from types import SimpleNamespace
from nooch_village.insight_ingest import insight_from_grounding, _slug
from nooch_village.insight import Insight, GroundingStatus
from nooch_village.notes_store import NotesStore


def test_assessment_levert_unresolved_insight():
    kaartje = insight_from_grounding("vegan", "Vegan schoenen zijn veelal plasticvrij.")
    assert kaartje is not None
    assert kaartje.status == GroundingStatus.UNRESOLVED
    assert kaartje.claim == "Vegan schoenen zijn veelal plasticvrij."


def test_leeg_assessment_levert_none():
    assert insight_from_grounding("vegan", "") is None
    assert insight_from_grounding("vegan", "   ") is None


def test_concept_id_op_kaartje():
    kaartje = insight_from_grounding("vegan", "Relevant voor de missie.", concept_id="vegan")
    assert kaartje is not None
    assert kaartje.concept_id == "vegan"


def test_evidence_titels_in_reference_en_deterministische_id():
    evidence = [
        {"title": "Paper A", "year": 2020},
        {"title": "Paper B", "year": 2021},
        {"title": "Paper C", "year": 2022},
        {"title": "Paper D", "year": 2023},
    ]
    kaartje1 = insight_from_grounding("duurzaam", "Duurzaamheid groeit.", evidence=evidence)
    kaartje2 = insight_from_grounding("duurzaam", "Andere tekst.", evidence=evidence)
    assert kaartje1 is not None
    assert "Paper A" in kaartje1.reference
    assert "Paper B" in kaartje1.reference
    assert "Paper C" in kaartje1.reference
    assert "Paper D" not in kaartje1.reference  # alleen eerste 3
    assert kaartje1.id == kaartje2.id            # deterministisch op word


def test_word_veld_gevuld_na_grounding():
    kaartje = insight_from_grounding("vegan shoes", "Relevant voor missie-schoenen.")
    assert kaartje is not None
    assert kaartje.word == "vegan shoes"


def test_insight_zonder_word_veld_laadt_backward_compat():
    from nooch_village.insight import Insight
    kaartje = Insight(id="test_id", claim="een claim", source="handmatig")
    assert kaartje.word is None










# ── Tests voor Librarian dag-reflectie (_on_dag_eindigt) ─────────────────────

def _dag_eindigt_event():
    from nooch_village.event_bus import Event
    return Event("dag_eindigt", {"label": "2026-06-22"}, "facilitator")






