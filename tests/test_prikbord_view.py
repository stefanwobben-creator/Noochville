"""Brok 3 — de cockpit-prikbordweergave (render_prikbord): WIP-meter, Kanban-kolommen,
cluster master-switch, stuwmeer (werk dat op de mens wacht) en de briefjes."""
from __future__ import annotations

from nooch_village.cockpit import render_prikbord


def _snap():
    root = {"id": "r", "owner": "the_source", "scope": "Sokken-idee", "status": "running",
            "cluster": "r", "parent": None, "links": []}
    m1 = {"id": "m1", "owner": "harry", "scope": "elastaan-alt", "status": "running",
          "cluster": "r", "parent": "r", "links": ["m2"], "dod_outcome": "Lijst materialen"}
    m2 = {"id": "m2", "owner": "scout", "scope": "leveranciers", "status": "blocked",
          "cluster": "r", "parent": "r", "links": ["m1"], "blocked_on": "mens: rol 'scout' onbemand"}
    fut = {"id": "f", "owner": "trends", "scope": "related kw", "status": "future",
           "cluster": "f", "parent": "r", "links": []}
    return {"projects": [root, m1, m2, fut], "wip": {"board": 3, "roles": {"harry": 2}},
            "pinboard": [{"id": "b1", "kind": "request", "tag": "supplier",
                          "title": "Zoek leverancier", "by": "harry", "status": "open",
                          "claimed_by": None, "created_at": 1},
                         {"id": "b2", "kind": "outcome", "tag": "seed", "title": "3 seeds",
                          "by": "harry", "status": "done", "claimed_by": "scout", "created_at": 2}],
            "generated_at": 1.0}


def test_prikbord_rendert_alle_panelen():
    h = render_prikbord(_snap(), csrf_token="tok")
    # WIP-meter: bord-breed + per rol
    assert "WIP" in h and "Bord-breed" in h
    # vier Kanban-kolommen
    for col in ("Toekomst", "Actief", "Wachten", "Done"):
        assert col in h
    # master-switch op de cluster-root (running → cluster aan), met aantal leden
    assert "master-switch" in h and "cluster aan" in h
    # stuwmeer toont het op-de-mens-wachtende werk
    assert "Stuwmeer" in h and "op jou" in h
    # briefjes: open verzoek zichtbaar, done-briefje weggefilterd
    assert "Zoek leverancier" in h and "3 seeds" not in h


def test_prikbord_geen_stuwmeer_groen():
    snap = _snap()
    snap["projects"] = [p for p in snap["projects"] if "mens" not in str(p.get("blocked_on"))]
    h = render_prikbord(snap, csrf_token="tok")
    assert "Geen stuwmeer" in h


def test_prikbord_read_only_zonder_token():
    # zonder csrf_token (read-only) geen statusknoppen-formulieren, wel het bord
    h = render_prikbord(_snap(), csrf_token=None)
    assert "Het bord" in h and 'action="/action"' not in h
