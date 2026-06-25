"""Oordeel = training: zachte verdicts (leuk idee / zachte nee / nu niet / elders) sluiten een
kans én leggen een trainingssignaal vast, zonder harde regel. Alleen vision_drop blokkeert."""
from __future__ import annotations

from nooch_village.feedback import Feedback, training_block
from nooch_village.human_inbox import HumanInbox
from nooch_village.inbox_actions import decide_opportunity
from nooch_village.business_case import make_business_case


def _inbox(tmp_path):
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    iid = inbox.add_opportunity("Sokken van hennep", by="herman", wat="Hennep-sokken testen.",
                                business_case=make_business_case(effect=40, effort=2, confidence=0.6))
    return inbox, iid


def test_feedback_store_persisteert(tmp_path):
    fb = Feedback(str(tmp_path / "feedback.json"))
    fb.add("praise", "Reviews tonen", "mooi denkwerk", by="analyst")
    assert Feedback(str(tmp_path / "feedback.json")).all()[0]["verdict"] == "praise"


def test_training_block_positief_en_negatief_en_rolfilter():
    items = [
        {"verdict": "praise", "title": "Reviews tonen", "reason": "", "by": "analyst"},
        {"verdict": "soft_reject", "title": "Pop-up store", "reason": "te duur", "by": "analyst"},
        {"verdict": "not_now", "title": "Podcast", "reason": "later", "by": "scout"},
        {"verdict": "vision_drop", "title": "Adverteren", "reason": "geen ads", "by": "analyst"},
    ]
    block = training_block(items, role="analyst")
    assert "goed denkwerk: Reviews tonen" in block
    assert "Pop-up store" in block and "te duur" in block
    assert "Podcast" not in block          # andere rol (scout) → niet voor analyst
    assert "Adverteren" not in block       # vision_drop is geen zacht signaal (zit in constraints)
    # zonder rolfilter komt alles van de zachte verdicts mee
    assert "Podcast" in training_block(items)


def test_verdict_praise_sluit_en_logt(tmp_path):
    inbox, iid = _inbox(tmp_path)
    fb = Feedback(str(tmp_path / "feedback.json"))
    res = decide_opportunity(inbox, iid, "praise", reason="goed idee", feedback=fb)
    assert res["ok"] and res["status"] == "praise"
    assert inbox.get(iid)["status"] == "resolved"          # uit de triage
    assert fb.all()[0]["verdict"] == "praise" and fb.all()[0]["by"] == "herman"


def test_verdict_not_now_en_elsewhere_sluiten_verschillend(tmp_path):
    inbox, iid = _inbox(tmp_path)
    fb = Feedback(str(tmp_path / "feedback.json"))
    assert decide_opportunity(inbox, iid, "not_now", feedback=fb)["status"] == "not_now"
    assert inbox.get(iid)["status"] == "deferred"
    inbox2 = HumanInbox(str(tmp_path / "i2.json"))
    iid2 = inbox2.add_opportunity("Ruilfeest", by="scout")
    assert decide_opportunity(inbox2, iid2, "elsewhere", feedback=fb)["status"] == "elsewhere"
    assert inbox2.get(iid2)["status"] == "resolved"
    assert {f["verdict"] for f in fb.all()} == {"not_now", "elsewhere"}


def test_soft_reject_geen_huisregel_maar_wel_signaal(tmp_path):
    from nooch_village.constraints import Constraints
    inbox, iid = _inbox(tmp_path)
    fb = Feedback(str(tmp_path / "feedback.json"))
    cons = Constraints(str(tmp_path / "constraints.json"))
    decide_opportunity(inbox, iid, "soft_reject", reason="niet nu passend",
                       constraints=cons, feedback=fb)
    assert inbox.get(iid)["status"] == "rejected"
    assert cons.texts() == []                              # GEEN harde huis-regel
    assert fb.all()[0]["verdict"] == "soft_reject"


def test_vision_drop_wel_huisregel_en_signaal(tmp_path):
    from nooch_village.constraints import Constraints
    inbox, iid = _inbox(tmp_path)
    fb = Feedback(str(tmp_path / "feedback.json"))
    cons = Constraints(str(tmp_path / "constraints.json"))
    decide_opportunity(inbox, iid, "reject", reason="we bieden geen sokken aan",
                       remember_constraint=True, constraints=cons, feedback=fb)
    assert inbox.get(iid)["status"] == "rejected"
    assert "geen sokken" in cons.texts()[0]               # harde huis-regel
    assert fb.all()[0]["verdict"] == "vision_drop"
