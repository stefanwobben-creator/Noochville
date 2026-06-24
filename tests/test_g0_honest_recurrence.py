"""R1a-hardening: G0 toetst echt herhalingsbewijs, geen zelfgeschreven boilerplate.

De bug: de C-weg plakte "Structureel terugkerend gat" in de rationale, en G0 las
trigger_example + rationale samen. Zo keurde de poort zijn eigen boilerplate goed
en werden nep-rollen geboren. Nu leest G0 alleen de trigger (de waargenomen feiten
uit het logboek), en weigert hij mechanische term-smurrie als purpose.

Thread-vrij; geen netwerk (llm.reason gemockt waar de coherentiepoort meedraait)."""
from __future__ import annotations
import time
import pytest
from unittest.mock import patch

from nooch_village.governance import Gate, Records
from nooch_village.models import (
    Proposal, GovernanceChange, ChangeKind, Record, RecordType, RoleDefinition, Tension,
)
from nooch_village.seeds import seed_records
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.inhabitant import Inhabitant


gate = Gate()


def _add_role_proposal(trigger, rationale, purpose="een echte functie vervullen"):
    return Proposal(
        proposer_role="test_rol",
        change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="nieuwe_rol",
                                purpose=purpose),
        tension="test",
        trigger_example=trigger,
        rationale=rationale,
        source="sensed",
    )


# ── DE EXPLOIT-GUARD: gefabriceerde rationale telt niet meer ──────────────────

def test_gefabriceerde_rationale_wordt_geweigerd(records_with_root):
    """Recurrence-woord alleen in de rationale (de oude exploit) → G0 weigert."""
    p = _add_role_proposal(
        trigger="test_rol: eenmalig dingetje gezien",      # GEEN herhaling
        rationale="Structureel terugkerend gat: geen rol dekt dit.",  # boilerplate
    )
    passed, gate_name, reason = gate.check(p, records_with_root)
    assert not passed
    assert gate_name == "G0"
    assert "herhalingsbewijs" in reason


def test_echt_bewijs_in_trigger_passeert_g0(records_with_root):
    """Herhaling in de trigger (uit het logboek) → G0 laat door."""
    p = _add_role_proposal(
        trigger="test_rol: gat meermaals waargenomen (3x sinds 2026-06-10); legal audit",
        rationale="neutrale toelichting zonder bewijswoorden",
    )
    passed, gate_name, _ = gate.check(p, records_with_root)
    assert passed or gate_name != "G0"


def test_slug_purpose_wordt_geweigerd(records_with_root):
    """Mechanische term-smurrie als purpose → G0 weigert, ook mét herhalingsbewijs."""
    p = _add_role_proposal(
        trigger="test_rol: gat meermaals waargenomen (4x sinds 2026-06-01); x",
        rationale="neutraal",
        purpose="Beheert en bewaakt vegan, plastic, schoenen, transparantie.",
    )
    passed, gate_name, reason = gate.check(p, records_with_root)
    assert not passed
    assert gate_name == "G0"
    assert "woordcluster" in reason or "term-opsomming" in reason


# ── Integratie: _sense_gap-bewijs landt als echte telling in de trigger ───────

class _Ctx:
    def __init__(self, records):
        self.records = records
        self.settings = {}


@pytest.fixture()
def seeded(tmp_path):
    recs = Records(str(tmp_path / "gov.json"))
    seed_records(recs)
    return recs


def _inh(records, bus):
    rec = Record(id="test_rol", type=RecordType.ROLE, parent="noochville",
                 source="seed", definition=RoleDefinition(purpose="Test"))
    return Inhabitant(rec, bus, SkillRegistry(), _Ctx(records))


def test_evidence_stempelt_meermaals_in_trigger(seeded):
    """Een Tension mét logboek-bewijs (obs=3) → trigger bevat 'meermaals' + telling."""
    bus = EventBus(name="test")
    proposals = []
    bus.subscribe("proposal_raised", lambda e: proposals.append(e))

    inh = _inh(seeded, bus)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: coherent\nREASON: heldere rol"):
        inh._raise_governance_proposal(Tension(
            sensed_by="test_rol",
            description="recurring legal compliance audit needed",
            kind="structural",
            evidence={"observations": 3, "first_seen": time.time() - 86400, "gap_key": "x"},
        ))

    add_role = [p for p in proposals
                if p.data["proposal"]["change"]["kind"] == "add_role"]
    assert len(add_role) == 1
    trigger = add_role[0].data["proposal"]["trigger_example"].lower()
    assert "meermaals" in trigger
    assert "3x" in trigger


def test_neutrale_trigger_wordt_door_g0_geweigerd(records_with_root):
    """Een add_role-voorstel met een neutrale trigger (geen herhaling) → G0 weigert.
    (Het integratie-pad zonder bewijs levert sinds R1b sowieso geen add_role meer op,
    maar de Gate-regel zelf moet onafhankelijk blijven gelden.)"""
    p = _add_role_proposal(trigger="test_rol:eenmalig dingetje gezien", rationale="neutraal")
    passed, gate_name, _ = gate.check(p, records_with_root)
    assert not passed and gate_name == "G0"
