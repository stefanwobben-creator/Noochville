"""Fase 2 — opportunity-reflex: elke rol bedenkt periodiek één onderbouwde kans (project /
rol-uitbreiding / nieuwe rol) met hypothese + business-case, die op de backlog landt.
Sensen + voorstellen, nooit zelf uitvoeren. Thread-vrij, LLM gemockt."""
from __future__ import annotations
import types
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.inhabitant import Inhabitant, _parse_opportunity
from nooch_village.projects import ProjectLedger


def test_parse_opportunity():
    o = _parse_opportunity(
        "TYPE: project\nTITEL: Reviews oogsten op de PDP\n"
        "HYPOTHESE: als we reviews tonen, dan +conversie omdat sociaal bewijs\n"
        "EFFECT: l\nEFFORT: 2\nCONFIDENCE: 0.7\nRATIONALE: sociaal bewijs werkt")
    assert o["type"] == "project" and o["titel"].startswith("Reviews")
    assert o["effort"] == 2 and o["confidence"] == 0.7 and o["effect"] == "l"


def _stub(tmp_path, *, skills=()):
    s = SimpleNamespace(id="analyst", log=__import__("logging").getLogger("t"))
    s.dna = SimpleNamespace(purpose="groei-analyse", accountabilities=["bezoekers volgen"],
                            skills=list(skills))
    s.context = SimpleNamespace(
        records=None,
        projects=ProjectLedger(str(tmp_path / "projects.json")),
        strategy={"north_star": {"metric": "pairs_sold", "target": 1000000,
                                 "unit": "paar", "horizon": "per jaar"},
                  "goals": [{"description": "1000 paar Q4", "active": True}]})
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s._opportunity_reflex = types.MethodType(Inhabitant._opportunity_reflex, s)
    s._raise_opportunity_governance = types.MethodType(Inhabitant._raise_opportunity_governance, s)
    return s


def test_reflex_project_landt_in_backlog(tmp_path):
    s = _stub(tmp_path)
    resp = ("TYPE: project\nTITEL: Reviews oogsten op de PDP\n"
            "HYPOTHESE: reviews → conversie\nEFFECT: 80\nEFFORT: 2\nCONFIDENCE: 0.7\n"
            "RATIONALE: sociaal bewijs")
    with patch("nooch_village.llm.reason", return_value=resp):
        s._opportunity_reflex()
    projects = s.context.projects.all()
    assert len(projects) == 1
    p = projects[0]
    assert p["scope"] == "Reviews oogsten op de PDP"
    assert p["business_case"]["effect"] == 80 and p["hypothesis"] == "reviews → conversie"

    # dedup: zelfde kans opnieuw → geen tweede project
    with patch("nooch_village.llm.reason", return_value=resp):
        s._opportunity_reflex()
    assert len(s.context.projects.all()) == 1


def test_reflex_amend_role_wordt_voorstel(tmp_path):
    s = _stub(tmp_path)
    resp = ("TYPE: amend_role\nTITEL: conversie-experimenten op de PDP draaien\n"
            "HYPOTHESE: A/B-tests → hogere conversie\nEFFECT: m\nEFFORT: 3\nCONFIDENCE: 0.5\n"
            "RATIONALE: meten is weten")
    with patch("nooch_village.llm.reason", return_value=resp):
        s._opportunity_reflex()
    raised = [e for e in s._events if e.name == "proposal_raised"]
    assert len(raised) == 1
    prop = raised[0].data["proposal"]
    assert prop["change"]["kind"] == "amend_role"
    assert prop["business_case"]["effect"] == 10        # tier 'm'
    assert prop["hypothesis"].startswith("A/B")


def test_reflex_fail_closed_zonder_llm(tmp_path):
    s = _stub(tmp_path)
    with patch("nooch_village.llm.reason", return_value=None):
        s._opportunity_reflex()
    assert s.context.projects.all() == [] and s._events == []
