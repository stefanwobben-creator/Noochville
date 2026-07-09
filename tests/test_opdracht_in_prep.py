"""De opdracht (p['description']) bereikt de prep-prompt van de daemon.

Sectie direct ná het projectdoel, vóór de skill-catalogus; leeg → geen kop; hard begrensd op
description_context_max_chars; corrupt veld → fail-closed (prep loopt door zonder sectie).
Prompt-capture, geen echte LLM.
"""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry

_HEADER = "Opdracht van de mens (de checklist moet hieraan voldoen):"


def _inhabitant(tmp_path, **settings):
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0", **settings},
                          data_dir=str(tmp_path), projects=None, records=None)
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="x", accountabilities=["research"], domains=[], skills=[]),
                 source="sensed")
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)


def _capture_prompt(inh, goal, **kw):
    cap = {}
    def fake_reason(prompt, **k):
        cap["prompt"] = prompt
        return (None, "mock") if k.get("return_tier") else None
    with patch("nooch_village.llm.reason", side_effect=fake_reason):
        inh._plan_checklist(goal, **kw)
    return cap.get("prompt", "")


# 1. Met description → sectie in de prompt, ná het doel en vóór de catalogus
def test_1_opdracht_in_prompt_op_juiste_plek(tmp_path):
    inh = _inhabitant(tmp_path)
    prompt = _capture_prompt(inh, "Verbeter de homepage",
                             description="De tekst moet in het Engels en vegan benadrukken")
    assert _HEADER in prompt
    assert "De tekst moet in het Engels en vegan benadrukken" in prompt
    # positie: ná Projectdoel, vóór de skill-catalogus (stuurt de planning)
    assert prompt.index("Projectdoel") < prompt.index(_HEADER) < prompt.index("Jouw skills")


# 2. Zonder description → geen sectie (geen lege kop)
def test_2_zonder_description_geen_sectie(tmp_path):
    inh = _inhabitant(tmp_path)
    prompt = _capture_prompt(inh, "Verbeter de homepage")           # description niet meegegeven
    assert _HEADER not in prompt
    prompt2 = _capture_prompt(inh, "Verbeter de homepage", description="   ")   # alleen whitespace
    assert _HEADER not in prompt2


# 3. Description > max_chars → afgekapt (nette grens + …)
def test_3_afkap_op_max_chars(tmp_path):
    inh = _inhabitant(tmp_path, description_context_max_chars="15")
    prompt = _capture_prompt(inh, "doel",
                             description="begin midden zeer lang einde-uniek-woord")
    assert _HEADER in prompt and "…" in prompt
    assert "einde-uniek-woord" not in prompt                        # het staartwoord is weggekapt
    assert "begin" in prompt                                        # de kop bleef


# 4. Corrupt veld → fail-closed: prep loopt door zonder sectie, geen exception
def test_4_corrupt_veld_failclosed(tmp_path):
    inh = _inhabitant(tmp_path)
    prompt = _capture_prompt(inh, "doel", description=["corrupt", "geen", "string"])  # niet-string
    assert _HEADER not in prompt                                    # geen sectie, geen crash
    # directe unit op de helper: elk type → "" i.p.v. exception
    assert inh._opdracht_section(None) == "" and inh._opdracht_section({"x": 1}) == ""
