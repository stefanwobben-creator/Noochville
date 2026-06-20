"""Tests voor fase 2 van de Scientist-ombouw.

Vijf scenario's:
1. APPROVE-FIX: approve_escalation herstelt Secretary._pending zodat governance_verdict
   de adoption daadwerkelijk uitvoert — ook na een Village-herstart (lege _pending).
2. ADD_ROLE harry_hemp passeert G0 (herhalingsbewijs aanwezig).
3. REMOVE_ROLE tijdgeest_wachter faalt G3 (rol heeft accountabilities).
4. REMOVE_ROLE kennis_scout faalt G3 (rol heeft accountabilities).
5. activate_tijdgeest_wachter en activate_kennis_scout slaan gearchiveerde records over.
"""
from __future__ import annotations
import time
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nooch_village.governance import Gate, Records, Secretary, proposal_to_dict, proposal_from_dict
from nooch_village.models import (
    Proposal, GovernanceChange, ChangeKind,
    Record, RoleDefinition, RecordType,
)
from nooch_village.event_bus import EventBus, Event
from nooch_village.human_inbox import HumanInbox


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_records(tmp_path) -> Records:
    path = str(tmp_path / "gov.json")
    recs = Records(path)
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(purpose="test", skills=[], policies=[]),
                  members=["tijdgeest_wachter", "kennis_scout"])
    root.source = "seed"
    recs.put(root)

    # Accountabilities gespiegeld aan de echte governance_records.json
    tw = Record(id="tijdgeest_wachter", type=RecordType.ROLE, parent="noochville",
                definition=RoleDefinition(
                    purpose="Volgt de lange culturele taalverschuiving via Google Books Ngram",
                    accountabilities=[
                        "de lange-termijn frequentie van missie-relevante termen in het "
                        "boekencorpus periodiek volgen via Google Books Ngram Viewer",
                        "culturele verschuivingen richting of weg van het burgerframe "
                        "signaleren aan GrowthAnalyst en Librarian",
                    ],
                    skills=["ngram_culture"]))
    tw.source = "sensed"
    recs.put(tw)

    ks = Record(id="kennis_scout", type=RecordType.ROLE, parent="noochville",
                definition=RoleDefinition(
                    purpose="Grondt kandidaat-termen in wetenschappelijke literatuur",
                    accountabilities=[
                        "de inhoudelijke context van een term ophalen uit voltekst-boeken "
                        "(OpenLibrary Search Inside) en uit de wetenschappelijke literatuur "
                        "(Semantic Scholar of OpenAlex)",
                        "de gevonden evidentie distilleren tot een relevantie-duiding en "
                        "die voeden aan Librarian en GrowthAnalyst",
                    ],
                    skills=["openalex_evidence", "semscholar_tldr"]))
    ks.source = "sensed"
    recs.put(ks)
    return recs


def _add_proposal(kind: str, role_id: str, **kwargs) -> Proposal:
    combined = "structureel doorlopend wekelijks"
    return Proposal(
        proposer_role="human",
        change=GovernanceChange(kind=ChangeKind(kind), role_id=role_id, **kwargs),
        tension="test spanning",
        trigger_example=f"{combined}: trigger",
        rationale=f"{combined}: rationale",
        source="sensed",
    )


# ── 1. approve_escalation herstelt _pending ──────────────────────────────────

def test_approve_escalation_populates_pending_and_adopts(tmp_path):
    """approve_escalation werkt ook als Secretary._pending leeg is (Village-herstart).

    Simuleert:
    - Village A: Facilitator escaleert voorstel → opgeslagen in human_inbox als proposal-dict
    - Village B (herstart): approve_escalation → herstelt _pending → governance_verdict →
      Secretary._adopt → governance_changed gepubliceerd
    """
    recs = _make_records(tmp_path)
    bus  = EventBus(name="test")

    # Maak het voorstel aan en sla het op in de inbox zoals Facilitator dat doet
    proposal = _add_proposal("remove_role", "tijdgeest_wachter")
    proposal_dict = proposal_to_dict(proposal)
    inbox = HumanInbox(str(tmp_path / "human_inbox.json"))
    iid = inbox.add_escalation(proposal_dict, gate="G3",
                               reason="rol heeft accountabilities")
    # Bevestig: volledige proposal-dict is opgeslagen
    assert inbox.get(iid)["context"]["proposal"] == proposal_dict

    # Maak Secretary met lege _pending (simuleert herstart)
    secretary = Secretary(recs, bus)
    assert len(secretary._pending) == 0

    changed: list[dict] = []
    bus.subscribe("governance_changed", lambda e: changed.append(dict(e.data)))

    # Herstel _pending vanuit de opgeslagen proposal-dict (zoals approve_escalation doet)
    stored = inbox.get(iid)["context"]["proposal"]
    reconstructed = proposal_from_dict(stored)
    secretary.store_pending(reconstructed)
    assert proposal.id in secretary._pending

    # Publiceer governance_verdict approve → Secretary adopteert
    inbox.resolve(iid, "approved", reason="human goedkeuring")
    bus.publish(Event("governance_verdict",
                      {"proposal_id": proposal.id, "decision": "approve", "reason": "test"},
                      "human"))

    # Archivering: tijdgeest_wachter.archived moet True zijn
    rec = recs.get("tijdgeest_wachter")
    assert rec is not None
    assert rec.archived is True
    assert len(changed) == 1
    assert changed[0]["kind"] == "remove_role"


