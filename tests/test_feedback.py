"""Oordeel = training: zachte verdicts (leuk idee / zachte nee / nu niet / elders) sluiten een
kans én leggen een trainingssignaal vast, zonder harde regel. Alleen vision_drop blokkeert."""
from __future__ import annotations

from nooch_village.feedback import Feedback, training_block
from nooch_village.human_inbox import HumanInbox
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


