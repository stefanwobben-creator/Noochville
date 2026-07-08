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


# ── generieke offer→complete-lus (voorheen half af: alleen nl_corpus meldde af) ─────────────────

def test_dispatch_publiceert_generieke_completion():
    """Na de handler volgt een accountability_check_completed met het resultaat, zodat een wachter
    (bv. de ask_accountability-CLI) altijd antwoord krijgt — ook zonder eigen, specifiek event."""
    bus = EventBus(name="t")
    done = []
    bus.subscribe("accountability_check_completed", lambda e: done.append(e.data))
    inh = _inhabitant(bus)
    inh.offer("doe_iets", lambda p: {"antwoord": 42})
    inh._on_accountability_requested(_req("rol_a", "doe_iets", {"x": 1}))
    assert len(done) == 1
    assert done[0]["target"] == "rol_a"
    assert done[0]["accountability"] == "doe_iets"
    assert done[0]["result"] == {"antwoord": 42}
    assert done[0]["ok"] is True


def test_handler_zonder_dict_return_unblockt_wachter():
    """Een handler die None teruggeeft (zoals nl_corpus, dat z'n eigen event publiceert) → generieke
    completion carriert een lege result maar unblockt de wachter wel (niet-lege data + ok=True)."""
    bus = EventBus(name="t")
    done = []
    bus.subscribe("accountability_check_completed", lambda e: done.append(e.data))
    inh = _inhabitant(bus)
    inh.offer("doe_iets", lambda p: None)
    inh._on_accountability_requested(_req("rol_a", "doe_iets"))
    assert len(done) == 1 and done[0]["result"] == {} and done[0]["ok"] is True


def test_geen_completion_bij_ander_doel_of_onbekende_accountability():
    bus = EventBus(name="t")
    done = []
    bus.subscribe("accountability_check_completed", lambda e: done.append(e.data))
    inh = _inhabitant(bus)
    inh.offer("doe_iets", lambda p: {"ok": 1})
    inh._on_accountability_requested(_req("iemand_anders", "doe_iets"))     # ander doel → geen completion
    inh.sense_tension = lambda *a, **k: None
    inh._on_accountability_requested(_req("rol_a", "ken_ik_niet"))          # onbekend → geen completion
    assert done == []
