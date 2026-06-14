"""Integratietest: twee-slag-gate + classify_gap op de geboorte-naad, thread-vrij.

Volledig pad dat getest wordt:
  _sense_gap (1×) → registreer (1/2 — nog geen spanning)
  _sense_gap (2×) → count=2 → sense_tension → triage → _raise_governance_proposal
                 → classify_gap → A (gedekt) of C (nieuw gat)

_classify_llm is gepatchd naar "structural" zodat triage deterministisch naar
_raise_governance_proposal doorloopt, ook als er geen API-key beschikbaar is.
De twee-slag-gate (_sense_gap met min_count=2) wordt zelf meegenomen: op de eerste
aanroep wordt de spanning geregistreerd maar niet gesensed; op de tweede vliegt
sense_tension daadwerkelijk.

Noochie-record in de fixture heeft dummy skills die missie/veganistisch dekken,
zodat de drie junk-beschrijvingen een classify_gap A-uitkomst geven.
"""
from __future__ import annotations
import pytest
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.seeds import seed_records
from nooch_village.skills import SkillRegistry
from nooch_village.inhabitant import Inhabitant


class _FakeContext:
    def __init__(self, records, data_dir, settings=None):
        self.records = records
        self.data_dir = str(data_dir)
        self.settings = settings or {}


def _make_inhabitant(records, bus, data_dir):
    rec = records.get("noochie")
    return Inhabitant(rec, bus, SkillRegistry(), _FakeContext(records, data_dir))


@pytest.fixture()
def records(tmp_path):
    recs = Records(str(tmp_path / "gov.json"))
    seed_records(recs)
    # Noochie met skills die missie/veganistisch dekken → classify_gap geeft A
    # voor alle drie junk-beschrijvingen.
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
            # Dummy skills: missie/alignment + veganistisch → means-dekking ≥ 0.15
            # voor de drie junk-beschrijvingen → classify_gap A (niet B of C).
            skills=["missie_alignment_check", "veganistisch_standpunt"],
        ),
    ))
    return recs


def _two_strikes(inh: Inhabitant, gap_key: str, description: str) -> None:
    """Roep _sense_gap twee keer aan; de tweede vuurt sense_tension."""
    with patch.object(inh, "_classify_llm", return_value="structural"):
        inh._sense_gap(gap_key, description, kind="governance", min_count=2)
        inh._sense_gap(gap_key, description, kind="governance", min_count=2)


def _add_role_events(proposals: list) -> list:
    return [p for p in proposals
            if p.data.get("proposal", {}).get("change", {}).get("kind") == "add_role"]


# ── Junk-beschrijvingen: A via twee-slag-gate ─────────────────────────────────

@pytest.mark.parametrize("description", [
    "Beheert en bewaakt missie-alignment, missie-gedreven, transparantie, kernwaarden.",
    "Beheert en bewaakt veganistisch, missie-lens, niche-label, doorbreken.",
    "Beheert en bewaakt missie-alignment, marketingtruc, veganistisch, onderscheid.",
])
def test_junk_gap_blocked_at_two_strike_gate(tmp_path, records, description):
    """Junk-missie-gap: 2×_sense_gap → sense_tension → triage(structureel)
    → classify_gap A (gedekt door noochie) → geen ADD_ROLE, geen role_born."""
    bus = EventBus(name="test")
    proposals = []
    bus.subscribe("proposal_raised", lambda e: proposals.append(e))

    inh = _make_inhabitant(records, bus, tmp_path / "data")
    gap_key = f"junk_{abs(hash(description)) % 10**8}"
    _two_strikes(inh, gap_key, description)

    assert _add_role_events(proposals) == [], (
        f"Junk-beschrijving passeerde de gate en genereerde ADD_ROLE:\n  {description!r}"
    )


# ── Verify eerste slag registreert maar stelt niet voor ───────────────────────

def test_first_strike_does_not_fire_sense_tension(tmp_path, records):
    """De eerste _sense_gap mag nog geen spanning produceren (1/2 nog niet gehaald)."""
    bus = EventBus(name="test")
    tensions = []
    bus.subscribe("tension_sensed", lambda e: tensions.append(e))

    inh = _make_inhabitant(records, bus, tmp_path / "data")
    with patch.object(inh, "_classify_llm", return_value="structural"):
        inh._sense_gap("gate_test", "missie-alignment ontbreekt structureel", min_count=2)

    assert tensions == [], "Eerste slag mag nog geen tension_sensed publiceren"


# ── C-tegenproef: echt nieuw gat bereikt ADD_ROLE-pad ────────────────────────

def test_uncovered_gap_reaches_add_role_via_two_strike_gate(tmp_path, records):
    """Ongedekte C-gap: 2×_sense_gap → sense_tension → classify_gap C → ADD_ROLE-voorstel."""
    bus = EventBus(name="test")
    proposals = []
    bus.subscribe("proposal_raised", lambda e: proposals.append(e))

    inh = _make_inhabitant(records, bus, tmp_path / "data")
    _two_strikes(inh, "legal_compliance_gat", "legal compliance audit required")

    add_role = _add_role_events(proposals)
    assert len(add_role) == 1, (
        "Ongedekte C-gap moet na twee slagen precies één ADD_ROLE-voorstel opleveren"
    )
