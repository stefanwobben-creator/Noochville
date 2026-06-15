"""Tests voor _funnel_c_proposal — de drie filters van de C-trechter.

Filter 1  Kandidaat-dedup (deterministisch): gap_key matcht bestaand record → drop.
Filter 2  Recurrence-passage (no-op): twee-slag-gate stroomopwaarts reeds doorlopen.
Filter 3  Coherentiepoort via LLM: fail-closed; alleen "coherent" → True.
"""
from __future__ import annotations
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.seeds import seed_records
from nooch_village.skills import SkillRegistry
from nooch_village.inhabitant import Inhabitant


class _FakeContext:
    def __init__(self, records, data_dir, settings=None):
        self.records = records
        self.data_dir = str(data_dir)
        self.settings = settings or {}


def _base_records(tmp_path):
    """Minimale records: seed + noochie zonder missie-skills zodat
    'legal compliance audit required' als classify_gap C uitkomt."""
    recs = Records(str(tmp_path / "gov.json"))
    seed_records(recs)
    recs.put(Record(
        id="noochie", type=RecordType.ROLE, parent="noochville", source="sensed",
        definition=RoleDefinition(
            purpose=(
                "De missie belichamen en bepleiten in het dorp. "
                "Kernwaarden: veganistisch, transparantie, missie-gedreven."
            ),
            accountabilities=[
                "missie-alignment bewaken en bepleiten via governance",
                "de stem van het merk zijn: veganistisch en duurzaam standpunt bewaken",
                "kernwaarden bewaken: transparantie, missie-gedreven, niche-label",
            ],
            skills=["missie_alignment_check", "veganistisch_standpunt"],
        ),
    ))
    return recs


def _make_inhabitant(recs, bus, data_dir):
    rec = recs.get("noochie")
    return Inhabitant(rec, bus, SkillRegistry(), _FakeContext(recs, data_dir))


# ── Unit-test 1: dedup dropt op bestaand gap_key ────────────────────────────

def test_c_funnel_dedup_drops_existing_gap_key(tmp_path):
    """Filter 1: gap_key matcht een niet-gearchiveerd record → _funnel_c_proposal False.
    LLM wordt niet bereikt (dedup blokkeert eerder)."""
    recs = _base_records(tmp_path)
    recs.put(Record(
        id="compliance_required_audit", type=RecordType.ROLE,
        parent="noochville", source="sensed",
        definition=RoleDefinition(purpose="bestaande compliance-rol"),
    ))
    bus = EventBus(name="test")
    inh = _make_inhabitant(recs, bus, tmp_path / "data")

    result = inh._funnel_c_proposal(
        "legal compliance audit required",
        "compliance_required_audit",
        recs.all(),
    )
    assert result is False


# ── Unit-test 2: nieuw gap_key passeert dedup, coherentiepoort laat door ─────

def test_c_funnel_passes_new_gap_key(tmp_path):
    """Geen record met gap_key → dedup slaat over; met coherent LLM-verdict → True.

    Keuze: llm.reason wordt gemockt op "coherent" zodat de test key-onafhankelijk
    is. Zonder mock zou de poort fail-closed (None) zijn bij ontbrekende API-key,
    wat de dedup-passage-logica verbergt. De mock isoleert filter 1 en 3 samen.
    """
    recs = _base_records(tmp_path)
    bus = EventBus(name="test")
    inh = _make_inhabitant(recs, bus, tmp_path / "data")

    with patch("nooch_village.llm.reason",
               return_value="VERDICT: coherent\nREASON: heldere distincte rol"):
        result = inh._funnel_c_proposal(
            "legal compliance audit required",
            "compliance_required_audit",
            recs.all(),
        )
    assert result is True


# ── Integratietest 3: dedup blokkeert proposal_raised ────────────────────────

def test_c_proposal_dedup_blocks_publish(tmp_path):
    """Volledig pad: 2×_sense_gap → classify_gap C → _funnel_c_proposal dedup → geen publish.

    r_id voor 'legal compliance audit required' = 'compliance_required_audit'.
    Dat record bestaat al → trechter dropt het voorstel vóór bus.publish.
    Tegenstelling: test_uncovered_gap_reaches_add_role_via_two_strike_gate (geen dedup)
    bewijst dat zonder het record wél gepubliceerd wordt.
    """
    recs = _base_records(tmp_path)
    recs.put(Record(
        id="compliance_required_audit", type=RecordType.ROLE,
        parent="noochville", source="sensed",
        definition=RoleDefinition(purpose="bestaande compliance-rol"),
    ))
    bus = EventBus(name="test")
    proposals = []
    bus.subscribe("proposal_raised", lambda e: proposals.append(e))

    inh = _make_inhabitant(recs, bus, tmp_path / "data")
    with patch.object(inh, "_classify_llm", return_value="structural"):
        inh._sense_gap("legal_compliance_gat", "legal compliance audit required",
                       kind="governance", min_count=2)
        inh._sense_gap("legal_compliance_gat", "legal compliance audit required",
                       kind="governance", min_count=2)

    add_role = [p for p in proposals
                if p.data.get("proposal", {}).get("change", {}).get("kind") == "add_role"]
    assert add_role == [], (
        "C-trechter dedup moet ADD_ROLE blokkeren als 'compliance_required_audit' "
        "al als record bestaat"
    )


# ── Coherentiepoort unit-tests ─────────────────────────────────────────────────

def test_coherence_gate_passes_coherent_verdict(tmp_path):
    """Filter 3: LLM geeft 'coherent' → _funnel_c_proposal True."""
    recs = _base_records(tmp_path)
    bus = EventBus(name="test")
    inh = _make_inhabitant(recs, bus, tmp_path / "data")

    with patch("nooch_village.llm.reason",
               return_value="VERDICT: coherent\nREASON: dit is een heldere rol"):
        result = inh._funnel_c_proposal(
            "juridische claims controleren en afhandelen",
            "juridische_claims_afhandelen",
            recs.all(),
        )
    assert result is True


def test_coherence_gate_blocks_vague_verdict(tmp_path):
    """Filter 3: LLM geeft 'vague' → _funnel_c_proposal False; drop is gelogd."""
    recs = _base_records(tmp_path)
    bus = EventBus(name="test")
    inh = _make_inhabitant(recs, bus, tmp_path / "data")

    with patch("nooch_village.llm.reason",
               return_value="VERDICT: vague\nREASON: keyword-cluster zonder mandaat"):
        with patch.object(inh.log, "warning") as mock_warn:
            result = inh._funnel_c_proposal(
                "missie-alignment, transparantie, kernwaarden",
                "missie_transparantie_kernwaarden",
                recs.all(),
            )

    assert result is False
    logged = " ".join(str(c) for c in mock_warn.call_args_list)
    assert "vague" in logged


def test_coherence_gate_fails_closed_on_exception(tmp_path):
    """Filter 3: llm.reason gooit een exception → fail-closed False; fout is gelogd."""
    recs = _base_records(tmp_path)
    bus = EventBus(name="test")
    inh = _make_inhabitant(recs, bus, tmp_path / "data")

    with patch("nooch_village.llm.reason", side_effect=RuntimeError("verbinding verbroken")):
        with patch.object(inh.log, "warning") as mock_warn:
            result = inh._funnel_c_proposal(
                "juridische claims controleren",
                "juridische_claims_controleren",
                recs.all(),
            )

    assert result is False
    logged = " ".join(str(c) for c in mock_warn.call_args_list)
    assert "fail-closed" in logged
