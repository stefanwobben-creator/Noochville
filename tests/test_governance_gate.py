"""De geldigheidspoort hoort bij de motor, niet bij een rol.

Op 28 augustus 2026 legde een afslankingsronde `facilitator` slapend en stond het dorp drie dagen
stil: de dagcadans woonde in die rol en niemand luidde de bel meer. Zonder foutmelding, want er
faalde niets. De klok is toen naar `Dagcyclus` verhuisd.

De G0-G4 poort bleef zitten, en dat was dezelfde weeffout één laag dieper: `_on_proposal_raised` was
in productie de ENIGE luisteraar op `proposal_raised`. Archiveer of verslaap die rol en élk
governance-voorstel blijft stil liggen — precies op het moment dat je de rollen gaat opruimen en dus
het meeste governance-verkeer hebt.

Wat hieronder wordt vastgelegd:

1. De poort draait zonder dat er ook maar één rol bestaat.
2. Hij draait maar ÉÉN keer per voorstel (geen dubbele afhandeling na de verhuizing).
3. De Facilitator-rol luistert niet meer, en kan dus zonder gevolgen slapen of weg.
4. De drie uitkomsten (aangenomen, G0-ongeldig, geëscaleerd) gedragen zich als voorheen.
"""
from __future__ import annotations

import pytest

from nooch_village.event_bus import EventBus, Event
from nooch_village.governance import (GovernanceGate, Records, proposal_to_dict)
from nooch_village.models import (Proposal, GovernanceChange, ChangeKind, Record, RecordType,
                                  RoleDefinition)


@pytest.fixture()
def dorp(tmp_path):
    records = Records(str(tmp_path / "records.json"))
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(purpose="wortel"), members=[], source="seed")
    records.put(root)
    bus = EventBus(name="test")
    gevangen: dict[str, list] = {}
    for ev in ("proposal_gate_passed", "proposal_invalid", "governance_review_requested",
               "_store_pending_proposal"):
        gevangen[ev] = []
        bus.subscribe(ev, (lambda naam: lambda e: gevangen[naam].append(e))(ev))
    gate = GovernanceGate(records, bus, None)
    return records, bus, gate, gevangen


def _voorstel(**kw):
    change = GovernanceChange(kind=ChangeKind.ADD_ROLE,
                              role_id=kw.pop("role_id", "nieuwe_rol"),
                              purpose=kw.pop("purpose", "Iets nuttigs doen voor het dorp"),
                              new_role_parent=kw.pop("parent", "noochville"))
    return Proposal(proposer_role=kw.pop("proposer_role", "the_source"), change=change,
                    tension=kw.pop("tension", "er is niemand die dit oppakt"),
                    trigger_example=kw.pop(
                        "trigger_example",
                        "dit komt structureel terug, wekelijks in het roloverleg"),
                    rationale=kw.pop("rationale", "dit werk komt structureel terug"), **kw)


def _raise(bus, p):
    bus.publish(Event("proposal_raised", {"proposal": proposal_to_dict(p)}, "test"))


# ── 1. de poort staat los van elke rol ───────────────────────────────────────

def test_poort_draait_zonder_dat_er_een_rol_bestaat(dorp):
    """DE KERNTEST. Geen Reconciler, geen inwoner, geen facilitator — en toch een oordeel."""
    _records, bus, _gate, gevangen = dorp
    _raise(bus, _voorstel())
    totaal = sum(len(v) for v in gevangen.values())
    assert totaal >= 1, "geen enkel event: het voorstel is stil blijven liggen"


def test_facilitator_luistert_niet_meer():
    """Zou hij dat wél doen, dan wordt elk voorstel na de verhuizing dubbel afgehandeld."""
    import inspect
    from nooch_village.roles import Facilitator
    src = inspect.getsource(Facilitator)
    assert 'react("proposal_raised"' not in src
    assert "GovernanceGate" in src            # de verwijzing waar het nu wél woont


def test_het_dorp_hangt_de_poort_op():
    import inspect
    from nooch_village import village
    src = inspect.getsource(village)
    assert "GovernanceGate(" in src


# ── 2. precies één keer ──────────────────────────────────────────────────────

def test_een_voorstel_wordt_een_keer_beoordeeld(dorp):
    _records, bus, _gate, gevangen = dorp
    _raise(bus, _voorstel())
    beslissingen = (len(gevangen["proposal_gate_passed"])
                    + len(gevangen["proposal_invalid"])
                    + len(gevangen["governance_review_requested"]))
    assert beslissingen == 1, f"{beslissingen} oordelen over één voorstel"


# ── 3. de drie uitkomsten ────────────────────────────────────────────────────

def test_geldig_voorstel_wordt_aangenomen(dorp):
    _records, bus, _gate, gevangen = dorp
    _raise(bus, _voorstel())
    assert len(gevangen["proposal_gate_passed"]) == 1
    assert not gevangen["proposal_invalid"]


def test_structureel_ongeldig_gaat_terug_naar_de_proposer(dorp):
    """G0 is 'dit kan niet bestaan', en dat is geen mensenwerk maar een vormfout."""
    _records, bus, _gate, gevangen = dorp
    _raise(bus, _voorstel(purpose="", role_id=""))
    assert len(gevangen["proposal_invalid"]) == 1
    assert gevangen["proposal_invalid"][0].data["gate"] == "G0"
    assert not gevangen["proposal_gate_passed"]


def test_de_afzender_is_het_dorp_en_niet_een_rol(dorp):
    """Zodat je in de logs en op de bus ziet dat de poort van de motor komt."""
    _records, bus, _gate, gevangen = dorp
    _raise(bus, _voorstel())
    assert gevangen["proposal_gate_passed"][0].sender == GovernanceGate.BRON
    assert GovernanceGate.BRON != "facilitator"


# ── 4. de bekende val ────────────────────────────────────────────────────────

def test_slapende_facilitator_legt_governance_niet_stil(dorp):
    """De regressietest op 28 augustus, nu voor de poort in plaats van de klok.

    We bouwen geen rol; dat IS de situatie na archiveren. Als deze test ooit faalt omdat iemand de
    poort terugzet in een rol, dan is dat precies de fout die drie dagen stilstand kostte."""
    _records, bus, _gate, gevangen = dorp
    for n in range(3):
        _raise(bus, _voorstel(role_id=f"rol_{n}"))
    assert len(gevangen["proposal_gate_passed"]) == 3
