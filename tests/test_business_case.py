"""Fase 1 — business-case maakt van spanningen afweegbare kansen.
Pure scorer + proposal-veld-roundtrip + de geprioriteerde kansen-backlog in de cockpit."""
from __future__ import annotations
import json

from nooch_village.business_case import make_business_case, business_value, format_business_case
from nooch_village.governance import proposal_to_dict, proposal_from_dict
from nooch_village.models import Proposal, GovernanceChange, ChangeKind
from nooch_village import cockpit


def test_make_business_case_normaliseert():
    bc = make_business_case(effect="l", effort=9, confidence=2.0)
    assert bc["effect"] == 30        # tier 'l' → 30
    assert bc["effort"] == 5         # geklemd op 1..5
    assert bc["confidence"] == 1.0   # geklemd op 0..1


def test_business_value_rangschikt():
    hoog = make_business_case(effect=100, effort=2, confidence=0.8)   # 100*0.8/2 = 40
    laag = make_business_case(effect=10, effort=5, confidence=0.3)    # 10*0.3/5 = 0.6
    assert business_value(hoog) == 40.0
    assert business_value(laag) == 0.6
    assert business_value(None) == 0.0
    assert business_value(hoog) > business_value(laag)


def test_format_business_case():
    s = format_business_case(make_business_case(effect=40, effort=2, confidence=0.5))
    assert "40 pairs_sold" in s and "waarde" in s


def test_proposal_draagt_business_case_roundtrip():
    p = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="rev_scout"),
        tension="structureel terugkerend", trigger_example="meermaals", rationale="x",
        hypothesis="als we reviews oogsten, dan meer conversie omdat sociaal bewijs",
        business_case=make_business_case(effect=50, effort=3, confidence=0.6))
    d = proposal_to_dict(p)
    assert d["business_case"]["effect"] == 50 and d["hypothesis"].startswith("als we")
    p2 = proposal_from_dict(d)
    assert p2.business_case["effect"] == 50 and p2.hypothesis == p.hypothesis


def test_cockpit_backlog_gerangschikt(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "library.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    # twee voorstellen in de inbox met business-case, verschillende waarde
    inbox = {
        "a": {"id": "a", "type": "escalation", "subject": "reviews oogsten", "status": "pending",
              "context": {"proposal": {"proposer_role": "analyst",
                          "hypothesis": "sociaal bewijs → conversie",
                          "business_case": make_business_case(effect=100, effort=2, confidence=0.8)}}},
        "b": {"id": "b", "type": "escalation", "subject": "fora monitoren", "status": "pending",
              "context": {"proposal": {"proposer_role": "scout",
                          "business_case": make_business_case(effect=10, effort=5, confidence=0.3)}}},
    }
    (data / "human_inbox.json").write_text(json.dumps(inbox), encoding="utf-8")

    snap = cockpit.gather(str(data))
    assert [b["title"] for b in snap["backlog"]] == ["reviews oogsten", "fora monitoren"]  # op waarde
    assert snap["backlog"][0]["value"] == 40.0

    # De dichte kansen-backlog is uit het dashboard (verwerken gaat via de focusmodus); de
    # ranking-data leeft nog in snap. De render mag gewoon draaien zonder die tabel.
    page = cockpit.render_html(snap, csrf_token="t")
    assert "Kansen-backlog" not in page
