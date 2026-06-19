"""Tests voor keyword_batch — pure functies, geen I/O."""
from __future__ import annotations
import pytest
from nooch_village.keyword_batch import propose_batch
from nooch_village.keyword_matrix import core_candidates, longtail_candidates, MARKET_LANGUAGES


def test_propose_batch_nl_heeft_alle_keys_en_defaults():
    result = propose_batch("nl")
    assert result["market"] == "nl"
    assert result["country"] == "nl"
    assert result["data_source"] == "cli"
    assert result["tier"] == "core"
    assert "candidates" in result
    assert "estimated_credits" in result


def test_estimated_credits_gelijk_aan_len_candidates():
    for market in MARKET_LANGUAGES:
        for tier in ("core", "longtail"):
            result = propose_batch(market, tier=tier)
            assert result["estimated_credits"] == len(result["candidates"])


def test_longtail_meer_kandidaten_dan_core_en_bevat_drie_woord_term():
    core = propose_batch("nl", tier="core")
    longtail = propose_batch("nl", tier="longtail")
    assert len(longtail["candidates"]) > len(core["candidates"])
    assert any(len(t.split()) == 3 for t in longtail["candidates"])


def test_candidates_de_exact_gelijk_aan_matrix():
    result = propose_batch("de")
    assert result["candidates"] == core_candidates("de")


def test_onbekende_tier_en_markt_raises_valueerror():
    with pytest.raises(ValueError, match="tier"):
        propose_batch("nl", tier="premium")
    with pytest.raises(ValueError, match="markt"):
        propose_batch("xx")


def test_estimated_credits_binnen_skill_cap():
    for market in MARKET_LANGUAGES:
        for tier in ("core", "longtail"):
            result = propose_batch(market, tier=tier)
            assert result["estimated_credits"] <= 100, (
                f"{market}/{tier}: {result['estimated_credits']} credits > skill-cap 100"
            )
