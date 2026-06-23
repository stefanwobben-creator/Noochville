"""Tests voor ContentCheckSkill (Fase 2 brokje 12). Thread-vrij, LLM gemockt.

De harde claim-gate (per publicatie-soort) plus de LLM-toets tegen de copy_rules.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.content_check import ContentCheckSkill
from nooch_village.insight import Insight, GroundingStatus, EvidenceType
from nooch_village.notes_store import NotesStore


def _store(tmp_path):
    s = NotesStore(str(tmp_path / "notes.json"))
    s.add(Insight(id="v", claim="een verified claim", source="t",
                  status=GroundingStatus.VERIFIED, grounds="g", warrant="w",
                  rebuttal="r", evidence_type=EvidenceType.PEER_REVIEWED))
    s.add(Insight(id="u", claim="een onbewezen claim", source="t"))  # unresolved
    return s


def _run(tmp_path, payload, mock_return="OK", copy_rules="REGELS"):
    skill = ContentCheckSkill()
    ctx = SimpleNamespace(notes=_store(tmp_path), copy_rules=copy_rules)
    with patch("nooch_village.llm.reason", return_value=mock_return) as mock:
        out = skill.run(payload, context=ctx)
    return out, mock


def test_verboden_woord_in_sales_blokkeert(tmp_path):
    out, _ = _run(tmp_path, {"text": "Gemaakt van plastic en trots.",
                             "claim_insight_ids": [], "kind": "sales_page"})
    assert "plastic" in out["forbidden_words"]
    assert out["gate_ok"] is False


def test_onbewezen_claim_in_sales_blokkeert(tmp_path):
    out, _ = _run(tmp_path, {"text": "Een schone tekst.",
                             "claim_insight_ids": ["u"], "kind": "sales_page"})
    assert any(ci["insight_id"] == "u" for ci in out["claim_issues"])
    assert out["gate_ok"] is False


def test_verified_claim_schone_sales_is_ok(tmp_path):
    out, _ = _run(tmp_path, {"text": "Een schone tekst.",
                             "claim_insight_ids": ["v"], "kind": "sales_page"})
    assert out["forbidden_words"] == []
    assert out["claim_issues"] == []
    assert out["gate_ok"] is True


def test_blog_laat_onbewezen_claim_door(tmp_path):
    """Blog is niet streng: onbewezen claims worden niet geblokkeerd."""
    out, _ = _run(tmp_path, {"text": "Gemaakt van plastic.",
                             "claim_insight_ids": ["u"], "kind": "blog"})
    assert out["gate_ok"] is True


def test_llm_suggesties_komen_terug(tmp_path):
    out, _ = _run(tmp_path, {"text": "Tekst.", "claim_insight_ids": [], "kind": "blog"},
                  mock_return="Te lang, en mist de smirk-check.")
    assert out["suggestions"] == "Te lang, en mist de smirk-check."


def test_geen_llm_geen_suggesties_maar_gate_blijft(tmp_path):
    out, _ = _run(tmp_path, {"text": "Gemaakt van plastic.", "claim_insight_ids": [],
                             "kind": "sales_page"}, mock_return=None)
    assert out["suggestions"] is None
    assert "plastic" in out["forbidden_words"]   # harde gate werkt zonder LLM
    assert out["gate_ok"] is False
