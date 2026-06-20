"""Tests voor The Source — de menselijke founding rol in het dorp.

Vijf scenario's:
1. RECORD: migrate_records voegt the_source toe met source=seed, persona=Stefan,
   zeven accountabilities, geen skills; en plaatst hem in noochville.members.
2. UNMANNED: na build belandt the_source in reconciler.unmanned, niet in live.
3. INBOX-SKIP: sync_unmanned slaat source=seed records over; geen activatie-item
   voor the_source, ook al staat hij niet in CLASS_MAP.
4. APPROVE: approve_escalation publiceert governance_verdict met sender "the_source".
5. ROUNDTRIP: persona overleeft een save()/_load()-roundtrip — zou de originele
   _load-bug hebben gevangen waarbij het persona-veld niet werd meegeladen.
"""
from __future__ import annotations
import pytest
from types import SimpleNamespace

from nooch_village.governance import Records, Secretary, Reconciler, proposal_to_dict, proposal_from_dict
from nooch_village.models import (
    Proposal, GovernanceChange, ChangeKind,
    Record, RoleDefinition, RecordType,
)
from nooch_village.event_bus import EventBus, Event
from nooch_village.human_inbox import HumanInbox
from nooch_village.matchmaker import Matchmaker
from nooch_village.skills import SkillRegistry
from nooch_village.seeds import seed_records, migrate_records


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_records(tmp_path) -> Records:
    path = str(tmp_path / "gov.json")
    recs = Records(path)
    seed_records(recs)
    migrate_records(recs)
    return recs


# ── 1. RECORD ─────────────────────────────────────────────────────────────────

def test_the_source_record_bestaat_na_migrate(tmp_path):
    """migrate_records schrijft the_source met source=seed, persona=Stefan, 7 accountabilities."""
    recs = _make_records(tmp_path)
    rec = recs.get("the_source")

    assert rec is not None
    assert rec.source == "seed"
    assert rec.persona == "Stefan"
    assert rec.type == RecordType.ROLE
    assert rec.parent == "noochville"
    assert rec.definition.skills == []
    assert len(rec.definition.accountabilities) == 7
    assert "de richting van NoochVille bepalen" in rec.definition.accountabilities
    assert "een vangnet zijn" in rec.definition.accountabilities

    root = recs.root()
    assert "the_source" in root.members


# ── 2. UNMANNED ───────────────────────────────────────────────────────────────

def test_the_source_belandt_in_unmanned_niet_in_live(tmp_path):
    """Na build: the_source in reconciler.unmanned, niet in reconciler.live."""
    path = str(tmp_path / "gov.json")
    recs = Records(path)

    # Minimale setup: alleen wortelcirkel + the_source
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(purpose="test", skills=[]),
                  members=["the_source"])
    root.source = "seed"
    recs.put(root)

    the_source = Record(
        id="the_source", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(
            purpose="De droom van NoochVille bedenken en iedereen enthousiast maken.",
            accountabilities=["de richting van NoochVille bepalen"],
            skills=[],
        ),
        source="seed",
        persona="Stefan",
    )
    recs.put(the_source)

    bus      = EventBus(name="test")
    registry = SkillRegistry()
    context  = SimpleNamespace(
        settings={}, data_dir=str(tmp_path),
        library=None, lexicon=None, records=recs,
        observations=None, monitoring=None, projects=None,
    )
    matchmaker = Matchmaker(bus)

    reconciler = Reconciler(recs, bus, registry, context, matchmaker, class_map={})
    reconciler.build()

    assert "the_source" in reconciler.unmanned, "the_source verwacht in unmanned"
    assert "the_source" not in reconciler.live, "the_source mag niet live draaien"


# ── 3. INBOX-SKIP ─────────────────────────────────────────────────────────────

def test_seed_record_krijgt_geen_activatie_item(tmp_path):
    """sync_unmanned slaat source=seed over — geen activatie-item voor the_source."""
    recs = _make_records(tmp_path)
    inbox = HumanInbox(str(tmp_path / "inbox.json"))

    # Lege CLASS_MAP: the_source heeft geen entry
    inbox.sync_unmanned(recs.all(), class_map={})

    the_source_items = [
        i for i in inbox.all() if i.get("subject") == "the_source"
    ]
    assert the_source_items == [], (
        "geen activatie-item verwacht: the_source is source=seed en sync_unmanned slaat "
        "alle niet-sensed records over"
    )


# ── 4. APPROVE ────────────────────────────────────────────────────────────────

def test_persona_overleeft_save_load_roundtrip(tmp_path):
    """persona-veld overleeft een Records.save()/_load()-roundtrip.

    Regressietest voor de _load-bug waarbij het persona-veld niet werd gelezen
    uit de JSON; na herladen viel het terug op None (de dataclass-default).
    """
    path = str(tmp_path / "gov.json")
    recs = Records(path)

    rec = Record(
        id="test_rol", type=RecordType.ROLE, parent=None,
        definition=RoleDefinition(purpose="test", skills=[]),
        source="seed",
        persona="Testpersoon",
    )
    recs.put(rec)   # schrijft naar disk via save()

    # Nieuwe instantie laadt hetzelfde bestand via _load()
    recs2 = Records(path)
    reloaded = recs2.get("test_rol")

    assert reloaded is not None
    assert reloaded.persona == "Testpersoon", (
        f"persona genivelleerd naar {reloaded.persona!r} na save/_load-roundtrip"
    )


def test_approve_escalation_sender_is_the_source():
    """approve_escalation publiceert governance_verdict met sender 'the_source'."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)

    proposal = Proposal(
        proposer_role="test",
        change=GovernanceChange(
            kind=ChangeKind.REMOVE_ROLE,
            role_id="nonexistent_test_rol",
        ),
        tension="test sender verificatie",
        trigger_example="structureel terugkerend meermaals",
        rationale="doorlopend structureel gekoppeld",
        source="sensed",
    )
    proposal_dict = proposal_to_dict(proposal)
    iid = v.human_inbox.add_escalation(proposal_dict, gate="G3", reason="test")

    captured: list[str] = []
    v.bus.subscribe("governance_verdict", lambda e: captured.append(e.sender))

    result = v.approve_escalation(iid, reason="test")

    assert result is True
    assert captured == ["the_source"], (
        f"verwacht sender='the_source', kreeg {captured!r}"
    )
