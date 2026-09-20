"""Mens-poort voor kansen: een door een rol gesensde kans landt als beslissing in de inbox en
wordt PAS een project als de mens 'm goedkeurt. Negeren sluit 'm. Niets wordt autonoom gequeued."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox
from nooch_village.projects import ProjectLedger
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


