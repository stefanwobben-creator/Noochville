"""Facilitator-rolreview: per rol één verbetervoorstel als kans in de inbox (mens-gated),
gegrond in de referentiebank. Kernrollen/cirkels worden overgeslagen. Fail-closed zonder LLM."""
from __future__ import annotations

from nooch_village.governance import Records
from nooch_village.governance_examples import GovernanceExamples
from nooch_village.governance_review import review_role, review_all_roles, _parse_review
from nooch_village.human_inbox import HumanInbox
from nooch_village.models import Record, RoleDefinition, RecordType


def test_parse_review():
    assert _parse_review("SUGGESTIE: Bewaken van X\nWAAROM: helderder") == {
        "suggestion": "Bewaken van X", "why": "helderder"}
    assert _parse_review("GEEN") is None
    assert _parse_review("") is None


def test_parse_review_volledige_meerregelige_suggestie():
    """Een voorstel als 'Vervang X door:\\n<nieuwe tekst>' mag NIET afkappen op 'door:'."""
    txt = ("SUGGESTIE: Vervang de accountability 'tijdgeest-signalen publiceren' door:\n"
           "Signaleren van culturele taalverschuivingen die de missie raken\n"
           "WAAROM: korter en in de -en-vorm")
    out = _parse_review(txt)
    assert "Signaleren van culturele taalverschuivingen" in out["suggestion"]
    assert out["suggestion"].endswith("raken")               # volledige zin, niet 'door:'
    assert out["why"].startswith("korter")


def test_review_role_failclosed():
    role = {"id": "scout", "purpose": "markt observeren", "accountabilities": ["markt kijken"]}
    assert review_role(role, "", llm_reason=lambda p: None) is None


def test_review_role_levert_suggestie():
    role = {"id": "scout", "purpose": "markt observeren", "accountabilities": ["markt kijken"]}
    out = review_role(role, "(voorbeelden)",
                      llm_reason=lambda p: "SUGGESTIE: Volgen van concurrenten en markttrends\n"
                                           "WAAROM: -en-vorm en concreter")
    assert out["suggestion"].startswith("Volgen van")


def _recs(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    r.put(Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                 definition=RoleDefinition(purpose="Nooch"), source="seed"))
    r.put(Record(id="facilitator", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="proces"), source="seed"))
    r.put(Record(id="scout", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="markt observeren",
                                           accountabilities=["markt kijken"]), source="seed"))
    r.put(Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="woorden cureren"), source="seed"))
    return r


def test_review_all_roles_vult_inbox_en_skipt_kernrollen(tmp_path):
    recs = _recs(tmp_path)
    ge = GovernanceExamples(str(tmp_path / "ge.json"))   # leeg → grounding fail-closed, prima
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    res = review_all_roles(recs, ge, inbox,
                           llm_reason=lambda p: "SUGGESTIE: Aanscherpen van dit aandachtsgebied\n"
                                                "WAAROM: helderder")
    # facilitator (kernrol) + wortelcirkel overgeslagen; scout + librarian gereviewd
    assert res["reviewed"] == 2 and res["proposed"] == 2
    opps = [i for i in inbox.all() if i["type"] == "opportunity"]
    assert len(opps) == 2
    assert all(o["context"]["by"] == "facilitator" for o in opps)
    assert any("scout" in o["subject"] for o in opps)
    assert not any("facilitator" in o["subject"] for o in opps)   # kernrol niet gereviewd


def test_review_all_roles_failclosed_geen_voorstellen(tmp_path):
    recs = _recs(tmp_path)
    ge = GovernanceExamples(str(tmp_path / "ge.json"))
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    res = review_all_roles(recs, ge, inbox, llm_reason=lambda p: None)
    assert res["reviewed"] == 2 and res["proposed"] == 0
    assert [i for i in inbox.all() if i["type"] == "opportunity"] == []
