"""Tests voor ContentSchrijvenSkill (Fase 2 brokje 11). Thread-vrij, LLM gemockt.

Scope 57 (skill-review 12-09-2026): de prompt is Engels (de inhoudslaag is sinds 06-09 Engels), de
draft is het enige inhoudsveld (`_claim_insight_ids`/`_kind` zijn run-administratie), en 'geen
model' of 'geen materiaal' is een `error` — geen succes zonder tekst. De asserts op de Nederlandse
prompt-zinnen en op `claim_insight_ids` legden dat oude gedrag vast en zijn daarom mee omgezet."""
from __future__ import annotations

from unittest.mock import patch

from nooch_village.skills_impl.content_schrijven import ContentSchrijvenSkill

_CARDS = [
    {"id": "a", "word": "barefoot shoes", "claim": "Barefoot shoes are rising in demand.", "status": "verified"},
    {"id": "b", "word": "green gap", "claim": "Intention stalls on the price premium.", "status": "unresolved"},
]


def _run(payload, mock_return="Een mooi stuk tekst.", context=None):
    skill = ContentSchrijvenSkill()
    with patch("nooch_village.llm.reason", return_value=mock_return) as mock:
        out = skill.run(payload, context=context)
    return out, mock


def test_levert_tekst_en_claim_ids():
    out, _ = _run({"cards": _CARDS, "kind": "blog"})
    assert out["text"] == "Een mooi stuk tekst."
    assert out["_claim_insight_ids"] == ["a", "b"]
    assert out["_kind"] == "blog"
    assert "claim_insight_ids" not in out and "kind" not in out      # geen inhoudssleutel naast de draft


def test_prompt_bevat_materiaal_en_soort():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    prompt = mock.call_args[0][0]
    assert "Intention stalls on the price premium." in prompt
    assert "blog" in prompt


def test_strikte_soort_vraagt_alleen_verified_als_claim():
    _, mock = _run({"cards": _CARDS, "kind": "sales_page"})
    prompt = mock.call_args[0][0]
    assert "use ONLY verified cards as hard claims" in prompt


def test_blog_is_verkennend_niet_strikt():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    prompt = mock.call_args[0][0]
    assert "exploratively" in prompt
    assert "use ONLY verified cards as hard claims" not in prompt


def test_engels_default_in_prompt():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    assert "Write your answer in English." in mock.call_args[0][0]


def test_geen_llm_is_een_fout_geen_lege_tekst():
    """Geen model = fout (item blijft open), niet 'gelukt met text=None'."""
    out, _ = _run({"cards": _CARDS, "kind": "blog"}, mock_return=None)
    assert "error" in out and "text" not in out


def test_geen_kaarten_is_een_fout():
    out, _ = _run({"cards": [], "kind": "blog"})
    assert "error" in out and "cards" in out["error"]


# ── brief (lezer + emotie), regels uit context, eerste-draft-framing ──────────

def test_brief_lezer_en_emotie_in_prompt():
    _, mock = _run({"cards": _CARDS, "kind": "blog",
                    "audience": "Yasmine, design-first",
                    "desired_outcome": "excited about the look"})
    prompt = mock.call_args[0][0]
    assert "Yasmine, design-first" in prompt
    assert "excited about the look" in prompt


def test_copyregels_uit_context_in_prompt():
    from types import SimpleNamespace
    ctx = SimpleNamespace(copy_rules="MERKREGELS: burger niet consument.")
    _, mock = _run({"cards": _CARDS, "kind": "blog"}, context=ctx)
    assert "MERKREGELS: burger niet consument." in mock.call_args[0][0]


def test_eerste_draft_framing_en_kopopties():
    _, mock = _run({"cards": _CARDS, "kind": "blog"})
    prompt = mock.call_args[0][0]
    assert "FIRST DRAFT" in prompt
    assert "headline options" in prompt
