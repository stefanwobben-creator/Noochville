"""Test dat het amend_role-voorstel voor serpapi_trends door de gate komt. Thread-vrij."""
from __future__ import annotations

from nooch_village.role_proposals import build_website_watcher_serpapi_proposal
from nooch_village.governance import Gate, Records
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.models import ChangeKind


def _seeded(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)
    return r


def test_voorstel_is_amend_role_met_serpapi():
    p = build_website_watcher_serpapi_proposal()
    assert p.change.kind == ChangeKind.AMEND_ROLE
    assert p.change.role_id == "website_watcher"
    assert p.change.add_skills == ["serpapi_trends"]


def test_voorstel_passeert_de_gate(tmp_path):
    p = build_website_watcher_serpapi_proposal()
    passed, gate, reason = Gate().check(p, _seeded(tmp_path))
    assert passed, f"verwacht aangenomen, maar {gate} blokkeerde: {reason}"
