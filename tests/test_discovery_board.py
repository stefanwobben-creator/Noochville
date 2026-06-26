"""Brok 4 — discovery-rollen bedraad op het bord (b → a via 'stollen'):
één staand experiment per rol, telt elke puls +1, hangt uitkomst-briefje op + routeert review,
spaced repetition, 'door de seeds heen → verzoek aan Harry', en na 3× automatisch een
rol-specifieke accountability op de roloverleg-agenda."""
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
            Library(os.path.join(d, "lib.json")), d)


def _seed(lib, *words):
    for w in words:
        lib.curate(w, "approved", by="test")
        lib.set_function(w, "volg")


def test_ensure_root_idempotent():
    led, _, _, _ = _stores()
    a = db.ensure_root(led)
    b = db.ensure_root(led)
    assert a == b == db.DISCOVERY_ROOT
    assert led.get(db.DISCOVERY_ROOT)["status"] == "future"     # master-switch standaard uit
    assert sum(1 for p in led.all() if p["id"] == db.DISCOVERY_ROOT) == 1


def test_ensure_experiment_een_per_rol():
    led, _, _, _ = _stores()
    pid = db.ensure_experiment(led, "trends")
    p = led.get(pid)
    assert p["origin"] == "experiment" and p["parent"] == db.DISCOVERY_ROOT
    assert p["status"] == "future" and p["scope"] == db.STANDING_SCOPE["trends"]
    assert db.ensure_experiment(led, "trends") == pid          # dedup: één per rol


def test_spaced_seed_kiest_oudste():
    assert db.spaced_seed([], {}) is None
    assert db.spaced_seed(["a", "b"], {}) in ("a", "b")            # ongezien
    assert db.spaced_seed(["a", "b"], {"a": 100.0, "b": 5.0}) == "b"  # b langst geleden


def test_run_role_telt_op_briefje_en_review_dedup():
    led, pin, lib, _ = _stores()
    lib.curate("bekend", "approved", by="test")                   # al bekend → niet routeren
    pid = db.ensure_experiment(led, "harry_hemp")
    routed = []
    h = db.run_role(led, pin, "harry_hemp", pid, ["hennepschoen", "bekend", "  "],
                    route_review=lambda t: routed.append(t) or True, library=lib)
    assert h["fresh"] == ["hennepschoen"] and routed == ["hennepschoen"]
    # NIET afgerond: staand werk; teller op 1
    assert led.get(pid)["status"] != "done" and h["executions"] == 1
    out = [b for b in pin.all() if b["kind"] == "outcome"]
    assert out and out[0]["tag"] == db.TAG["harry_hemp"] and pid in out[0]["links"]


def test_pulse_master_switch_gate():
    led, pin, lib, _ = _stores()
    _seed(lib, "hennep")
    # root nog future → alleen klaarzetten, niets uitvoeren
    res0 = db.run_discovery_pulse(led, pin, lib, ["harry_hemp", "trends", "concurrent_scout"],
                                  do_discovery=lambda o, s: ["x_" + o], route_review=lambda t: True)
    assert res0["ensured"] and res0["ran"] == []
    assert all(led.get(p)["executions"] == 0 for p in res0["ensured"])
    # mens zet de master-switch aan → nu draaien ze
    led.start(db.ensure_root(led))
    state = {}
    res = db.run_discovery_pulse(led, pin, lib, ["harry_hemp", "trends", "concurrent_scout"],
                                 do_discovery=lambda o, s: ["x_" + o],
                                 route_review=lambda t: True, seeds_state=state)
    assert len(res["ran"]) == 3 and all(h["ok"] for h in res["ran"])
    assert "hennep" in state                                       # spaced repetition gedraaid


def test_pulse_zonder_seeds_vraagt_harry():
    led, pin, lib, _ = _stores()                                  # geen seeds in de bibliotheek
    led.start(db.ensure_root(led))
    res = db.run_discovery_pulse(led, pin, lib, ["trends"],
                                 do_discovery=lambda o, s: [], route_review=lambda t: True)
    assert res["requested_seeds"] is True
    reqs = [b for b in pin.all() if b["kind"] == "request" and b["tag"] == db.TAG["harry_hemp"]]
    assert reqs and "seed" in reqs[0]["title"].lower()


def test_stolt_na_3x_tot_rol_specifieke_accountability():
    """De b → a kern: na 3 pulsen draagt het staande experiment van een rol zich automatisch
    voor als rol-specifieke accountability op de roloverleg-agenda (optie 1)."""
    from nooch_village.roloverleg import Agenda, formalize_ripe_experiments
    led, pin, lib, d = _stores()
    _seed(lib, "hennep")
    led.start(db.ensure_root(led))
    state = {}
    for _ in range(3):
        db.run_discovery_pulse(led, pin, lib, ["trends"],
                               do_discovery=lambda o, s: ["term"], route_review=lambda t: True,
                               seeds_state=state)
    pid = db.ensure_experiment(led, "trends")
    assert led.get(pid)["executions"] == 3
    agenda = Agenda(os.path.join(d, "agenda.json"))
    n = formalize_ripe_experiments(led, agenda)
    assert n == 1
    items = agenda.open()
    assert items and items[0]["role_id"] == "trends"
    assert items[0]["change"]["add_accountabilities"][0] == db.STANDING_SCOPE["trends"]
    # dedup: tweede keer formaliseren doet niets
    assert formalize_ripe_experiments(led, agenda) == 0