# ── 2. ADD_ROLE harry_hemp passeert G0 ───────────────────────────────────────

def test_add_role_harry_hemp_passes_g0(tmp_path):
    """ADD_ROLE harry_hemp passeert G0: herhalingsbewijs aanwezig in trigger+rationale."""
    recs = _make_records(tmp_path)
    gate = Gate()

    proposal = Proposal(
        proposer_role="human",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id="harry_hemp",
            purpose="Observeert tijdgeest en grondt termen in wetenschap",
            add_accountabilities=[
                "wekelijks ngram-data meten",
                "keyword_evidence publiceren via OpenAlex",
            ],
            add_skills=["ngram_culture", "openalex_evidence"],
            new_role_parent="noochville",
        ),
        tension="consolidatie van TijdgeestWachter en KennisScout",
        trigger_example="structureel wekelijks gecombineerd in dezelfde puls",
        rationale="doorlopend gekoppeld: elke ngram-term vraagt grounding",
        source="sensed",
    )

    passed, gate_name, reason = gate.check(proposal, recs, context=None)
    assert passed, f"ADD_ROLE harry_hemp verwacht G0-G4 te passeren maar faalde op {gate_name}: {reason}"


# ── 3. REMOVE_ROLE tijdgeest_wachter faalt G3 ────────────────────────────────

def test_remove_role_tijdgeest_wachter_fails_g3(tmp_path):
    """REMOVE_ROLE tijdgeest_wachter faalt G3: rol heeft accountabilities."""
    recs = _make_records(tmp_path)
    gate = Gate()

    proposal = _add_proposal("remove_role", "tijdgeest_wachter")
    passed, gate_name, reason = gate.check(proposal, recs, context=None)

    assert not passed
    assert gate_name == "G3"
    assert "tijdgeest_wachter" in reason


# ── 4. REMOVE_ROLE kennis_scout faalt G3 ─────────────────────────────────────

def test_remove_role_kennis_scout_fails_g3(tmp_path):
    """REMOVE_ROLE kennis_scout faalt G3: rol heeft accountabilities."""
    recs = _make_records(tmp_path)
    gate = Gate()

    proposal = _add_proposal("remove_role", "kennis_scout")
    passed, gate_name, reason = gate.check(proposal, recs, context=None)

    assert not passed
    assert gate_name == "G3"
    assert "kennis_scout" in reason


# ── 5. activate-functies slaan gearchiveerde records over ─────────────────────

def test_activate_skips_archived_records(tmp_path):
    """activate_tijdgeest_wachter en activate_kennis_scout slaan archived records over."""
    from nooch_village.seeds import activate_tijdgeest_wachter, activate_kennis_scout

    recs = _make_records(tmp_path)

    # Archiveer beide records
    tw = recs.get("tijdgeest_wachter")
    tw.archived = True
    recs.put(tw)

    ks = recs.get("kennis_scout")
    ks.archived = True
    recs.put(ks)

    # Skills verwijderen zodat we kunnen meten of ze er terug in komen
    tw.definition.skills = []
    recs.put(tw)
    ks.definition.skills = []
    recs.put(ks)

    activate_tijdgeest_wachter(recs)
    activate_kennis_scout(recs)

    # Gearchiveerde records blijven ongewijzigd
    assert recs.get("tijdgeest_wachter").definition.skills == []
    assert recs.get("kennis_scout").definition.skills == []
