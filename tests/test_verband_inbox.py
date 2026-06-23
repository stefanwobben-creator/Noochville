"""Tests voor de mens-gegateerde dwarslinks (3c, brokje 8). Thread-vrij.

Een verband-voorstel landt in de human-inbox; bij approve schrijft de mens het
touwtje (notes.link) tussen de twee kaartjes. Reject laat het touwtje weg.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.human_inbox import HumanInbox
from nooch_village.event_bus import Event
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


def _inbox(tmp_path):
    return HumanInbox(str(tmp_path / "human_inbox.json"))


# ── opslag + dedup ────────────────────────────────────────────────────────────

def test_add_verband_slaat_voorstel_op(tmp_path):
    inbox = _inbox(tmp_path)
    iid = inbox.add_verband("a", "b", "A en B hangen samen", "reden")
    item = inbox.get(iid)
    assert item["type"] == "verband"
    assert item["status"] == "pending"
    assert item["context"]["kaart_a_id"] == "a"
    assert item["context"]["kaart_b_id"] == "b"
    assert item["context"]["voorstel_claim"] == "A en B hangen samen"


def test_add_verband_dedup_op_ongeordend_paar(tmp_path):
    inbox = _inbox(tmp_path)
    i1 = inbox.add_verband("a", "b", "claim", "")
    i2 = inbox.add_verband("b", "a", "andere claim", "")  # zelfde paar, andere volgorde
    assert i1 == i2
    assert len([x for x in inbox.all() if x["type"] == "verband"]) == 1


# ── routering via de Village ──────────────────────────────────────────────────

def test_village_routeert_verband_naar_inbox(tmp_path):
    from nooch_village.village import Village
    inbox = _inbox(tmp_path)
    fake = SimpleNamespace(human_inbox=inbox)
    ev = Event("human_decision_needed", {
        "topic": "verband", "kaart_a_id": "a", "kaart_b_id": "b",
        "voorstel_claim": "samen", "reason": "test",
    }, "librarian")
    Village._on_verband_suggestion(fake, ev)
    assert len([x for x in inbox.all() if x["type"] == "verband"]) == 1


def test_village_negeert_ander_topic(tmp_path):
    from nooch_village.village import Village
    inbox = _inbox(tmp_path)
    fake = SimpleNamespace(human_inbox=inbox)
    Village._on_verband_suggestion(fake, Event("human_decision_needed",
        {"topic": "keyword", "word": "x"}, "lib"))
    assert inbox.all() == []


def test_village_negeert_verband_zonder_ids(tmp_path):
    from nooch_village.village import Village
    inbox = _inbox(tmp_path)
    fake = SimpleNamespace(human_inbox=inbox)
    Village._on_verband_suggestion(fake, Event("human_decision_needed",
        {"topic": "verband", "kaart_a_id": "a"}, "lib"))  # b ontbreekt
    assert inbox.all() == []


# ── approve schrijft het touwtje ──────────────────────────────────────────────

def test_approve_verband_legt_touwtje(tmp_path):
    from nooch_village.inbox.__main__ import _approve_verband
    inbox = _inbox(tmp_path)
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim=".", source="t", word="barefoot"))
    notes.add(Insight(id="b", claim=".", source="t", word="vegan"))
    iid = inbox.add_verband("a", "b", "samen", "")

    ok = _approve_verband(inbox, inbox.get(iid), iid, notes)
    assert ok is True
    assert "b" in notes.get("a").links_to            # touwtje gelegd
    assert inbox.get(iid)["status"] == "approved"    # item gesloten


def test_approve_verband_zonder_kaartje_sluit_maar_linkt_niet(tmp_path):
    from nooch_village.inbox.__main__ import _approve_verband
    inbox = _inbox(tmp_path)
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim=".", source="t", word="barefoot"))
    iid = inbox.add_verband("a", "weg", "samen", "")  # 'weg' bestaat niet

    ok = _approve_verband(inbox, inbox.get(iid), iid, notes)
    assert ok is False
    assert notes.get("a").links_to == []
    assert inbox.get(iid)["status"] == "approved"    # wel netjes gesloten
