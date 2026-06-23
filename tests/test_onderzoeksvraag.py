"""Tests voor OnderzoeksvraagSkill (Fase 1 brokje 4). Thread-vrij, LLM gemockt.

Legt vast: een geldige vraag komt eruit, de trend-term en claim staan in de prompt,
en alle vier de fail-closed-paden (geen LLM, 'geen', onparseerbaar, leeg) geven None.
"""
from __future__ import annotations

from unittest.mock import patch

from nooch_village.skills_impl.onderzoeksvraag import OnderzoeksvraagSkill

_KAART = {"word": "barefoot shoes", "claim": "barefoot schoenen stijgen al weken in zoekvraag"}


def _run(mock_return):
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value=mock_return):
        return skill.run({"kaart": _KAART}, context=None)


def test_geldige_vraag_komt_eruit():
    out = _run("VRAAG: Welke biomechanische voordelen drijven de opkomst van barefoot schoenen?")
    assert out["vraag"] == "Welke biomechanische voordelen drijven de opkomst van barefoot schoenen?"


def test_prompt_bevat_trend_en_claim():
    """De afgeleide vraag moet op de échte trend-kaart slaan, niet generiek zijn."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value="VRAAG: iets") as mock:
        skill.run({"kaart": _KAART}, context=None)
    prompt = mock.call_args[0][0]
    assert "barefoot shoes" in prompt
    assert "stijgen al weken" in prompt


def test_geen_llm_geeft_none():
    assert _run(None)["vraag"] is None


def test_geen_zinvolle_vraag_geeft_none():
    assert _run("VRAAG: geen")["vraag"] is None
    assert _run("VRAAG: geen zinvolle vraag mogelijk")["vraag"] is None


def test_onparseerbaar_antwoord_geeft_none():
    assert _run("Ik denk dat barefoot schoenen leuk zijn.")["vraag"] is None


def test_lege_vraag_geeft_none():
    assert _run("VRAAG:    ")["vraag"] is None


def test_prompt_vraagt_engels_default():
    """De werktaal is Engels: zonder locale draagt de prompt de Engelse instructie."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value="VRAAG: x") as mock:
        skill.run({"kaart": _KAART}, context=None)
    assert "Write your answer in English." in mock.call_args[0][0]


def test_prompt_respecteert_expliciete_locale():
    """Een expliciete locale wijkt af van de default."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value="VRAAG: x") as mock:
        skill.run({"kaart": _KAART, "locale": "nl"}, context=None)
    assert "Write your answer in Dutch." in mock.call_args[0][0]
