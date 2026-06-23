"""Tests voor het generieke grant_skill-voorstel (AMEND_ROLE add_skills) via de gate."""
from __future__ import annotations

from nooch_village.role_proposals import build_grant_skill_proposal
from nooch_village.governance import Gate, Records
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.models import ChangeKind


def _seeded(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_voorstel_is_amend_role_met_skill():
    p = build_grant_skill_proposal("librarian", "verband_voorstel")
    assert p.change.kind == ChangeKind.AMEND_ROLE
    assert p.change.role_id == "librarian"
    assert p.change.add_skills == ["verband_voorstel"]
    assert p.trigger_example


def test_voorstel_passeert_de_gate(tmp_path):
    p = build_grant_skill_proposal("librarian", "verband_voorstel")
    passed, gate, reason = Gate().check(p, _seeded(tmp_path))
    assert passed, f"verwacht aangenomen, maar {gate}: {reason}"
