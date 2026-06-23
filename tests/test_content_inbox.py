"""Tests voor de content-inbox-itemtypen (Fase 2 brokje 13b). Thread-vrij."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox


def _inbox(tmp_path):
    return HumanInbox(str(tmp_path / "human_inbox.json"))


def test_add_content_suggestion_slaat_op(tmp_path):
    inbox = _inbox(tmp_path)
    iid = inbox.add_content_suggestion("trend", ["trend", "b"], "rijk cluster")
    item = inbox.get(iid)
    assert item["type"] == "content_suggestion"
    assert item["status"] == "pending"
    assert item["context"]["seed_id"] == "trend"
    assert item["context"]["cluster_ids"] == ["trend", "b"]


def test_content_suggestion_dedup_op_seed(tmp_path):
    inbox = _inbox(tmp_path)
    i1 = inbox.add_content_suggestion("trend", ["trend", "b"])
    i2 = inbox.add_content_suggestion("trend", ["trend", "c"])  # zelfde seed
    assert i1 == i2
    assert len([x for x in inbox.all() if x["type"] == "content_suggestion"]) == 1


def test_add_content_draft_slaat_op(tmp_path):
    inbox = _inbox(tmp_path)
    iid = inbox.add_content_draft("trend", "blog", "De tekst.", ["trend", "b"])
    item = inbox.get(iid)
    assert item["type"] == "content_draft"
    assert item["context"]["text"] == "De tekst."
    assert item["context"]["kind"] == "blog"


def test_content_draft_dedup_op_seed_en_soort(tmp_path):
    inbox = _inbox(tmp_path)
    i1 = inbox.add_content_draft("trend", "blog", "A", [])
    i2 = inbox.add_content_draft("trend", "blog", "B", [])     # zelfde seed+soort
    i3 = inbox.add_content_draft("trend", "sales_page", "C", [])  # ander soort
    assert i1 == i2
    assert i3 != i1
    assert len([x for x in inbox.all() if x["type"] == "content_draft"]) == 2
