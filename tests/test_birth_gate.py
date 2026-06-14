"""Thread-vrije regressietest: classify_gap bewaakt de geboorte-naad.

Drie scenario's:
  JUNK  de 3 junk-beschrijvingen van vanmiddag → geen ADD_ROLE, geen role_born.
  C     echt ongedekt gat (legal compliance)   → ADD_ROLE-voorstel door de engine.
  B     B-spanning (middelen ontbreken)        → means_gap_sensed, geen ADD_ROLE.

Inhabitant._raise_governance_proposal() wordt rechtstreeks aangeroepen;
de thread wordt nooit gestart (geen start(), geen join()).
"""
from __future__ import annotations
import pytest
from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.human_inbox import HumanInbox
from nooch_village.models import Record, RecordType, RoleDefinition, Tension
from nooch_village.seeds import seed_records
from nooch_village.skills import SkillRegistry
from nooch_village.inhabitant import Inhabitant


class _FakeContext:
    def __init__(self, records, settings=None):
        self.records = records
        self.settings = settings or {}


def _make_inhabitant(records, bus):
    rec = Record(
        id="test_rol", type=RecordType.ROLE, parent="noochville", source="seed",
        definition=RoleDefinition(purpose="Test"),
    )
    return Inhabitant(rec, bus, SkillRegistry(), _FakeContext(records))


@pytest.fixture()
def records(tmp_path):
    recs = Records(str(tmp_path / "gov.json"))
    seed_records(recs)
    # Noochie: missie-mandaat (bewaken, transparantie, veganistisch), geen skills.
    # Junk-beschrijvingen raken dit mandaat → B-uitkomst (geen geboorte).
    recs.put(Record(
        id="noochie", type=RecordType.ROLE, parent="noochville", source="sensed",
        definition=RoleDefinition(
            purpose=(
                "De missie belichamen en bepleiten in het dorp. "
                "Kernwaarden: veganistisch, transparantie, missie-gedreven."
            ),
            accountabilities=[
                "missie-alignment bewaken en bepleiten via governance",
                "de stem van het merk zijn: veganistisch en duurzaam standpunt bewaken",
                "kernwaarden bewaken: transparantie, missie-gedreven, niche-label",
            ],
            skills=[],
        ),
    ))
    return recs


# ── JUNK: gedekte beschrijvingen blokkeren geboorte ──────────────────────────

@pytest.mark.parametrize("description", [
    "Beheert en bewaakt missie-alignment, missie-gedreven, transparantie, kernwaarden.",
    "Beheert en bewaakt veganistisch, missie-lens, niche-label, doorbreken.",
    "Beheert en bewaakt missie-alignment, marketingtruc, veganistisch, onderscheid.",
])
def test_junk_description_produces_no_birth(tmp_path, records, description):
    """Junk-beschrijvingen die bestaand mandaat raken, mogen geen ADD_ROLE doorsturen."""
    bus = EventBus(name="test")
    add_role_events = []
    bus.subscribe("proposal_raised", lambda e: (
        add_role_events.append(e)
        if e.data.get("proposal", {}).get("change", {}).get("kind") == "add_role"
        else None
    ))

    inh = _make_inhabitant(records, bus)
    inh._raise_governance_proposal(
        Tension(sensed_by="test_rol", description=description, kind="structural"))

    assert add_role_events == [], (
        f"Junk-beschrijving stuurde toch een ADD_ROLE-voorstel door:\n  {description!r}"
    )


# ── C: echt ongedekt gat → ADD_ROLE-pad ──────────────────────────────────────

def test_truly_new_gap_reaches_add_role_path(tmp_path, records):
    """Een echt ongedekt gat (legal compliance) bereikt het ADD_ROLE-voorstel."""
    bus = EventBus(name="test")
    proposals = []
    bus.subscribe("proposal_raised", lambda e: proposals.append(e))

    inh = _make_inhabitant(records, bus)
    inh._raise_governance_proposal(
        Tension(sensed_by="test_rol",
                description="legal compliance audit required", kind="structural"))

    add_role = [p for p in proposals
                if p.data.get("proposal", {}).get("change", {}).get("kind") == "add_role"]
    assert len(add_role) == 1, (
        "Legal compliance gap moet precies één ADD_ROLE-voorstel opleveren"
    )


# ── B: middelen ontbreken → means_gap_sensed, geen ADD_ROLE ──────────────────

def test_b_gap_publishes_means_gap_not_add_role(tmp_path, records):
    """B-spanning: mandaat gedekt door analyst, skills ontbreken → means_gap, geen ADD_ROLE."""
    bus = EventBus(name="test")
    add_role_events = []
    means_gaps = []
    bus.subscribe("proposal_raised", lambda e: (
        add_role_events.append(e)
        if e.data.get("proposal", {}).get("change", {}).get("kind") == "add_role"
        else None
    ))
    bus.subscribe("means_gap_sensed", lambda e: means_gaps.append(e))

    inh = _make_inhabitant(records, bus)
    # Analyst dekt "bezoekersdata" in mandaat, maar heeft geen conversiemeting-skill → B
    inh._raise_governance_proposal(
        Tension(sensed_by="test_rol",
                description="bezoekersdata conversiemeting ontbreekt voor doelgroepanalyse",
                kind="structural"))

    assert add_role_events == [], "B-spanning mag geen ADD_ROLE opleveren"
    assert len(means_gaps) == 1, "B-spanning moet means_gap_sensed publiceren"
