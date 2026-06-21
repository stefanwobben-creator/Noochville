from __future__ import annotations
import pytest
from nooch_village.concept_suggest import suggest_concept

CONCEPTS = [
    {
        "concept_id": "vegan",
        "words": {"nl": "veganistisch", "en": "vegan"},
        "rationale": "Geen dierenleer is beleidsregel.",
    },
    {
        "concept_id": "sustainable",
        "words": {"nl": "duurzaam", "en": "sustainable"},
        "rationale": "Duurzaamheid als missie-kern.",
    },
]


def test_geldig_concept_id_wordt_teruggegeven():
    result = suggest_concept("vegan schoenen", CONCEPTS, reason_fn=lambda p: "vegan")
    assert result == "vegan"


def test_geen_antwoord_levert_none():
    result = suggest_concept("iets", CONCEPTS, reason_fn=lambda p: "GEEN")
    assert result is None


def test_hallucinatie_concept_id_levert_none():
    result = suggest_concept("iets", CONCEPTS, reason_fn=lambda p: "plastic_free")
    assert result is None


def test_reason_fn_none_levert_none():
    result = suggest_concept("iets", CONCEPTS, reason_fn=lambda p: None)
    assert result is None


def test_lege_concepten_lijst_levert_none():
    result = suggest_concept("vegan schoenen", [], reason_fn=lambda p: "vegan")
    assert result is None


def test_whitespace_rond_antwoord_wordt_gestript():
    result = suggest_concept("duurzame schoenen", CONCEPTS, reason_fn=lambda p: "  sustainable  ")
    assert result == "sustainable"
