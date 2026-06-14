"""Pin elke tak van Gate G0-G4."""
from __future__ import annotations
import pytest
from nooch_village.governance import Gate
from nooch_village.models import (
    Proposal, GovernanceChange, ChangeKind, Record, RoleDefinition, RecordType,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_proposal(**kwargs) -> Proposal:
    defaults = dict(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="analyst"),
        tension="test",
        trigger_example="terugkerend probleem",
        rationale="structureel patroon",
        source="sensed",
    )
    defaults.update(kwargs)
    return Proposal(**defaults)


def _role(rid, accs=None, domains=None, source="seed") -> Record:
    return Record(
        id=rid, type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(
            purpose=f"doel van {rid}",
            accountabilities=accs or [],
            domains=domains or [],
        ),
        source=source,
    )


gate = Gate()


# ── G0: structurele geldigheid ────────────────────────────────────────────────

class TestG0:
    def test_add_role_zonder_herhalingsbewijs_faalt(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.ADD_ROLE,
                role_id="nieuwe_rol",
                purpose="iets doen",
            ),
            trigger_example="één keer een probleem gezien",
            rationale="leek handig",
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G0"
        assert "herhalingsbewijs" in reason

    def test_add_role_met_herhalingsbewijs_passeert_g0(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.ADD_ROLE,
                role_id="nieuwe_rol",
                purpose="iets doen",
            ),
            trigger_example="terugkerend elke week",
            rationale="structureel patroon dat wekelijks opduikt",
        )
        passed, gate_name, _ = gate.check(p, records_with_root)
        assert passed or gate_name != "G0"

    def test_verplichte_velden_ontbreken(self, records_with_root):
        p = _make_proposal(tension="")  # tension leeg
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G0"
        assert "verplichte velden" in reason

    def test_amend_role_zonder_role_id_faalt(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(kind=ChangeKind.AMEND_ROLE),  # geen role_id
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G0"
        assert "role_id" in reason

    def test_add_role_zonder_purpose_faalt(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.ADD_ROLE,
                role_id="nieuwe_rol",
                # purpose ontbreekt
            ),
            trigger_example="structureel terugkerende taak",
            rationale="wekelijks patroon",
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G0"
        assert "purpose" in reason

    def test_add_policy_zonder_policy_id_faalt(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(kind=ChangeKind.ADD_POLICY, policy_text="geen reclame"),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G0"
        assert "policy_id" in reason


# ── G1: domein-botsing ────────────────────────────────────────────────────────

class TestG1:
    def test_nieuw_domein_overlapt_bestaand(self, records_with_root):
        records_with_root.put(_role("bibliotheek_rol", domains=["bibliotheek"]))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="andere_rol",
                add_domains=["bibliotheek"],
            ),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G1"
        assert "bibliotheek" in reason

    def test_g1_negeert_demo_records(self, records_with_root):
        records_with_root.put(_role("demo_rol", domains=["bibliotheek"], source="demo"))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="echte_rol",
                add_domains=["bibliotheek"],
            ),
        )
        passed, gate_name, _ = gate.check(p, records_with_root)
        assert passed or gate_name != "G1"

    def test_eigen_domein_amenden_geen_botsing(self, records_with_root):
        records_with_root.put(_role("mijn_rol", domains=["bibliotheek"]))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="mijn_rol",
                add_domains=["bibliotheek"],
            ),
        )
        passed, gate_name, _ = gate.check(p, records_with_root)
        assert passed or gate_name != "G1"


# ── G2: accountability-duplicaat ─────────────────────────────────────────────

class TestG2:
    def test_accountability_al_bij_andere_rol(self, records_with_root):
        records_with_root.put(_role("analist", accs=["dagelijkse groeipuls bewaken"]))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="nieuwe_rol",
                add_accountabilities=["dagelijkse groeipuls bewaken"],
            ),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G2"
        assert "analist" in reason

    def test_g2_negeert_demo_records(self, records_with_root):
        records_with_root.put(_role("demo_analist", accs=["groeipuls bewaken"], source="demo"))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="nieuwe_rol",
                add_accountabilities=["groeipuls bewaken"],
            ),
        )
        passed, gate_name, _ = gate.check(p, records_with_root)
        assert passed or gate_name != "G2"

    def test_eigen_accountability_geen_duplicaat(self, records_with_root):
        records_with_root.put(_role("mijn_rol", accs=["groeipuls bewaken"]))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="mijn_rol",
                add_accountabilities=["groeipuls bewaken"],
            ),
        )
        passed, gate_name, _ = gate.check(p, records_with_root)
        assert passed or gate_name != "G2"


# ── G3: verweesd werk ─────────────────────────────────────────────────────────

class TestG3:
    def test_remove_role_met_accountabilities_escaleert(self, records_with_root):
        records_with_root.put(_role("te_verwijderen", accs=["iets heel belangrijks doen"]))
        p = _make_proposal(
            change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id="te_verwijderen"),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G3"
        assert "te_verwijderen" in reason

    def test_remove_role_zonder_accountabilities_passeert_g3(self, records_with_root):
        records_with_root.put(_role("lege_rol", accs=[]))
        p = _make_proposal(
            change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id="lege_rol"),
        )
        passed, gate_name, _ = gate.check(p, records_with_root)
        assert passed or gate_name != "G3"

    def test_remove_accountability_nergens_belegd_faalt(self, records_with_root):
        records_with_root.put(_role("mijn_rol", accs=["unieke taak nergens anders"]))
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="mijn_rol",
                remove_accountabilities=["unieke taak nergens anders"],
            ),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G3"
        assert "unieke taak nergens anders" in reason


# ── G4: missie-poort ─────────────────────────────────────────────────────────

class TestG4:
    def test_hard_violation_plastic_goedkeuren(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                add_accountabilities=["plastic goedkeuren voor productie"],
            ),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G4"
        assert "missie-policy" in reason

    def test_hard_violation_google_ads_autoriseren(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                add_accountabilities=["google ads autoriseren voor campagnes"],
            ),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G4"

    def test_anchor_purpose_wijzigen_escaleert(self, records_with_root):
        root_id = records_with_root.root().id
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id=root_id,
                purpose="nieuw doel zonder missie",
            ),
        )
        passed, gate_name, reason = gate.check(p, records_with_root)
        assert not passed
        assert gate_name == "G4"
        assert "mens-eigendom" in reason or "founder" in reason

    def test_schone_amend_passeert_g4(self, records_with_root):
        p = _make_proposal(
            change=GovernanceChange(
                kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                add_accountabilities=["wekelijkse groei-rapportage schrijven"],
            ),
        )
        passed, gate_name, _ = gate.check(p, records_with_root, context=None)
        assert passed or gate_name not in ("G0", "G4")
