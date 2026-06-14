"""Tests voor means-gap routing naar de inbox — thread-vrij.

Vier scenario's:
1. means-gap gesensed → precies één inbox-item, keyed op gap_key.
2. Zelfde gap_key opnieuw → geen tweede item (inbox-dedup).
3. Geen amend_role-voorstel voor means-gaps (KennisScout + TijdgeestWachter).
4. semscholar_no_key wordt niet gesensed en komt niet in de inbox.
"""
from __future__ import annotations
import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.human_inbox import HumanInbox
from nooch_village.inhabitant import Inhabitant
from nooch_village.roles import KennisScout, TijdgeestWachter
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_role(role_id, bus, tmp_path, cls=Inhabitant):
    registry = SkillRegistry()
    context  = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        records=None,
    )
    record = Record(
        id=role_id,
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="test", accountabilities=[],
                                   domains=[], skills=[]),
        source="sensed",
    )
    return cls(record, bus, registry, context)


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


# ── 3. Geen amend_role-voorstel meer — KennisScout ──────────────────────────

def test_kennis_scout_reflect_geen_governance_voorstel(tmp_path):
    bus = EventBus(name="test")
    ks  = _make_role("kennis_scout", bus, tmp_path, KennisScout)

    proposals  = []
    tensions   = []
    means_gaps = []
    bus.subscribe("proposal_raised",  lambda e: proposals.append(e))
    bus.subscribe("tension_sensed",   lambda e: tensions.append(e))
    bus.subscribe("means_gap_sensed", lambda e: means_gaps.append(e.data["gap_key"]))

    ks._reflect()

    assert len(proposals) == 0, "geen governance-voorstel voor means-gaps"
    assert "openlibrary_v2"   in means_gaps, "openlibrary_v2 moet als means_gap verschijnen"
    assert "semscholar_no_key" not in means_gaps, "semscholar_no_key moet zwijgen"


# ── 4. semscholar verschijnt niet in de inbox ────────────────────────────────

def test_semscholar_niet_in_inbox(tmp_path):
    bus   = EventBus(name="test")
    inbox = HumanInbox(str(tmp_path / "inbox.json"))

    # Koppel bus → inbox zoals Village dat doet
    bus.subscribe("means_gap_sensed",
                  lambda e: inbox.add_means_gap(e.data["gap_key"], e.data["description"]))

    ks = _make_role("kennis_scout", bus, tmp_path, KennisScout)
    ks._reflect()

    subjects = [i["subject"] for i in inbox.all()]
    assert "openlibrary_v2"    in subjects
    assert "semscholar_no_key" not in subjects


def test_tijdgeest_reflect_geen_governance_voorstel(tmp_path):
    bus = EventBus(name="test")
    tw  = _make_role("tijdgeest_wachter", bus, tmp_path, TijdgeestWachter)

    proposals  = []
    means_gaps = []
    bus.subscribe("proposal_raised",  lambda e: proposals.append(e))
    bus.subscribe("means_gap_sensed", lambda e: means_gaps.append(e.data["gap_key"]))

    tw._reflect()

    assert len(proposals)      == 0,    "geen governance-voorstel"
    assert "ngram_2019_cutoff" in means_gaps
    assert "nl_corpus_coverage" in means_gaps
