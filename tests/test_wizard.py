"""Project-wizard (founder 20 jul): de LLM maakt een ruw idee scherp tot een toetsbare uitkomst
en stelt een checklist voor die per item tegen de skills van de rol wordt getoetst."""
from __future__ import annotations

import json

from nooch_village.wizard import plan_items, sharpen_outcome


def test_sharpen_fail_soft():
    # LLM levert niets → ruw idee terug (mens kan alsnog verder)
    assert sharpen_outcome("kijk naar zolen", reason_fn=lambda *a, **k: None) == "kijk naar zolen"
    assert sharpen_outcome("", reason_fn=lambda *a, **k: "x") == ""
    # LLM levert een uitkomst → schoongemaakt terug
    out = sharpen_outcome("zolen", reason_fn=lambda *a, **k: '  "Er ligt een overzicht van 3 zolen." ')
    assert out == "Er ligt een overzicht van 3 zolen."


CATALOG = [
    {"name": "epo_patents", "description": "patenten", "input": "query: str"},
    {"name": "openalex_evidence", "description": "studies", "input": "term: str"},
]
REQUIRED = {"epo_patents": ("query",), "openalex_evidence": ("term",)}


def _fake_plan(*a, **k):
    return json.dumps({"items": [
        {"tekst": "Zoek patenten op afbreekbare zolen", "skill": "epo_patents",
         "payload": {"query": "biodegradable outsole"}},
        {"tekst": "Haal studies op", "skill": "openalex_evidence", "payload": {}},   # payload mist
        {"tekst": "Bel drie leveranciers", "skill": None, "payload": {}},            # geen skill
        {"tekst": "Gebruik magie", "skill": "niet_bestaand", "payload": {}},         # skill niet van rol
    ]})


def test_plan_items_toetst_skills_en_payload():
    items = plan_items("Overzicht afbreekbare zolen", CATALOG,
                       reason_fn=_fake_plan, required_of=lambda s: REQUIRED.get(s, ()))
    assert len(items) == 4
    assert items[0]["skill"] == "epo_patents" and items[0]["ok"] is True
    assert items[1]["skill"] == "openalex_evidence" and items[1]["ok"] is False   # payload onvolledig
    assert "payload onvolledig" in items[1]["reden"]
    assert items[2]["skill"] is None and items[2]["ok"] is False                   # mens-taak
    assert items[3]["skill"] is None                                                # onbekende skill → null


def test_plan_items_fail_soft():
    assert plan_items("doel", CATALOG, reason_fn=lambda *a, **k: None) == []
    assert plan_items("", CATALOG, reason_fn=_fake_plan) == []
