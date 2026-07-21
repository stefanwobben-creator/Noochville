"""Twee nieuwe skills (founder 20 jul): ruis_check (te brede zoekopdracht = ongeldige meting,
niet een bevinding) en escaleer (een rol routeert bewust naar de juiste rol of de Founding
Farmer). Beide deterministisch, met een Kroniek-brug."""
from __future__ import annotations

import json
import types

from nooch_village.evidence_ledger import classify_result
from nooch_village.notifications import NotifStore
from nooch_village.skills_impl.escaleer import EscaleerSkill
from nooch_village.skills_impl.ruis_check import RuisCheckSkill


def test_ruis_check_drempel_en_kroniek():
    sk = RuisCheckSkill()
    ctx = types.SimpleNamespace(settings={})
    breed = sk.run({"query": "shoes", "aantal": 3079427}, ctx)
    assert breed["status"] == "te_breed" and "te breed" in breed["oordeel"]
    assert sk.evidence_records(breed, role_id="harry_hemp")[0]["status"] == "fout"
    ok = sk.run({"query": "PHA barefoot outsole", "aantal": 42}, ctx)
    assert ok["status"] == "bruikbaar"
    assert sk.evidence_records(ok, role_id="harry_hemp")[0]["status"] == "bevestigd"
    # override-drempel + fail-net bij ontbrekende/ongeldige input
    assert sk.run({"query": "x", "aantal": 100, "drempel": 50}, ctx)["status"] == "te_breed"
    assert "error" in sk.run({"query": "x"}, ctx)
    assert "error" in sk.run({"query": "x", "aantal": "veel"}, ctx)
    assert RuisCheckSkill.required_payload == ("query", "aantal")


def test_escaleer_landt_als_notificatie(tmp_path):
    ctx = types.SimpleNamespace(data_dir=str(tmp_path))
    sk = EscaleerSkill()
    # 'founder' → the_source
    r = sk.run({"reden": "twijfel over de barefoot-claim", "naar": "founder", "van": "Lara"}, ctx)
    assert r["ok"] and r["naar"] == "the_source"
    notif = NotifStore(f"{tmp_path}/notifications.json")
    got = notif.for_targets([("role", "the_source")])
    assert got and "twijfel over de barefoot-claim" in got[0]["snippet"]
    assert sk.evidence_records(r, role_id="librarian")[0]["status"] == "bevestigd"
    # naar een concrete rol
    r2 = sk.run({"reden": "dit is compliance-werk", "naar": "compliance"}, ctx)
    assert r2["naar"] == "compliance"
    assert NotifStore(f"{tmp_path}/notifications.json").for_targets([("role", "compliance")])
    # fail-net
    assert "error" in sk.run({"reden": "x"}, ctx)


def test_beide_in_registry():
    from nooch_village.registry_factory import build_skill_registry
    reg = build_skill_registry()
    assert reg.get("ruis_check") is not None
    assert reg.get("escaleer") is not None
