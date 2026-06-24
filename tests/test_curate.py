"""Tests voor de curate-engine. Geen netwerk: reason wordt geïnjecteerd."""
from __future__ import annotations

from nooch_village.curate import (
    build_curate_prompt, parse_cards, validate_card, finalize_card, curate,
)


# ── prompt ────────────────────────────────────────────────────────────────────

def test_prompt_dwingt_engels_en_atomair_af():
    p = build_curate_prompt("ruwe tekst", ["bestaand_id"])
    assert "ENGLISH ONLY" in p
    assert "ATOMIC" in p
    assert "bestaand_id" in p


# ── parse_cards ───────────────────────────────────────────────────────────────

def test_parse_schone_json():
    assert parse_cards('[{"id":"a","claim":"x"}]') == [{"id": "a", "claim": "x"}]


def test_parse_met_codefences_en_proza():
    txt = "Sure!\n```json\n[{\"id\":\"a\",\"claim\":\"x\"}]\n```\nklaar"
    assert parse_cards(txt) == [{"id": "a", "claim": "x"}]


def test_parse_onparseerbaar_geeft_leeg():
    assert parse_cards("geen json hier") == []
    assert parse_cards(None) == []
    assert parse_cards("[kapot") == []


# ── validate_card ─────────────────────────────────────────────────────────────

def test_valid_compleet_kaartje():
    assert validate_card({"id": "vegan_shoes_demand", "claim": "x", "grounds": "y"}) is True


def test_invalid_zonder_grounds():
    assert validate_card({"id": "a", "claim": "x"}) is False


def test_invalid_zonder_claim():
    assert validate_card({"id": "a", "grounds": "y"}) is False


def test_invalid_id_geen_slug():
    assert validate_card({"id": "Niet Slug", "claim": "x", "grounds": "y"}) is False


# ── finalize_card ─────────────────────────────────────────────────────────────

def test_finalize_injecteert_vaste_velden():
    f = finalize_card({"id": "a", "claim": "x", "grounds": "y", "evidence_type": "measured"},
                      source="S", source_date="2026-06-24")
    assert f["source"] == "S" and f["source_date"] == "2026-06-24"
    assert f["status"] == "supported"
    assert f["evidence_type"] == "measured"


def test_finalize_onbekend_evidence_type_wordt_none():
    f = finalize_card({"id": "a", "claim": "x", "grounds": "y", "evidence_type": "rommel"},
                      source="S", source_date="2026-06-24")
    assert f["evidence_type"] is None


# ── curate (orkestratie) ──────────────────────────────────────────────────────

def test_curate_engels_atomair_uit_fuzzy():
    fake = lambda prompt: '[{"id":"consumer_declines","claim":"Consumer declines","grounds":"ngram"}]'
    cards = curate("consument daalt", source="harry", source_date="2026-06-24", reason_fn=fake)
    assert len(cards) == 1
    assert cards[0]["id"] == "consumer_declines"
    assert cards[0]["source"] == "harry"


def test_curate_dropt_incomplete_kaartjes():
    # tweede kaartje mist grounds → valt af
    fake = lambda p: '[{"id":"a","claim":"x","grounds":"y"},{"id":"b","claim":"z"}]'
    cards = curate("...", source="s", source_date="2026-06-24", reason_fn=fake)
    assert [c["id"] for c in cards] == ["a"]


def test_curate_geen_llm_geeft_leeg():
    assert curate("x", source="s", source_date="2026-06-24", reason_fn=lambda p: None) == []
