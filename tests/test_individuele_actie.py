"""R1b-hardening: categorie-splitsing (Holacracy).

Een rol is een DOORLOPENDE verantwoordelijkheid. Een ongedekt gat zonder
herhalingsbewijs is geen rol maar een EENMALIGE individuele actie → naar de mens,
niet als rol-geboorte. Mét herhalingsbewijs → wel een rol-voorstel.

Thread-vrij; llm.reason gemockt voor de coherentiepoort."""
from __future__ import annotations
import time
import pytest
from unittest.mock import patch

from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition, Tension
from nooch_village.seeds import seed_records
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.inhabitant import Inhabitant


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


_DESC = "recurring legal compliance audit needed"


def _capture(bus):
    events = {"proposal_raised": [], "individuele_actie": []}
    for name in events:
        bus.subscribe(name, lambda e, n=name: events[n].append(e))
    return events


def test_geen_herhaling_wordt_individuele_actie(seeded):
    """C-gap zonder logboek-bewijs → individuele_actie, GEEN rol-voorstel."""
    bus = EventBus(name="test")
    events = _capture(bus)
    inh = _inh(seeded, bus)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: coherent\nREASON: ok"):
        inh._raise_governance_proposal(
            Tension(sensed_by="test_rol", description=_DESC, kind="structural"))

    assert len(events["individuele_actie"]) == 1
    add_role = [p for p in events["proposal_raised"]
                if p.data["proposal"]["change"]["kind"] == "add_role"]
    assert add_role == []


def test_met_herhaling_wordt_rol_voorstel(seeded):
    """C-gap mét logboek-bewijs (obs=3) → rol-voorstel, GEEN individuele actie."""
    bus = EventBus(name="test")
    events = _capture(bus)
    inh = _inh(seeded, bus)
    with patch("nooch_village.llm.reason",
               return_value="VERDICT: coherent\nREASON: ok"):
        inh._raise_governance_proposal(Tension(
            sensed_by="test_rol", description=_DESC, kind="structural",
            evidence={"observations": 3, "first_seen": time.time() - 86400, "gap_key": "x"}))

    assert events["individuele_actie"] == []
    add_role = [p for p in events["proposal_raised"]
                if p.data["proposal"]["change"]["kind"] == "add_role"]
    assert len(add_role) == 1


def test_village_routeert_individuele_actie_naar_inbox(tmp_path):
    """Het individuele_actie-event landt als inspectie-item in de human inbox."""
    from nooch_village.village import Village
    v = Village(heartbeat_seconds=86400, data_dir=str(tmp_path / "box"))
    before = len(v.human_inbox.pending())
    from nooch_village.event_bus import Event
    v.bus.publish(Event("individuele_actie",
                        {"gap_key": "eenmalig_dingetje", "description": "iets eenmaligs",
                         "by": "test_rol"}, "test_rol"))
    after = v.human_inbox.pending()
    assert len(after) == before + 1
    assert any("individuele actie"
               in i.get("context", {}).get("description", "").lower() for i in after)
