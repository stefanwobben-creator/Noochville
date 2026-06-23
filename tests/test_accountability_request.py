"""Tests voor spelregel 5: rol-vraagt-rol om een accountability. Thread-vrij.

We testen de dispatch-logica synchroon (roepen _on_accountability_requested direct aan),
zonder de inwoner-thread te starten.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry


def _inhabitant(bus, rid="rol_a"):
    rec = Record(id=rid, type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test"), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"})
    return Inhabitant(rec, bus, SkillRegistry(), ctx)


def _req(target, key, payload=None, frm="rol_b"):
    return Event("accountability_requested",
                 {"target": target, "accountability": key,
                  "payload": payload or {}, "from": frm}, frm)


# ── offer ─────────────────────────────────────────────────────────────────────

def test_offer_registreert_handler():
    inh = _inhabitant(EventBus(name="t"))
    inh.offer("nl_corpus_coverage", lambda p: None)
    assert "nl_corpus_coverage" in inh._offered


# ── ask_accountability publiceert het verzoek ─────────────────────────────────

def test_ask_accountability_publiceert_verzoek():
    bus = EventBus(name="t")
    events = []
    bus.subscribe("accountability_requested", lambda e: events.append(e))
    asker = _inhabitant(bus, "rol_b")
    asker.ask_accountability("harry_hemp", "nl_corpus_coverage", {"locale": "nl"})
    assert len(events) == 1
    d = events[0].data
    assert d["target"] == "harry_hemp"
    assert d["accountability"] == "nl_corpus_coverage"
    assert d["payload"] == {"locale": "nl"}
    assert d["from"] == "rol_b"


# ── dispatch ──────────────────────────────────────────────────────────────────

def test_dispatch_roept_handler_aan_met_payload():
    inh = _inhabitant(EventBus(name="t"))
    gezien = []
    inh.offer("doe_iets", lambda p: gezien.append(p))
    inh._on_accountability_requested(_req("rol_a", "doe_iets", {"x": 1}))
    assert gezien == [{"x": 1}]


def test_dispatch_negeert_ander_doel():
    inh = _inhabitant(EventBus(name="t"))
    gezien = []
    inh.offer("doe_iets", lambda p: gezien.append(p))
    inh._on_accountability_requested(_req("iemand_anders", "doe_iets"))
    assert gezien == []          # niet aan mij gericht


def test_onbekende_accountability_senst_spanning():
    inh = _inhabitant(EventBus(name="t"))
    gesenst = []
    inh.sense_tension = lambda desc, kind="operational": gesenst.append((desc, kind))
    inh._on_accountability_requested(_req("rol_a", "ken_ik_niet"))
    assert len(gesenst) == 1
    assert "ken_ik_niet" in gesenst[0][0]
