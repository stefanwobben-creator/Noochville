"""Tests voor keyword_batch inbox-items — structuur, dedup en print. Geen Village, geen credits."""
from __future__ import annotations
import pytest
from nooch_village.human_inbox import HumanInbox
from nooch_village.keyword_batch import propose_batch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _inbox(tmp_path):
    return HumanInbox(str(tmp_path / "inbox.json"))


def _batch_args(market: str = "nl", tier: str = "core") -> tuple:
    b = propose_batch(market, tier=tier)
    return b["market"], b["tier"], b["candidates"], b["estimated_credits"]


# ── Tests: add_keyword_batch ──────────────────────────────────────────────────

def test_add_keyword_batch_item_structuur(tmp_path):
    inbox = _inbox(tmp_path)
    market, tier, candidates, credits = _batch_args("nl", "core")
    iid = inbox.add_keyword_batch(market, tier, candidates, credits)

    item = inbox.get(iid)
    assert item is not None
    assert item["type"]    == "keyword_batch"
    assert item["status"]  == "pending"
    assert item["subject"] == "nl/core"
    assert item["resolved_at"] is None
    assert item["resolution"]  is None

    ctx = item["context"]
    assert ctx["market"]            == "nl"
    assert ctx["tier"]              == "core"
    assert ctx["candidates"]        == candidates
    assert ctx["estimated_credits"] == credits


def test_add_keyword_batch_fr_subject_correct(tmp_path):
    inbox = _inbox(tmp_path)
    market, tier, candidates, credits = _batch_args("fr", "core")
    iid = inbox.add_keyword_batch(market, tier, candidates, credits)
    assert inbox.get(iid)["subject"] == "fr/core"


def test_add_keyword_batch_dedup_zelfde_markt_tier_pending(tmp_path):
    inbox = _inbox(tmp_path)
    market, tier, candidates, credits = _batch_args("nl", "core")
    iid1 = inbox.add_keyword_batch(market, tier, candidates, credits)
    iid2 = inbox.add_keyword_batch(market, tier, candidates, credits)

    assert iid1 == iid2
    batches = [i for i in inbox.all() if i["type"] == "keyword_batch"]
    assert len(batches) == 1


def test_add_keyword_batch_verschillende_markten_geen_dedup(tmp_path):
    inbox = _inbox(tmp_path)
    iid_nl = inbox.add_keyword_batch(*_batch_args("nl", "core"))
    iid_fr = inbox.add_keyword_batch(*_batch_args("fr", "core"))
    assert iid_nl != iid_fr
    batches = [i for i in inbox.all() if i["type"] == "keyword_batch"]
    assert len(batches) == 2


def test_add_keyword_batch_dedup_na_afsluiten_mag_opnieuw(tmp_path):
    """Dedup geldt alleen bij status pending — na resolve mag dezelfde batch opnieuw."""
    inbox = _inbox(tmp_path)
    market, tier, candidates, credits = _batch_args("nl", "core")
    iid1 = inbox.add_keyword_batch(market, tier, candidates, credits)
    inbox.resolve(iid1, "rejected", reason="test")
    iid2 = inbox.add_keyword_batch(market, tier, candidates, credits)
    assert iid1 != iid2


# ── Tests: _print_item_full ───────────────────────────────────────────────────

def test_print_item_full_toont_markt_tier_credits_kandidaten(tmp_path, capsys):
    from nooch_village.inbox.__main__ import _print_item_full

    inbox = _inbox(tmp_path)
    market, tier, candidates, credits = _batch_args("fr", "core")
    iid  = inbox.add_keyword_batch(market, tier, candidates, credits)
    item = inbox.get(iid)

    _print_item_full(item)
    out = capsys.readouterr().out

    assert "fr"         in out
    assert "core"       in out
    assert str(credits) in out
    assert candidates[0] in out          # minstens één kandidaat zichtbaar
    assert "approve"    in out           # acties-sectie aanwezig
    assert "reject"     in out
