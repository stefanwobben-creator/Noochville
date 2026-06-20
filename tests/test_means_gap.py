"""Tests voor means-gap routing naar de inbox — thread-vrij.

Drie scenario's:
1. means-gap gesensed → precies één inbox-item, keyed op gap_key.
2. Zelfde gap_key opnieuw → geen tweede item (inbox-dedup).
3. Dedup houdt stand nadat het item al resolved is.
"""
from __future__ import annotations
import pytest

from nooch_village.human_inbox import HumanInbox


# ── 1. Eerste means-gap → één inbox-item ────────────────────────────────────

def test_means_gap_lands_once_in_inbox(tmp_path):
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid   = inbox.add_means_gap("openlibrary_v2", "test beschrijving")
    items = inbox.all()
    assert len(items) == 1
    item  = items[0]
    assert item["type"]    == "means_gap"
    assert item["subject"] == "openlibrary_v2"
    assert item["status"]  == "pending"
    assert item["id"]      == iid


# ── 2. Zelfde gap_key → geen tweede item ────────────────────────────────────

def test_same_gap_key_no_second_item(tmp_path):
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid1  = inbox.add_means_gap("openlibrary_v2", "beschrijving 1")
    iid2  = inbox.add_means_gap("openlibrary_v2", "beschrijving 2")
    assert iid1 == iid2, "zelfde item moet teruggegeven worden"
    assert len(inbox.all()) == 1, "mag slechts één item bevatten"


def test_dedup_overleeft_resolved_status(tmp_path):
    """Dedup geldt ook als het item al opgelost is (eenmalig melden is definitief)."""
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid   = inbox.add_means_gap("ngram_2019_cutoff", "test")
    inbox.resolve(iid, "approved")
    iid2  = inbox.add_means_gap("ngram_2019_cutoff", "opnieuw")
    assert iid == iid2
    assert len(inbox.all()) == 1
