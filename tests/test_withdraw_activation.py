"""Inbox-hygiëne: een activation-item trekt zichzelf in zodra zijn rol gearchiveerd is.

Een inbox-item is een open vraag gekoppeld aan een premisse. Verdwijnt de premisse
(de rol wordt via governance gearchiveerd), dan is de vraag moot en wordt hij ingetrokken
— geen menselijke afwijzing, maar een ingetrokken vraag. Geen netwerk, thread-vrij."""
from __future__ import annotations
from types import SimpleNamespace

from nooch_village.human_inbox import HumanInbox


def _rec(role_id, archived=False):
    return SimpleNamespace(id=role_id, archived=archived)


def _activation_record(role_id):
    return {
        "type": "role", "source": "sensed",
        "definition": {"purpose": "iets", "accountabilities": [], "domains": [], "skills": []},
    }


def test_withdraw_activation_trekt_pending_item_in(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    iid = hi.add_activation("junk_rol", _activation_record("junk_rol"))
    assert len(hi.pending()) == 1

    ok = hi.withdraw_activation("junk_rol")
    assert ok is True
    assert hi.pending() == []
    item = next(i for i in hi._items.values() if i["id"] == iid)
    assert item["status"] == "withdrawn"
    assert "premisse" in item["resolution"]["reason"]


def test_withdraw_is_geen_afwijzing(tmp_path):
    """Een ingetrokken item is 'withdrawn', niet 'rejected' (andere semantiek)."""
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    hi.add_activation("junk_rol", _activation_record("junk_rol"))
    hi.withdraw_activation("junk_rol")
    item = next(iter(hi._items.values()))
    assert item["status"] == "withdrawn"
    assert item["status"] != "rejected"


def test_sweep_trekt_alleen_gearchiveerde_in(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    hi.add_activation("dood_rol", _activation_record("dood_rol"))
    hi.add_activation("levend_rol", _activation_record("levend_rol"))

    records = [_rec("dood_rol", archived=True), _rec("levend_rol", archived=False)]
    n = hi.withdraw_archived_activations(records)

    assert n == 1
    pend = [i["subject"] for i in hi.pending()]
    assert pend == ["levend_rol"]            # alleen het levende item blijft staan


def test_geen_pending_geeft_false(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    assert hi.withdraw_activation("bestaat_niet") is False


def test_ingetrokken_item_komt_niet_terug(tmp_path):
    """add_activation dedupt op role_id ongeacht status → een ingetrokken item
    wordt niet opnieuw aangemaakt."""
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    hi.add_activation("junk_rol", _activation_record("junk_rol"))
    hi.withdraw_activation("junk_rol")
    hi.add_activation("junk_rol", _activation_record("junk_rol"))   # opnieuw proberen
    assert hi.pending() == []                                       # blijft ingetrokken
