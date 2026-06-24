"""Gedeelde inbox-acties: één gevalideerd pad voor CLI én cockpit.

Keyword-beslissing sluit het item én cureert in de bibliotheek; defer en confirm zijn
pure bookkeeping. Geen Village, geen netwerk."""
from __future__ import annotations
import pytest

from nooch_village.human_inbox import HumanInbox
from nooch_village.inbox_actions import decide_keyword, defer_item, confirm_item


class _StubLibrary:
    def __init__(self):
        self.calls = []
    def curate(self, word, status, rationale="", evidence=None, by="Librarian"):
        self.calls.append({"word": word, "status": status, "by": by})
        return {"word": word, "status": status}


def _inbox_with_keyword(tmp_path, word="vegan sneakers"):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_keyword_escalation(word, reason="impliceert plastic",
                                    demand={"signal": "rising", "locale": "en"})
    return hi, iid


def test_approve_keyword_cureert_approved(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    lib = _StubLibrary()
    res = decide_keyword(hi, lib, iid, "approve", reason="ok")
    assert res["ok"] and res["status"] == "approved"
    assert hi.get(iid)["status"] == "approved"
    assert lib.calls == [{"word": "vegan sneakers", "status": "approved", "by": "human"}]


def test_reject_keyword_cureert_forbidden(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    lib = _StubLibrary()
    res = decide_keyword(hi, lib, iid, "reject", reason="greenwashing")
    assert res["ok"] and res["status"] == "forbidden"
    assert hi.get(iid)["status"] == "rejected"
    assert lib.calls[0]["status"] == "forbidden"


def test_decide_keyword_weigert_niet_pending(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    lib = _StubLibrary()
    decide_keyword(hi, lib, iid, "approve")
    res = decide_keyword(hi, lib, iid, "reject")     # al beslist
    assert not res["ok"]
    assert len(lib.calls) == 1                        # tweede besluit raakt de bibliotheek niet


def test_decide_keyword_weigert_ander_type(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_means_gap("gap_x", "iets")
    lib = _StubLibrary()
    res = decide_keyword(hi, lib, iid, "approve")
    assert not res["ok"] and "geen keyword" in res["error"]
    assert lib.calls == []


def test_defer_item(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    res = defer_item(hi, iid, reason="later")
    assert res["ok"]
    assert hi.get(iid)["status"] == "deferred"


def test_confirm_item_zonder_voorstel_faalt(tmp_path):
    hi, iid = _inbox_with_keyword(tmp_path)
    res = confirm_item(hi, iid)
    assert not res["ok"]


def test_confirm_item_met_voorstel(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_means_gap("gap_x", "iets")
    hi.propose_resolution(iid, by="harry_hemp", reason="ik dek dit nu")
    res = confirm_item(hi, iid)
    assert res["ok"]
    assert hi.get(iid)["status"] == "approved"
