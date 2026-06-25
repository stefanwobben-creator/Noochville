"""Mens-poort voor kansen: een door een rol gesensde kans landt als beslissing in de inbox en
wordt PAS een project als de mens 'm goedkeurt. Negeren sluit 'm. Niets wordt autonoom gequeued."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox
from nooch_village.projects import ProjectLedger
from nooch_village.inbox_actions import decide_opportunity
from nooch_village.business_case import make_business_case


def _setup(tmp_path):
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    iid = inbox.add_opportunity("Reviews oogsten op de PDP", by="analyst", kind="project",
                                wat="We tonen reviews op de productpagina.",
                                waarom="sociaal bewijs → conversie",
                                business_case=make_business_case(effect=80, effort=2, confidence=0.7))
    return inbox, projects, iid


def test_kans_in_inbox_pending(tmp_path):
    inbox, _projects, iid = _setup(tmp_path)
    item = inbox.get(iid)
    assert item["type"] == "opportunity" and item["status"] == "pending"
    # dedup op titel
    iid2 = inbox.add_opportunity("Reviews oogsten op de PDP")
    assert iid2 == iid


def test_approve_maakt_project(tmp_path):
    inbox, projects, iid = _setup(tmp_path)
    assert projects.all() == []                            # nog geen project vóór akkoord
    res = decide_opportunity(inbox, projects, iid, "approve")
    assert res["ok"] and res["status"] == "approved"
    ps = projects.all()
    assert len(ps) == 1 and ps[0]["scope"] == "Reviews oogsten op de PDP"
    assert ps[0]["business_case"]["effect"] == 80
    assert inbox.get(iid)["status"] == "approved"          # uit de inbox


def test_reject_sluit_zonder_project(tmp_path):
    inbox, projects, iid = _setup(tmp_path)
    res = decide_opportunity(inbox, projects, iid, "reject")
    assert res["ok"] and res["status"] == "rejected"
    assert projects.all() == []
    assert inbox.get(iid)["status"] == "rejected"


def test_dubbele_beslissing_faalt(tmp_path):
    inbox, projects, iid = _setup(tmp_path)
    decide_opportunity(inbox, projects, iid, "approve")
    again = decide_opportunity(inbox, projects, iid, "approve")
    assert again["ok"] is False
