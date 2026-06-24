"""Integratietests voor Secretary — thread-vrij, echte EventBus + Records op tmp_path."""
from __future__ import annotations
import pytest
from nooch_village.event_bus import EventBus, Event
from nooch_village.governance import Records, Secretary, proposal_to_dict, proposal_from_dict
from nooch_village.human_inbox import HumanInbox
from nooch_village.models import (
    Record, RoleDefinition, RecordType,
    Proposal, GovernanceChange, ChangeKind,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _role(rid: str, **kwargs) -> Record:
    return Record(
        id=rid, type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="test doel", **kwargs),
        source="seed",
    )


def _amend(role_id: str, add_accs: list[str] | None = None) -> Proposal:
    return Proposal(
        proposer_role="test_rol",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id=role_id,
            add_accountabilities=add_accs or ["periodiek rapporteren"],
        ),
        tension="spanning", trigger_example="terugkerend", rationale="structureel",
    )


def _add_role(role_id: str) -> Proposal:
    return Proposal(
        proposer_role="test_rol",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id=role_id,
            purpose="nieuwe rol doet iets structureels",
        ),
        tension="spanning", trigger_example="terugkerend", rationale="structureel",
    )


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def sec(bus, records_with_root):
    return Secretary(records_with_root, bus), records_with_root, bus


# ── proposal_gate_passed ──────────────────────────────────────────────────────

def test_gate_passed_amend_emits_adopted_and_changed(sec):
    secretary, records, bus = sec
    records.put(_role("werk_rol"))
    adopted, changed = [], []
    bus.subscribe("role_adopted", adopted.append)
    bus.subscribe("governance_changed", changed.append)

    p = _amend("werk_rol")
    bus.publish(Event("proposal_gate_passed", {"proposal": proposal_to_dict(p)}, "facilitator"))

    assert len(adopted) == 1 and adopted[0].data["record_id"] == "werk_rol"
    assert len(changed) == 1 and changed[0].data["kind"] == "amend_role"


def test_gate_passed_amend_writes_accountability(sec):
    secretary, records, bus = sec
    records.put(_role("werk_rol"))

    p = _amend("werk_rol", add_accs=["wekelijks trend-rapport opstellen"])
    bus.publish(Event("proposal_gate_passed", {"proposal": proposal_to_dict(p)}, "facilitator"))

    rec = records.get("werk_rol")
    assert "wekelijks trend-rapport opstellen" in rec.definition.accountabilities
    assert rec.version == 2


def test_gate_passed_add_role_emits_born_and_changed(sec):
    secretary, records, bus = sec
    born, changed = [], []
    bus.subscribe("role_born", born.append)
    bus.subscribe("governance_changed", changed.append)

    p = _add_role("nieuwe_rol")
    bus.publish(Event("proposal_gate_passed", {"proposal": proposal_to_dict(p)}, "facilitator"))

    assert len(born) == 1 and born[0].data["role_id"] == "nieuwe_rol"
    assert len(changed) == 1 and changed[0].data["kind"] == "add_role"
    assert records.get("nieuwe_rol") is not None


# ── remove_role: archiveren én uit ouder-members prunen ───────────────────────

def _remove_role(role_id: str) -> Proposal:
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id=role_id),
        tension="opruimen", trigger_example="terugkerend", rationale="structureel",
    )


def test_gate_passed_remove_role_archiveert_en_pruunt_members(sec):
    secretary, records, bus = sec
    records.put(_role("doomed"))
    root = records.root()
    root.members = list(root.members) + ["doomed"]
    records.put(root)

    p = _remove_role("doomed")
    bus.publish(Event("proposal_gate_passed", {"proposal": proposal_to_dict(p)}, "facilitator"))

    rec = records.get("doomed")
    assert rec.archived is True
    # Geen dangling member-ref meer in de ouder-cirkel
    assert "doomed" not in records.root().members


# ── governance_verdict ────────────────────────────────────────────────────────

