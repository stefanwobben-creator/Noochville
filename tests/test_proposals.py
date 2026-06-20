"""Round-trip test: proposal_to_dict ↔ proposal_from_dict behoudt elk veld."""
from __future__ import annotations
import time
import pytest
from nooch_village.governance import proposal_to_dict, proposal_from_dict
from nooch_village.models import Proposal, GovernanceChange, ChangeKind


def _full_proposal(**kwargs) -> Proposal:
    defaults = dict(
        proposer_role="website_watcher",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id="trends",
            purpose="nieuw doel",
            add_accountabilities=["wekelijkse rapportage"],
            remove_accountabilities=["oude taak"],
            add_domains=["data"],
            remove_domains=["archief"],
            add_skills=["gsc_performance"],
            remove_skills=["oude_skill"],
            new_role_parent="noochville",
            policy_id="pol_01",
            policy_text="geen reclame",
        ),
        tension="spanning over capaciteit",
        trigger_example="structureel terugkerende botsing",
        rationale="wekelijks patroon vereist structuurwijziging",
        id="abc123def456",
        status="escalated",
        created_at=1_700_000_000.0,
        escalation_gate="G2",
        escalation_reason="dubbele accountability",
        source="sensed",
    )
    defaults.update(kwargs)
    return Proposal(**defaults)


class TestRoundTrip:
    def test_alle_velden_bewaard(self):
        original = _full_proposal()
        d = proposal_to_dict(original)
        restored = proposal_from_dict(d)

        assert restored.id == original.id
        assert restored.proposer_role == original.proposer_role
        assert restored.tension == original.tension
        assert restored.trigger_example == original.trigger_example
        assert restored.rationale == original.rationale
        assert restored.status == original.status
        assert restored.created_at == original.created_at
        assert restored.escalation_gate == original.escalation_gate
        assert restored.escalation_reason == original.escalation_reason
        assert restored.source == original.source

    def test_change_velden_bewaard(self):
        original = _full_proposal()
        restored = proposal_from_dict(proposal_to_dict(original))
        c_orig = original.change
        c_rest = restored.change

        assert c_rest.kind == c_orig.kind
        assert c_rest.role_id == c_orig.role_id
        assert c_rest.purpose == c_orig.purpose
        assert c_rest.add_accountabilities == c_orig.add_accountabilities
        assert c_rest.remove_accountabilities == c_orig.remove_accountabilities
        assert c_rest.add_domains == c_orig.add_domains
        assert c_rest.remove_domains == c_orig.remove_domains
        assert c_rest.add_skills == c_orig.add_skills
        assert c_rest.remove_skills == c_orig.remove_skills
        assert c_rest.new_role_parent == c_orig.new_role_parent
        assert c_rest.policy_id == c_orig.policy_id
        assert c_rest.policy_text == c_orig.policy_text

    def test_add_role_round_trip(self):
        p = _full_proposal(
            change=GovernanceChange(
                kind=ChangeKind.ADD_ROLE,
                role_id="nieuwe_rol",
                purpose="waardevolle rol",
                new_role_parent="noochville",
            ),
        )
        restored = proposal_from_dict(proposal_to_dict(p))
        assert restored.change.kind == ChangeKind.ADD_ROLE
        assert restored.change.role_id == "nieuwe_rol"

    def test_lege_lijsten_bewaard(self):
        p = _full_proposal(
            change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="trends"),
        )
        restored = proposal_from_dict(proposal_to_dict(p))
        assert restored.change.add_accountabilities == []
        assert restored.change.add_domains == []
        assert restored.change.add_skills == []

    def test_none_velden_bewaard(self):
        p = _full_proposal(
            escalation_gate=None,
            escalation_reason=None,
        )
        restored = proposal_from_dict(proposal_to_dict(p))
        assert restored.escalation_gate is None
        assert restored.escalation_reason is None

    def test_source_default_sensed(self):
        p = _full_proposal()
        d = proposal_to_dict(p)
        del d["source"]
        restored = proposal_from_dict(d)
        assert restored.source == "sensed"
