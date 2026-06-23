"""Tests voor ContentSchrijvenSkill (Fase 2 brokje 11). Thread-vrij, LLM gemockt."""
from __future__ import annotations

from unittest.mock import patch

from nooch_village.skills_impl.content_schrijven import ContentSchrijvenSkill

_CARDS = [
    {"id": "a", "word": "barefoot shoes", "claim": "Barefoot shoes are rising in demand.", "status": "verified"},
    {"id": "b", "word": "green gap", "claim": "Intention stalls on the price premium.", "status": "unresolved"},
]


def _run(payload, mock_return="Een mooi stuk tekst."):
    skill = ContentSchrijvenSkill()
    with patch("nooch_village.llm.reason", return_value=mock_return) as mock:
        out = skill.run(payload, context=None)
    return out, mock


def test_levert_tekst_en_claim_ids():
    out, _ = _run({"cards": _CARDS, "kind": "blog"})
    assert out["text"] == "Een mooi stuk tekst."
    assert out["claim_insight_ids"] == ["a", "b"]
    assert out["kind"] == "blog"


def test_prompt_bevat_materiaal_en_soort():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    prompt = mock.call_args[0][0]
    assert "Intention stalls on the price premium." in prompt
    assert "blog" in prompt


def test_strikte_soort_vraagt_alleen_verified_als_claim():
    _, mock = _run({"cards": _CARDS, "kind": "sales_page"})
    prompt = mock.call_args[0][0]
    assert "UITSLUITEND geverifieerde" in prompt


def test_blog_is_verkennend_niet_strikt():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    prompt = mock.call_args[0][0]
    assert "verkennend" in prompt
    assert "UITSLUITEND geverifieerde" not in prompt


def test_engels_default_in_prompt():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    assert "Write your answer in English." in mock.call_args[0][0]


def test_geen_llm_geeft_geen_tekst():
    out, _ = _run({"cards": _CARDS, "kind": "blog"}, mock_return=None)
    assert out["text"] is None


def test_geen_kaarten_geeft_geen_tekst():
    out, _ = _run({"cards": [], "kind": "blog"})
    assert out["text"] is None