def test_verdict_approve_adopts(sec):
    secretary, records, bus = sec
    records.put(_role("werk_rol"))
    changed = []
    bus.subscribe("governance_changed", changed.append)

    p = _amend("werk_rol")
    bus.publish(Event("_store_pending_proposal", {"proposal": proposal_to_dict(p)}, "facilitator"))
    bus.publish(Event("governance_verdict",
                      {"proposal_id": p.id, "decision": "approve", "reason": "akkoord"},
                      "human"))

    assert len(changed) == 1
    assert records.get("werk_rol").version == 2


def test_verdict_reject_emits_rejected(sec):
    secretary, records, bus = sec
    records.put(_role("werk_rol"))
    rejected, changed = [], []
    bus.subscribe("governance_rejected", rejected.append)
    bus.subscribe("governance_changed", changed.append)

    p = _amend("werk_rol")
    bus.publish(Event("_store_pending_proposal", {"proposal": proposal_to_dict(p)}, "facilitator"))
    bus.publish(Event("governance_verdict",
                      {"proposal_id": p.id, "decision": "reject", "reason": "niet nodig"},
                      "human"))

    assert len(rejected) == 1 and rejected[0].data["proposal_id"] == p.id
    assert changed == []


def test_verdict_unknown_proposal_is_ignored(sec):
    """governance_verdict voor een onbekend proposal_id faalt stil."""
    secretary, records, bus = sec
    changed, rejected = [], []
    bus.subscribe("governance_changed", changed.append)
    bus.subscribe("governance_rejected", rejected.append)

    bus.publish(Event("governance_verdict",
                      {"proposal_id": "bestaat-niet", "decision": "approve"},
                      "human"))

    assert changed == [] and rejected == []


# ── remove_role adoption ──────────────────────────────────────────────────────

def test_approve_escalation_populates_pending_and_adopts(tmp_path):
    """Secretary._adopt archiveert een record bij REMOVE_ROLE na governance_verdict.

    Simuleert Village-herstart: Secretary._pending is leeg, approve_escalation
    herstelt het via store_pending, daarna adopteert governance_verdict de removal.
    Drie asserties: _pending gevuld, rec.archived is True, governance_changed gepubliceerd.
    """
    path = str(tmp_path / "gov.json")
    recs = Records(path)
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(purpose="test", skills=[], policies=[]),
                  members=["voorbeeld_rol"], source="seed")
    recs.put(root)
    rol = Record(id="voorbeeld_rol", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test rol",
                                           accountabilities=["iets periodiek doen"]),
                 source="seed")
    recs.put(rol)

    bus = EventBus()
    proposal = Proposal(
        proposer_role="human",
        change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id="voorbeeld_rol"),
        tension="test spanning",
        trigger_example="structureel wekelijks terugkerend: trigger",
        rationale="structureel doorlopend: rationale",
        source="sensed",
    )
    proposal_dict = proposal_to_dict(proposal)
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    iid = inbox.add_escalation(proposal_dict, gate="G3",
                               reason="rol heeft accountabilities")
    assert inbox.get(iid)["context"]["proposal"] == proposal_dict

    # Secretary met lege _pending simuleert Village-herstart
    secretary = Secretary(recs, bus)
    assert len(secretary._pending) == 0

    changed: list[dict] = []
    bus.subscribe("governance_changed", lambda e: changed.append(dict(e.data)))

    # Herstel _pending vanuit opgeslagen proposal-dict (zoals approve_escalation doet)
    reconstructed = proposal_from_dict(inbox.get(iid)["context"]["proposal"])
    secretary.store_pending(reconstructed)
    assert proposal.id in secretary._pending

    # governance_verdict approve → Secretary._adopt → archivering
    inbox.resolve(iid, "approved", reason="human goedkeuring")
    bus.publish(Event("governance_verdict",
                      {"proposal_id": proposal.id, "decision": "approve", "reason": "test"},
                      "human"))

    rec = recs.get("voorbeeld_rol")
    assert rec is not None
    assert rec.archived is True
    assert len(changed) == 1
    assert changed[0]["kind"] == "remove_role"
