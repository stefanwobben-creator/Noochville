"""`plan_offers`: de cockpit-side skill-match (LLM gestubd), machine-check tegen DNA, fail-closed.

SINDS 15 OKTOBER 2026 alleen nog in gebruik door de @mention-reply (`cockpit2._dna_skill_for`). Het
stille aanbod bij een checklist-item ("can pick this up"), het accepteren en de knop zijn weg, samen
met hun toetsen: de uitvoerder waarvoor ze bestonden bestaat sinds #516 niet meer.
"""
from __future__ import annotations

from unittest.mock import patch

from nooch_village.skill_match import plan_offers
from nooch_village.registry_factory import shared_registry
from nooch_village.models import Record, RoleDefinition, RecordType

_TITLE = "Uitvoerplan"


def _owner(skills):
    return Record(id="mother_earth__nooch__website_developer", type=RecordType.ROLE, parent="mother_earth__nooch",
                  definition=RoleDefinition(purpose="p", accountabilities=["seo"], domains=[], skills=skills),
                  source="seed")


def _fake_reason(payload_json):
    def _r(prompt, **k):
        return payload_json
    return _r


# ── plan_offers ────────────────────────────────────────────────────────────────
def test_plan_offers_match():
    rec = _owner(["openalex_evidence"])
    js = '{"matches":[{"skill":"openalex_evidence","payload":{"term":"hennep"}}]}'
    with patch("nooch_village.llm.reason", side_effect=_fake_reason(js)):
        out = plan_offers(rec, ["onderzoek hennep-claims"], shared_registry())
    assert len(out) == 1 and out[0]["skill"] == "openalex_evidence"
    assert out[0]["payload"] == {"term": "hennep"} and isinstance(out[0]["payload_ok"], bool)


def test_plan_offers_skill_niet_in_dna_wordt_none():
    rec = _owner(["openalex_evidence"])
    js = '{"matches":[{"skill":"verzonnen_skill","payload":{}}]}'   # buiten de harde DNA-lijst
    with patch("nooch_village.llm.reason", side_effect=_fake_reason(js)):
        out = plan_offers(rec, ["iets"], shared_registry())
    assert out == [None]


def test_plan_offers_geen_dna_skills():
    with patch("nooch_village.llm.reason", side_effect=_fake_reason("x")):
        assert plan_offers(_owner([]), ["iets"], shared_registry()) == [None]


def test_plan_offers_owner_none_en_llm_none_en_exceptie():
    assert plan_offers(None, ["a", "b"], shared_registry()) == [None, None]
    with patch("nooch_village.llm.reason", side_effect=_fake_reason(None)):     # LLM gaf niets
        assert plan_offers(_owner(["openalex_evidence"]), ["a"], shared_registry()) == [None]
    def _boom(prompt, **k):
        raise RuntimeError("stuk")
    with patch("nooch_village.llm.reason", side_effect=_boom):                  # exceptie → fail-closed
        assert plan_offers(_owner(["openalex_evidence"]), ["a"], shared_registry()) == [None]


# ── observability: elke stille fail-closed logt nu een STABIELE refuse-code ──────
def _codes(caplog):
    return " ".join(r.getMessage() for r in caplog.records)


def test_refuse_plan_offers_dna_none_exc(caplog):
    with caplog.at_level("WARNING", logger="nooch.refuse"):
        plan_offers(_owner([]), ["x"], shared_registry())                          # geen DNA
        with patch("nooch_village.llm.reason", side_effect=_fake_reason(None)):     # LLM leeg
            plan_offers(_owner(["openalex_evidence"]), ["x"], shared_registry())
        def _boom(prompt, **k):
            raise RuntimeError("stuk")
        with patch("nooch_village.llm.reason", side_effect=_boom):                  # exceptie
            plan_offers(_owner(["openalex_evidence"]), ["x"], shared_registry())
    m = _codes(caplog)
    assert "OFFER_NO_DNA" in m and "OFFER_LLM_NONE" in m and "OFFER_LLM_EXC" in m
