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
        records=None, data_dir=str(tmp_path),
        projects=ProjectLedger(str(tmp_path / "projects.json")),
        strategy={"north_star": {"metric": "pairs_sold", "target": 1000000,
                                 "unit": "paar", "horizon": "per jaar"},
                  "goals": [{"description": "1000 paar Q4", "active": True}]})
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s._opportunity_reflex = types.MethodType(Inhabitant._opportunity_reflex, s)
    s._raise_opportunity_governance = types.MethodType(Inhabitant._raise_opportunity_governance, s)
    s._rejected_opportunities = types.MethodType(Inhabitant._rejected_opportunities, s)
    return s


def test_reflex_project_publiceert_kans_geen_autoproject(tmp_path):
    """Mens-poort: een project-kans wordt GEEN project maar een opportunity_sensed-event
    (beslissing voor de mens), mét een WAT in gewone taal. Geen autonoom werk."""
    s = _stub(tmp_path)
    resp = ("TYPE: project\nTITEL: Reviews tonen op de productpagina\n"
            "WAT: We laten op elke productpagina de sterren en korte reviews van kopers zien, "
            "zodat nieuwe bezoekers zien dat anderen blij zijn met de schoenen.\n"
            "WAAROM: Mensen kopen eerder als ze zien dat anderen tevreden zijn.\n"
            "EFFECT: 80\nEFFORT: 2\nCONFIDENCE: 0.7")
    with patch("nooch_village.llm.reason", return_value=resp):
        s._opportunity_reflex()
    assert s.context.projects.all() == []                  # NIET autonoom gequeued
    opp = [e for e in s._events if e.name == "opportunity_sensed"]
    assert len(opp) == 1
    assert opp[0].data["title"] == "Reviews tonen op de productpagina"
    assert "sterren en korte reviews" in opp[0].data["wat"]      # mensentaal-WAT
    assert opp[0].data["business_case"]["effect"] == 80


def test_reflex_leest_afgewezen_kansen(tmp_path, monkeypatch):
    """De reflex voert eerder-afgewezen kansen + reden terug in de prompt (leerlus)."""
    import json as _json
    inbox = {"x": {"id": "x", "type": "opportunity", "subject": "Adverteren op Google",
                   "status": "rejected", "resolution": "advertising is verboden via policy",
                   "context": {"by": "analyst"}}}
    (tmp_path / "human_inbox.json").write_text(_json.dumps(inbox))
    s = _stub(tmp_path)
    seen = {}

    def _capture(p):
        seen["p"] = p
        return None
    monkeypatch.setattr("nooch_village.llm.reason", _capture)
    s._opportunity_reflex()
    assert "Adverteren op Google" in seen["p"] and "advertising is verboden" in seen["p"]


def test_reflex_amend_role_wordt_voorstel(tmp_path):
    s = _stub(tmp_path)
    resp = ("TYPE: amend_role\nTITEL: Kleine proefjes op de productpagina\n"
            "WAT: We proberen twee versies van de productpagina uit en kijken welke meer "
            "verkopen oplevert.\nWAAROM: Door te meten weten we wat echt werkt.\n"
            "EFFECT: m\nEFFORT: 3\nCONFIDENCE: 0.5")
    with patch("nooch_village.llm.reason", return_value=resp):
        s._opportunity_reflex()
    raised = [e for e in s._events if e.name == "proposal_raised"]
    assert len(raised) == 1
    prop = raised[0].data["proposal"]
    assert prop["change"]["kind"] == "amend_role"
    assert prop["business_case"]["effect"] == 10        # tier 'm'
    assert prop["hypothesis"].startswith("Door te meten")


def test_reflex_fail_closed_zonder_llm(tmp_path):
    s = _stub(tmp_path)
    with patch("nooch_village.llm.reason", return_value=None):
        s._opportunity_reflex()
    assert s.context.projects.all() == [] and s._events == []
