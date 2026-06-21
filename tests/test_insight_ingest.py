from __future__ import annotations
import pytest
from nooch_village.insight_ingest import insight_from_grounding, _slug
from nooch_village.insight import GroundingStatus


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
