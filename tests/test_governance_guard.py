"""Herkomst-wachter (B): records mogen alleen bootstrap-rollen seeden; elke andere rol hoort
via governance geboren te zijn (source=sensed). seed/migratie mogen geen seed-gehardcodeerde
niet-bootstrap rol opleveren."""
from __future__ import annotations

from nooch_village.governance import Records
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.seeds import (
    seed_records, migrate_records, role_provenance_violations, BOOTSTRAP_ROLES)


def test_seed_en_migrate_leveren_geen_seed_gehardcodeerde_rol(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    assert role_provenance_violations(r) == []      # alleen bootstrap-rollen geseed


def test_wachter_detecteert_seed_gehardcodeerde_niet_bootstrap_rol(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    smokkel = Record(id="smokkelrol", type=RecordType.ROLE, parent="noochville",
                     definition=RoleDefinition(purpose="stiekem geseed"))
    smokkel.source = "seed"
    r.put(smokkel)
    assert "smokkelrol" in role_provenance_violations(r)


def test_via_governance_geboren_rol_is_schoon(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    geboren = Record(id="echte_rol", type=RecordType.ROLE, parent="noochville",
                     definition=RoleDefinition(purpose="via de gate geboren"))
    geboren.source = "sensed"
    r.put(geboren)
    assert "echte_rol" not in role_provenance_violations(r)


def test_concurrent_scout_is_geen_bootstrap():
    assert "concurrent_scout" not in BOOTSTRAP_ROLES
