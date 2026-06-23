"""Test dat Harry's role-upgrade-voorstel door de gate komt. Thread-vrij."""
from __future__ import annotations

from nooch_village.role_proposals import build_harry_role_upgrade_proposal
from nooch_village.governance import Gate, Records
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.models import ChangeKind


def _seeded(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_voorstel_is_amend_role_harry():
    p = build_harry_role_upgrade_proposal()
    assert p.change.kind == ChangeKind.AMEND_ROLE
    assert p.change.role_id == "harry_hemp"
    assert p.change.purpose
    assert len(p.change.add_accountabilities) == 2


def test_voorstel_passeert_de_gate(tmp_path):
    p = build_harry_role_upgrade_proposal()
    passed, gate, reason = Gate().check(p, _seeded(tmp_path))
    assert passed, f"verwacht aangenomen, maar {gate}: {reason}"
