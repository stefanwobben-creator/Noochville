"""Holacracy-triage: vraag-aan-rol dialoog-lus (parkeren + gebundeld beantwoorden in de puls),
AI die governance-doelwit kiest (nieuw vs. uitbreiden) en een project Holacracy-formuleert,
plus de scroll-fix (rij-anchor) in de cockpit-render."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox
from nooch_village.inbox_actions import (
    ask_role, answer_pending_questions)
from nooch_village.business_case import make_business_case


def _inbox(tmp_path):
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    iid = inbox.add_opportunity("Reviews op de productpagina", by="analyst", kind="project",
                                wat="Sterren en korte reviews tonen.",
                                waarom="sociaal bewijs",
                                business_case=make_business_case(effect=80, effort=2, confidence=0.7))
    return inbox, iid


def test_vraag_wordt_geparkeerd_geen_llm(tmp_path):
    inbox, iid = _inbox(tmp_path)
    res = ask_role(inbox, iid, "Ik snap dit voorstel niet, wat bedoel je precies?")
    assert res["ok"] and res["status"] == "waiting"
    item = inbox.get(iid)
    assert item["status"] == "pending"                       # item blijft open
    dlg = item["context"]["dialogue"]
    assert len(dlg) == 1 and dlg[0]["answered"] is False
    assert inbox.pending_questions()[0]["iid"] == iid


def test_lege_vraag_wordt_geweigerd(tmp_path):
    inbox, iid = _inbox(tmp_path)
    assert ask_role(inbox, iid, "   ")["ok"] is False


def test_gebundelde_beantwoording_vult_dialoog(tmp_path):
    inbox, iid = _inbox(tmp_path)
    ask_role(inbox, iid, "Wat bedoel je met sociaal bewijs?")
    iid2 = inbox.add_opportunity("Sokken van hennep", by="herman", wat="Hennep-sokken testen.")
    ask_role(inbox, iid2, "Is hennep wel bio-afbreekbaar?")

    def fake_llm(prompt):
        # twee vragen → twee antwoorden in het gevraagde formaat
        assert "VRAAG 1" in prompt and "VRAAG 2" in prompt
        return ("ANTWOORD 1: Sociaal bewijs betekent dat mensen eerder kopen als ze zien dat "
                "anderen blij zijn.\nANTWOORD 2: Pure hennep wel, maar let op het elastan.")

    res = answer_pending_questions(inbox, records=None, llm_reason=fake_llm)
    assert res["answered"] == 2 and res["pending"] == 0
    d1 = inbox.get(iid)["context"]["dialogue"][0]
    assert d1["answered"] and "Sociaal bewijs" in d1["a"]
    # tweede keer: niks meer open
    assert answer_pending_questions(inbox, llm_reason=fake_llm)["answered"] == 0


def test_beantwoording_fail_closed_zonder_llm(tmp_path):
    inbox, iid = _inbox(tmp_path)
    ask_role(inbox, iid, "Leg eens uit?")
    res = answer_pending_questions(inbox, llm_reason=lambda p: None)
    assert res["answered"] == 0 and res["pending"] == 1
    assert inbox.get(iid)["context"]["dialogue"][0]["answered"] is False


