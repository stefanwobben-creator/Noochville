"""Tests voor het Compliance-rol-voorstel (via governance). Thread-vrij.

De rol wordt niet geseed maar geboren via een ADD_ROLE-voorstel dat de G0-G4-poort moet passeren,
en krijgt daarna claim_evidence via amend_role. Deze tests bewijzen dat beide voorstellen goed
gevormd zijn, de poort halen, en dat de rol bewust GEEN code-klasse heeft (generieke Inhabitant)."""
from __future__ import annotations

from nooch_village.role_proposals import (
    build_compliance_proposal, build_compliance_skills_proposal)
from nooch_village.governance import Gate, Records
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.models import ChangeKind

_REPETITION = ("meermaals", "terugkerend", "structureel", "wekelijks", "elke week")


def _seeded_records(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_voorstel_is_add_role_compliance():
    p = build_compliance_proposal()
    assert p.change.kind == ChangeKind.ADD_ROLE
    assert p.change.role_id == "compliance"
    assert p.change.purpose
    assert p.change.add_domains == ["claim-keuring"]
    assert p.change.add_accountabilities
    # default-ouder = de live operationele cirkel (naast concurrent_scout/harry_hemp)
    assert p.change.new_role_parent == "mother_earth__nooch__noochville"


def test_ouder_is_overschrijfbaar():
    p = build_compliance_proposal(parent="een_andere_cirkel")
    assert p.change.new_role_parent == "een_andere_cirkel"


def test_voorstel_heeft_herhalingsbewijs_in_trigger():
    p = build_compliance_proposal()
    assert any(w in p.trigger_example.lower() for w in _REPETITION)


def test_voorstel_passeert_de_gate(tmp_path):
    p = build_compliance_proposal()
    passed, gate, reason = Gate().check(p, _seeded_records(tmp_path))
    assert passed, f"verwacht aangenomen, maar {gate} blokkeerde: {reason}"


def test_compliance_wordt_niet_geseed(tmp_path):
    assert _seeded_records(tmp_path).get("compliance") is None


# ── activatie: skill via amend_role, GEEN code-klasse ─────────────────────────

def test_skills_voorstel_is_amend_role_claim_evidence():
    p = build_compliance_skills_proposal()
    assert p.change.kind == ChangeKind.AMEND_ROLE
    assert p.change.role_id == "compliance"
    assert p.change.add_skills == ["claim_evidence"]


def test_skills_voorstel_passeert_de_gate(tmp_path):
    p = build_compliance_skills_proposal()
    passed, gate, reason = Gate().check(p, _seeded_records(tmp_path))
    assert passed, f"verwacht aangenomen, maar {gate} blokkeerde: {reason}"


def test_compliance_niet_in_class_map():
    """Bewust generiek: de rol heeft geen eigen Inhabitant-subklasse; een geregistreerde skill
    volstaat voor materialisatie."""
    from nooch_village.village import CLASS_MAP
    assert "compliance" not in CLASS_MAP


def test_claim_evidence_skill_is_geregistreerd():
    """De skill die de rol levend maakt moet echt in de registry staan (anders blijft hij onbemand)."""
    from nooch_village.registry_factory import build_skill_registry
    assert build_skill_registry().get("claim_evidence") is not None
