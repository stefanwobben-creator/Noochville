"""Brok 4 — discovery-rollen bedraad op het bord: afgebakende projecten (één seed → één
deliverable), board-gedreven (WIP + master-switch), uitkomst → briefje + Librarian-review,
spaced repetition, en 'door de seeds heen → verzoek aan Harry'."""
from __future__ import annotations
import os
import tempfile

from nooch_village.projects import ProjectLedger
from nooch_village.pinboard import Pinboard
from nooch_village.library import Library
from nooch_village import discovery_board as db


def _stores():
    d = tempfile.mkdtemp()
    return (ProjectLedger(os.path.join(d, "p.json")),
            Pinboard(os.path.join(d, "pin.json")),
            Library(os.path.join(d, "lib.json")))


def _seed(lib, *words):
    for w in words:
        lib.curate(w, "approved", by="test")
        lib.set_function(w, "volg")


def test_ensure_root_idempotent():
    led, _, _ = _stores()
    a = db.ensure_root(led)
    b = db.ensure_root(led)
    assert a == b == db.DISCOVERY_ROOT
    assert led.get(db.DISCOVERY_ROOT)["status"] == "future"     # master-switch standaard uit
    assert sum(1 for p in led.all() if p["id"] == db.DISCOVERY_ROOT) == 1


def test_make_project_dedup_en_contract():
    led, _, _ = _stores()
    pid = db.make_discovery_project(led, "harry_hemp", "nieuwe seeds")
    assert pid is not None
    p = led.get(pid)
    assert p["status"] == "future" and p["parent"] == db.DISCOVERY_ROOT
    assert p["cluster"] == db.DISCOVERY_ROOT and p["origin"] == "discovery"
    assert p["done_when"] and p["goes_to"] == "librarian"
    assert db.make_discovery_project(led, "harry_hemp", "nieuwe seeds") is None   # dedup


def test_spaced_seed_kiest_oudste():
    assert db.spaced_seed([], {}) is None
    assert db.spaced_seed(["a", "b"], {}) in ("a", "b")            # ongezien
    assert db.spaced_seed(["a", "b"], {"a": 100.0, "b": 5.0}) == "b"  # b langst geleden


def test_harvest_done_briefje_en_review_dedup():
    led, pin, lib = _stores()
    lib.curate("bekend", "approved", by="test")                   # al bekend → niet routeren
    pid = db.make_discovery_project(led, "harry_hemp", "nieuwe seeds")
    led.start(led.get(db.DISCOVERY_ROOT)["id"]); led.start(pid)
    routed = []
    h = db.harvest(led, pin, pid, ["hennepschoen", "bekend", "  "],
                   route_review=lambda t: routed.append(t) or True, library=lib)
    assert h["fresh"] == ["hennepschoen"] and routed == ["hennepschoen"]
    assert led.get(pid)["status"] == "done"
    # uitkomst-briefje op het prikbord, gelinkt aan het project
    out = [b for b in pin.all() if b["kind"] == "outcome"]
    assert out and out[0]["tag"] == db.TAG["harry_hemp"] and pid in out[0]["links"]


def test_pulse_master_switch_en_oogst():
    led, pin, lib = _stores()
    _seed(lib, "hennep")
    # root nog future → niets activeert (master-switch uit)
    res0 = db.run_discovery_pulse(led, pin, lib, ["harry_hemp", "trends", "concurrent_scout"],
                                  wip={"board": 9, "roles": {}},
                                  do_discovery=lambda o, s: ["x_" + o], route_review=lambda t: True)
    assert res0["activated"] == [] and res0["created"]
    # mens zet de master-switch aan
    led.start(db.ensure_root(led))
    state = {}
    res = db.run_discovery_pulse(led, pin, lib, ["harry_hemp", "trends", "concurrent_scout"],
                                 wip={"board": 9, "roles": {}},
                                 do_discovery=lambda o, s: ["x_" + o],
                                 route_review=lambda t: True, seeds_state=state)
    assert res["activated"]                                        # nu draaien ze
    assert all(h["ok"] for h in res["harvested"])
    # alle geactiveerde discovery-projecten zijn geoogst en done
    assert all(led.get(h["pid"])["status"] == "done" for h in res["harvested"])
    # spaced repetition: de gedraaide seed kreeg een tijdstempel
    assert "hennep" in state


def test_pulse_zonder_seeds_vraagt_harry():
    led, pin, lib = _stores()                                     # geen seeds in de bibliotheek
    led.start(db.ensure_root(led))
    res = db.run_discovery_pulse(led, pin, lib, ["trends"],
                                 wip={"board": 9, "roles": {}},
                                 do_discovery=lambda o, s: [], route_review=lambda t: True)
    assert res["requested_seeds"] is True
    reqs = [b for b in pin.all() if b["kind"] == "request" and b["tag"] == db.TAG["harry_hemp"]]
    assert reqs and "seed" in reqs[0]["title"].lower()
