"""Tests voor het REMOVE_ROLE-voorstel via governance. Thread-vrij."""
from __future__ import annotations

from nooch_village.role_proposals import build_remove_role_proposal
from nooch_village.governance import Gate, Records
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.models import ChangeKind, Record, RoleDefinition, RecordType


def _seeded(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_voorstel_is_remove_role():
    p = build_remove_role_proposal("rommel_rol")
    assert p.change.kind == ChangeKind.REMOVE_ROLE
    assert p.change.role_id == "rommel_rol"
    assert p.trigger_example


def test_lege_rol_passeert_de_gate(tmp_path):
    """Een rol zonder accountabilities wordt zonder menselijke tussenkomst gearchiveerd."""
    records = _seeded(tmp_path)
    records.put(Record(
        id="cruft", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="rommel", skills=[], accountabilities=[]),
        source="sensed",
    ))
    p = build_remove_role_proposal("cruft")
    passed, gate, reason = Gate().check(p, records)
    assert passed, f"verwacht aangenomen, maar {gate}: {reason}"


def test_rol_met_accountabilities_escaleert_via_g3(tmp_path):
    """Een rol mét accountabilities mag niet stil verdwijnen: G3 escaleert naar de mens."""
    records = _seeded(tmp_path)
    records.put(Record(
        id="met_werk", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="doet iets",
                                  accountabilities=["belangrijk werk dat ergens heen moet"]),
        source="sensed",
    ))
    p = build_remove_role_proposal("met_werk")
    passed, gate, reason = Gate().check(p, records)
    assert not passed
    assert gate == "G3"
