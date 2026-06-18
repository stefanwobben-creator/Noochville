"""Tests voor de means_gap approve-handler in inbox/__main__.py.

Vijf invarianten:
  1. Approve met geldige input → submit_proposal met AMEND_ROLE, juiste role_id, add_skills.
  2. Approve → resolution-velden: skill_added, rationale, alternatives_considered,
     resolved_by="human-cli", resolved_at gezet.
  3. Lege skill_name → submit_proposal NIET aangeroepen, item pending.
  4. Te korte rationale → submit_proposal NIET aangeroepen, item pending.
  5. Gate-veto → item blijft pending, veto-reden zichtbaar.
"""
from __future__ import annotations
import time
from unittest.mock import patch

import pytest

from nooch_village.human_inbox import HumanInbox
from nooch_village.event_bus import EventBus, Event
from nooch_village.models import ChangeKind

# Import helper function direct — geen main() nodig
from nooch_village.inbox.__main__ import _approve_means_gap


# ── Fake Village ──────────────────────────────────────────────────────────────

class _FakeContext:
    settings: dict = {}


class _FakeVillage:
    """Lichtgewicht village-vervanger: echte EventBus, synchrone event-firing."""

    context = _FakeContext()

    def __init__(self, *, fire_event: str = "governance_changed", veto_gate: str | None = None):
        self.bus = EventBus(name="test")
        self._fire_event  = fire_event
        self._veto_gate   = veto_gate
        self.proposals: list = []

    def start(self): pass
    def stop(self):  pass

    def submit_proposal(self, proposal):
        self.proposals.append(proposal)
        if self._fire_event == "governance_changed":
            self.bus.publish(Event(
                "governance_changed",
                {"proposal_id": proposal.id},
                "secretary",
            ))
        elif self._fire_event == "governance_review_requested":
            self.bus.publish(Event(
                "governance_review_requested",
                {
                    "proposal_id": proposal.id,
                    "gate":   self._veto_gate or "G2",
                    "reason": "accountability_duplicaat",
                },
                "facilitator",
            ))
        elif self._fire_event == "proposal_invalid":
            self.bus.publish(Event(
                "proposal_invalid",
                {
                    "proposal_id": proposal.id,
                    "gate":   "G0",
                    "reason": "verplicht veld ontbreekt",
                },
                "facilitator",
            ))
        return proposal.id


def _make_inbox_with_item(tmp_path, role_id="tijdgeest_wachter"):
    """Maak een HumanInbox met één means_gap-item inclusief role_id in context."""
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    iid = inbox.add_means_gap(
        gap_key="ngram_2019_cutoff",
        description="ngram-corpus stopt in 2019; recentere bron ontbreekt",
        role_id=role_id,
    )
    item = inbox.get(iid)
    return inbox, item


# ── 1. submit_proposal met juiste GovernanceChange ────────────────────────────

def test_approve_means_gap_creates_amend_role_proposal(tmp_path):
    """Approve met geldige input → submit_proposal ontvangt AMEND_ROLE + juiste role_id + skill."""
    inbox, item = _make_inbox_with_item(tmp_path)
    fake_village = _FakeVillage(fire_event="governance_changed")

    inputs = iter([
        "english_ngram_2024",          # skill_name
        "Recentere ngram-data nodig",  # rationale (≥10 tekens)
        "geen",                        # alternatives_considered
    ])
    with patch("builtins.input", side_effect=inputs):
        with patch("time.sleep"):      # skip de 0.1s sleep in de handler
            _approve_means_gap(inbox, item, _load_fn=lambda: (None, fake_village))

    assert len(fake_village.proposals) == 1
    p = fake_village.proposals[0]
    assert p.change.kind     == ChangeKind.AMEND_ROLE
    assert p.change.role_id  == "tijdgeest_wachter"
    assert p.change.add_skills == ["english_ngram_2024"]
    assert p.proposer_role   == "human-cli"


# ── 2. Resolution-velden na succesvolle approve ───────────────────────────────

def test_approve_means_gap_writes_resolution_fields(tmp_path):
    """Na succesvolle approve → resolution bevat skill_added, rationale, alternatives, resolved_by."""
    inbox, item = _make_inbox_with_item(tmp_path)
    fake_village = _FakeVillage(fire_event="governance_changed")

    inputs = iter([
        "english_ngram_2024",
        "Recentere ngram-data nodig",
        "geen",
    ])
    with patch("builtins.input", side_effect=inputs):
        with patch("time.sleep"):
            _approve_means_gap(inbox, item, _load_fn=lambda: (None, fake_village))

    item_after = inbox.get(item["id"])
    assert item_after["status"] == "approved"
    assert item_after["resolved_at"] is not None

    res = item_after["resolution"]
    assert res["skill_added"]             == "english_ngram_2024"
    assert res["rationale"]               == "Recentere ngram-data nodig"
    assert res["alternatives_considered"] == "geen"
    assert res["resolved_by"]             == "human-cli"


# ── 3. Lege skill_name → geen submit ──────────────────────────────────────────

def test_approve_means_gap_rejects_empty_skill_name(tmp_path):
    """Lege skill_name → submit_proposal NIET aangeroepen, item blijft pending."""
    inbox, item = _make_inbox_with_item(tmp_path)
    fake_village = _FakeVillage()

    # Eerste input: leeg → validatie-fout; tweede: EOFError → afbreken
    with patch("builtins.input", side_effect=["", EOFError()]):
        with patch("time.sleep"):
            _approve_means_gap(inbox, item, _load_fn=lambda: (None, fake_village))

    assert fake_village.proposals == [], "submit_proposal mag niet worden aangeroepen"
    assert inbox.get(item["id"])["status"] == "pending", "item moet pending blijven"


# ── 4. Te korte rationale → geen submit ───────────────────────────────────────

def test_approve_means_gap_rejects_short_rationale(tmp_path):
    """Rationale < 10 tekens → submit_proposal NIET aangeroepen, item pending."""
    inbox, item = _make_inbox_with_item(tmp_path)
    fake_village = _FakeVillage()

    # skill_name OK, rationale te kort → EOFError → afbreken
    with patch("builtins.input", side_effect=["english_ngram_2024", "te kort", EOFError()]):
        with patch("time.sleep"):
            _approve_means_gap(inbox, item, _load_fn=lambda: (None, fake_village))

    assert fake_village.proposals == []
    assert inbox.get(item["id"])["status"] == "pending"


# ── 5. Gate-veto → item blijft pending ────────────────────────────────────────

def test_approve_means_gap_gate_veto_keeps_item_pending(tmp_path, capsys):
    """Gate-veto (G2 accountability_duplicaat) → item pending, veto-reden getoond."""
    inbox, item = _make_inbox_with_item(tmp_path)
    fake_village = _FakeVillage(
        fire_event="governance_review_requested",
        veto_gate="G2",
    )

    inputs = iter([
        "english_ngram_2024",
        "Recentere ngram-data nodig",
        "geen",
    ])
    with patch("builtins.input", side_effect=inputs):
        with patch("time.sleep"):
            _approve_means_gap(inbox, item, _load_fn=lambda: (None, fake_village))

    assert inbox.get(item["id"])["status"] == "pending", "item moet pending blijven na veto"
    output = capsys.readouterr().out
    assert "G2" in output, "gate-naam G2 moet zichtbaar zijn in output"
    assert "accountability_duplicaat" in output, "veto-reden moet zichtbaar zijn"
