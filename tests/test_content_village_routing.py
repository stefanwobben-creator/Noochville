"""Tests voor de Village-routering van content-events naar de inbox (brokje 13d-i)."""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.human_inbox import HumanInbox
from nooch_village.event_bus import Event
from nooch_village.village import Village


def _fake(tmp_path):
    inbox = HumanInbox(str(tmp_path / "i.json"))
    return SimpleNamespace(human_inbox=inbox), inbox


def test_content_opportunity_naar_inbox(tmp_path):
    fake, inbox = _fake(tmp_path)
    Village._on_content_opportunity(fake, Event("content_opportunity",
        {"seed_id": "trend", "cluster_ids": ["trend", "b"], "reason": "r"}, "cs"))
    items = [x for x in inbox.all() if x["type"] == "content_suggestion"]
    assert len(items) == 1
    assert items[0]["context"]["seed_id"] == "trend"


def test_content_opportunity_zonder_seed_negeert(tmp_path):
    fake, inbox = _fake(tmp_path)
    Village._on_content_opportunity(fake, Event("content_opportunity", {"cluster_ids": []}, "cs"))
    assert inbox.all() == []


def test_content_draft_naar_inbox(tmp_path):
    fake, inbox = _fake(tmp_path)
    Village._on_content_draft_ready(fake, Event("content_draft_ready",
        {"seed_id": "trend", "kind": "blog", "text": "DRAFT",
         "claim_insight_ids": ["trend"]}, "cs"))
    items = [x for x in inbox.all() if x["type"] == "content_draft"]
    assert len(items) == 1
    assert items[0]["context"]["text"] == "DRAFT"


def test_content_draft_zonder_tekst_negeert(tmp_path):
    fake, inbox = _fake(tmp_path)
    Village._on_content_draft_ready(fake, Event("content_draft_ready",
        {"seed_id": "trend", "text": None}, "cs"))
    assert inbox.all() == []
