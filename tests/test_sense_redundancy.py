"""Tests voor de pioniers-reflectie _sense_redundancy (R2). Thread-vrij.

Een rol wiens accountabilities volledig door andere live rollen gedekt zijn,
draft na herhaalde bevestiging (geduld) een mens-gegateerd remove_role-voorstel
voor zichzelf. De wortelcirkel doet dat nooit; een deels-ongedekte of lege rol ook niet.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType, ChangeKind
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.governance import Records, proposal_from_dict


def _role(rid, accs, parent="noochville", rtype=RecordType.ROLE):
    return Record(id=rid, type=rtype, parent=parent,
                  definition=RoleDefinition(purpose="t", accountabilities=accs), source="seed")


def _root(accs=None):
    return Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(purpose="anchor", accountabilities=accs or []),
                  source="seed")


def _records(tmp_path, *recs):
    r = Records(str(tmp_path / "gov.json"))
    for rec in recs:
        r.put(rec)
    return r


def _make_inh(tmp_path, record, records):
    bus = EventBus(name="test")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"},
                          data_dir=str(tmp_path), records=records,
                          library=None, lexicon=None, notes=None, observations=None)
    inh = Inhabitant(record, bus, SkillRegistry(), ctx)
    events: list[dict] = []
    bus.subscribe("proposal_raised", lambda e: events.append(dict(e.data)))
    return inh, events


_WATCHER = _role("watcher", ["monitor visitor traffic on the site"])


def test_redundante_rol_stelt_zichzelf_voor_opheffen(tmp_path):
    scribe = _role("scribe", ["monitor visitor traffic weekly"])  # gedekt door watcher
    recs = _records(tmp_path, _root(), _WATCHER, scribe)
    inh, events = _make_inh(tmp_path, scribe, recs)

    # geduld: eerste reflectie nog geen voorstel
    assert inh._sense_redundancy() is False
    assert events == []
    # tweede reflectie: voorstel
    assert inh._sense_redundancy() is True
    assert len(events) == 1
    prop = proposal_from_dict(events[0]["proposal"])
    assert prop.change.kind == ChangeKind.REMOVE_ROLE
    assert prop.change.role_id == "scribe"
    assert prop.proposer_role == "scribe"


def test_niet_redundant_geen_voorstel(tmp_path):
    harry = _role("harry", ["ground keywords in academic literature"])  # niet gedekt
    recs = _records(tmp_path, _root(), _WATCHER, harry)
    inh, events = _make_inh(tmp_path, harry, recs)
    assert inh._sense_redundancy() is False
    assert inh._sense_redundancy() is False
    assert events == []


def test_dedup_geen_herhaald_voorstel(tmp_path):
    scribe = _role("scribe", ["monitor visitor traffic weekly"])
    recs = _records(tmp_path, _root(), _WATCHER, scribe)
    inh, events = _make_inh(tmp_path, scribe, recs)
    inh._sense_redundancy()
    inh._sense_redundancy()
    inh._sense_redundancy()   # derde keer: niets nieuws
    assert len(events) == 1


def test_wortelcirkel_heft_zichzelf_nooit_op(tmp_path):
    # root heeft accountabilities die door watcher gedekt zouden zijn, maar de guard bailt
    root = _root(["monitor visitor traffic"])
    recs = _records(tmp_path, root, _WATCHER)
    inh, events = _make_inh(tmp_path, root, recs)
    assert inh._sense_redundancy() is False
    assert inh._sense_redundancy() is False
    assert events == []


def test_rol_zonder_accountabilities_niet_redundant(tmp_path):
    empty = _role("empty", [])
    recs = _records(tmp_path, _root(), _WATCHER, empty)
    inh, events = _make_inh(tmp_path, empty, recs)
    assert inh._sense_redundancy() is False
    assert events == []
