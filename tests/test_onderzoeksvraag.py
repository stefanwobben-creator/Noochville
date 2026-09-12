"""Tests voor OnderzoeksvraagSkill (Fase 1 brokje 4). Thread-vrij, LLM gemockt.

Legt vast: een geldige vraag komt eruit, de trend-term en claim staan in de prompt, en de drie
uitkomsten (scope 54): geen model → `error`; 'geen'/onparseerbaar/leeg → `no_data` + reason; en in
alle faalgevallen blijft `vraag` None voor de verdiep-lus in roles.py.

Tot scope 54 gaven alle vier de faalpaden `{"vraag": None}` — één antwoord voor drie oorzaken, en
"geen model" werd zo als "onderzocht, niets gevonden" afgevinkt. De tests hieronder zijn daarop
aangepast; het contract is nu JSON (`{"question": …}`), met de oude "VRAAG:"-regel als tolerantie.
"""
from __future__ import annotations

from unittest.mock import patch

from nooch_village.skills_impl.onderzoeksvraag import OnderzoeksvraagSkill, _vraag_uit

_KAART = {"word": "barefoot shoes", "claim": "barefoot schoenen stijgen al weken in zoekvraag"}


def _run(mock_return, payload=None):
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value=mock_return):
        return skill.run(payload or {"kaart": _KAART}, context=None)


def test_geldige_vraag_komt_eruit():
    out = _run('{"question": "Welke biomechanische voordelen drijven de opkomst van barefoot schoenen?"}')
    assert out["vraag"] == "Welke biomechanische voordelen drijven de opkomst van barefoot schoenen?"
    assert out["text"] == out["vraag"] and "error" not in out and not out.get("no_data")


def test_oude_regelvorm_blijft_werken():
    """Overgangs-tolerantie: een model dat de regelvorm teruggeeft, breekt de parser niet."""
    out = _run("VRAAG: Welke biomechanische voordelen drijven de opkomst van barefoot schoenen?")
    assert out["vraag"].startswith("Welke biomechanische")
    assert _vraag_uit("QUESTION: Why do people switch?") == "Why do people switch?"


def test_prompt_bevat_trend_en_claim_en_is_json_mode():
    """De afgeleide vraag moet op de échte trend-kaart slaan, niet generiek zijn — en de aanroep is
    JSON met een klein tokenbudget (één vraag hoeft geen 700 tokens)."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value='{"question": "iets"}') as mock:
        skill.run({"kaart": _KAART}, context=None)
    prompt = mock.call_args[0][0]
    assert "barefoot shoes" in prompt
    assert "stijgen al weken" in prompt
    assert mock.call_args.kwargs["json_mode"] is True
    assert mock.call_args.kwargs["max_tokens"] <= 200
    assert mock.call_args.kwargs["call_site"] == "skill_onderzoeksvraag"


def test_losse_word_en_claim_zonder_kaart():
    """Een projectplanner heeft zelden een kaart-dict; `word`/`claim` los werkt ook."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value='{"question": "Why?"}') as mock:
        out = skill.run({"word": "barefoot shoes", "claim": "rising"}, context=None)
    assert out["vraag"] == "Why?" and "barefoot shoes" in mock.call_args[0][0]


def test_geen_llm_is_een_fout_geen_leeg():
    """Scope 54: geen model laat het item OPEN (error), i.p.v. het als leeg af te vinken."""
    out = _run(None)
    assert out["vraag"] is None and "error" in out and not out.get("no_data")


def test_geen_zinvolle_vraag_is_no_data_met_reden():
    for antwoord in ('{"question": null}', '{"question": ""}', "VRAAG: geen",
                     "VRAAG: geen zinvolle vraag mogelijk"):
        out = _run(antwoord)
        assert out["vraag"] is None and out["no_data"] is True and "barefoot shoes" in out["reason"]
        assert "error" not in out


def test_onparseerbaar_antwoord_is_no_data():
    out = _run("Ik denk dat barefoot schoenen leuk zijn.")
    assert out["vraag"] is None and out.get("no_data") is True


def test_lege_vraag_is_no_data():
    out = _run("VRAAG:    ")
    assert out["vraag"] is None and out.get("no_data") is True


def test_kaart_als_string_wordt_bij_het_plannen_geweigerd():
    """Een string uit de planner gaf vroeger een AttributeError met een cryptische reden; nu zegt
    `validate_payload` het vóór de run, en `run` zelf valt terug op een nette fout."""
    s = OnderzoeksvraagSkill()
    assert s.validate_payload({"kaart": "barefoot shoes"}, None)
    assert s.validate_payload({"kaart": {"claim": "x"}}, None)
    assert s.validate_payload({"kaart": _KAART}, None) == []
    assert s.validate_payload({"word": "x"}, None) == []
    assert "error" in _run('{"question": "q"}', payload={"kaart": "barefoot shoes"})


def test_prompt_vraagt_engels_default():
    """De werktaal is Engels: zonder locale draagt de prompt de Engelse instructie."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value='{"question": "x"}') as mock:
        skill.run({"kaart": _KAART}, context=None)
    assert "Write your answer in English." in mock.call_args[0][0]


def test_prompt_respecteert_expliciete_locale():
    """Een expliciete locale wijkt af van de default."""
    skill = OnderzoeksvraagSkill()
    with patch("nooch_village.llm.reason", return_value='{"question": "x"}') as mock:
        skill.run({"kaart": _KAART, "locale": "nl"}, context=None)
    assert "Write your answer in Dutch." in mock.call_args[0][0]
