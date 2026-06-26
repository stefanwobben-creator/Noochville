"""Brok 2 — de autonome pull-scheduler (board_loop.activate_pulse). Toetst de vier guardrails:
master-switch, WIP (bord+rol, ook bij hervatten), fallback naar mens, en prioritering."""
from __future__ import annotations
import os
import tempfile

from nooch_village.projects import ProjectLedger
from nooch_village.board_loop import activate_pulse
from nooch_village.business_case import make_business_case


def _led():
    return ProjectLedger(os.path.join(tempfile.mkdtemp(), "p.json"))


def _active(led):
    return [p["id"] for p in led.all() if p["status"] == "running"]


def test_master_switch():
    led = _led()
    root = led.create("the_source", "idee", "human", status="future")
    a = led.create("harry", "taak A", "human", status="future", parent=root)
    # root future → lid activeert niet
    assert activate_pulse(led, ["harry"])["activated"] == []
    assert _active(led) == []
    # mens zet root actief → lid activeert
    led.start(root)
    res = activate_pulse(led, ["harry"])
    assert a in res["activated"] and a in _active(led)


def test_wip_board_en_rol():
    led = _led()
    root = led.create("the_source", "idee", "human", status="future")
    led.start(root)   # cluster aan
    leden = [led.create("harry", f"t{i}", "human", status="future", parent=root) for i in range(5)]
    # board cap 2 (root telt NIET als running? root is 'running' → telt mee). Zet board=3, rol harry=2.
    activate_pulse(led, ["harry"], wip={"board": 3, "roles": {"harry": 2}})
    # harry mag max 2 actief; board max 3 (root + 2 leden)
    assert sum(1 for p in led.all() if p["status"] == "running" and p["owner"] == "harry") == 2
    assert len(_active(led)) == 3


def test_fallback_onbemande_eigenaar():
    led = _led()
    root = led.create("the_source", "idee", "human", status="future"); led.start(root)
    a = led.create("ronnie", "taak voor onbemande rol", "human", status="future", parent=root)
    res = activate_pulse(led, ["harry"])           # ronnie niet beschikbaar
    assert a in res["escalated"]
    assert led.get(a)["status"] == "blocked" and "onbemand" in led.get(a)["blocked_on"]


def test_resume_is_wip_gated():
    led = _led()
    root = led.create("the_source", "idee", "human", status="future"); led.start(root)
    dep = led.create("scout", "levert iets", "human", status="future", parent=root)
    waiter = led.create("harry", "wacht op scout", "human", status="future", parent=root)
    led.wait_for(waiter, "nodig: scout-resultaat", on_id=dep)
    led.complete(dep)                              # blokkade klaar
    # board cap 1: root is al 'running' (1) → geen ruimte → waiter hervat NIET (WIP-gated bij hervatten)
    res = activate_pulse(led, ["harry", "scout"], wip={"board": 1, "roles": {}})
    assert res["resumed"] == [] and led.get(waiter)["status"] == "blocked"
    # board cap 3 → wel ruimte → hervat
    res2 = activate_pulse(led, ["harry", "scout"], wip={"board": 3, "roles": {}})
    assert waiter in res2["resumed"] and led.get(waiter)["status"] == "running"


def test_prioritering_hoogste_value_eerst():
    led = _led()
    root = led.create("the_source", "idee", "human", status="future"); led.start(root)
    laag = led.create("harry", "laag", "human", status="future", parent=root,
                      business_case=make_business_case(effect=10, effort=5, confidence=0.3))
    hoog = led.create("harry", "hoog", "human", status="future", parent=root,
                      business_case=make_business_case(effect=100, effort=2, confidence=0.9))
    # maar één plek vrij naast de root → de hoogste value moet gekozen worden
    activate_pulse(led, ["harry"], wip={"board": 2, "roles": {}})
    assert led.get(hoog)["status"] == "running" and led.get(laag)["status"] == "future"
