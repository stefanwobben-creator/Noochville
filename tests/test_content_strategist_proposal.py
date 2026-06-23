"""Tests voor het Content Strategist-voorstel (via governance). Thread-vrij.

De rol wordt niet geseed maar geboren via een ADD_ROLE-voorstel dat de G0-G4-poort
moet passeren. Deze tests bewijzen dat het voorstel goed gevormd is en de poort haalt.
"""
from __future__ import annotations

from nooch_village.role_proposals import (
    build_content_strategist_proposal, build_content_strategist_skills_proposal,
)
from nooch_village.governance import Gate, Records
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.models import ChangeKind

_REPETITION = ("meermaals", "terugkerend", "structureel", "wekelijks", "elke week")


def _seeded_records(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_voorstel_is_add_role_content_strategist():
    p = build_content_strategist_proposal()
    assert p.change.kind == ChangeKind.ADD_ROLE
    assert p.change.role_id == "content_strategist"
    assert p.change.purpose
    assert p.change.add_accountabilities
    assert p.change.add_domains == ["publieke content"]


def test_voorstel_heeft_herhalingsbewijs_voor_g0():
    p = build_content_strategist_proposal()
    combined = (p.trigger_example + " " + p.rationale).lower()
    assert any(w in combined for w in _REPETITION)


def test_voorstel_passeert_de_gate(tmp_path):
    p = build_content_strategist_proposal()
    records = _seeded_records(tmp_path)
    passed, gate, reason = Gate().check(p, records)
    assert passed, f"verwacht aangenomen, maar {gate} blokkeerde: {reason}"


def test_content_strategist_wordt_niet_geseed(tmp_path):
    """De rol mag NIET via seed bestaan: hij hoort via governance geboren te worden."""
    records = _seeded_records(tmp_path)
    assert records.get("content_strategist") is None


# ── 13e: activatie (skills via amend_role + CLASS_MAP) ────────────────────────

def test_skills_voorstel_is_amend_role():
    p = build_content_strategist_skills_proposal()
    assert p.change.kind == ChangeKind.AMEND_ROLE
    assert p.change.role_id == "content_strategist"
    assert set(p.change.add_skills) == {"content_schrijven", "content_check"}


def test_skills_voorstel_passeert_de_gate(tmp_path):
    p = build_content_strategist_skills_proposal()
    records = _seeded_records(tmp_path)
    passed, gate, reason = Gate().check(p, records)
    assert passed, f"verwacht aangenomen, maar {gate} blokkeerde: {reason}"


def test_content_strategist_in_class_map():
    from nooch_village.village import CLASS_MAP
    from nooch_village.roles import ContentStrategist
    assert CLASS_MAP.get("content_strategist") is ContentStrategist
