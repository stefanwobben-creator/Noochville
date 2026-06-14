"""Tests voor classify_gap → inbox dispatch — thread-vrij.

Drie scenario's:
  B  gap classificeert als B → means-gap in de inbox (zoals voorheen).
  A  gap classificeert als A → geen inbox-item (operationeel gedekt, gelogd).
  C  gap classificeert als C → placeholder-suggestie in de inbox, geen geboorte.

De tests spiegelen de logica van Village._on_means_gap zonder Village te starten:
ze gebruiken dezelfde Records/HumanInbox als echte objecten en roepen de
dispatch-logica aan via een inline handler over de bus — identiek aan de echte
wiring, maar zonder threads.
"""
from __future__ import annotations
import pytest
from nooch_village.event_bus import EventBus, Event
from nooch_village.human_inbox import HumanInbox
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.gap_classifier import classify_gap


# ── Fixture: Records met controleerbare A/B/C-uitkomsten ─────────────────────

@pytest.fixture()
def records(tmp_path):
    recs = Records(str(tmp_path / "gov.json"))

    # analyst — mandaat + skills → A-rol voor site/health-gaten
    recs.put(Record(
        id="analyst", type=RecordType.ROLE, parent="noochville", source="seed",
        definition=RoleDefinition(
            purpose="Bewaakt de online gezondheid en groei van Nooch.earth",
            accountabilities=["site monitoren", "bezoekersdata duiden"],
            skills=["site_health", "plausible_stats"],
        ),
    ))

    # kennis_scout — mandaat (evidentie), geen dekkende skills voor boek → B-rol
    recs.put(Record(
        id="kennis_scout", type=RecordType.ROLE, parent="noochville", source="sensed",
        definition=RoleDefinition(
            purpose="Kandidaat-termen gronden in boeken en wetenschap",
            accountabilities=[
                "de gevonden evidentie distilleren tot een relevantie-duiding",
                "OpenLibrary voltekst-grounding evalueren en toevoegen als v2",
            ],
            skills=["openalex_evidence", "semscholar_tldr"],
        ),
    ))

    # noochville root — brede purpose (missie, transparantie, kernwaarden)
    recs.put(Record(
        id="noochville", type=RecordType.CIRCLE, parent=None, source="seed",
        definition=RoleDefinition(
            purpose=(
                "Nooch.earth is het duurzaamste schoenenmerk ter wereld. "
                "Kernwaarden: transparantie, missie-gedreven, eerlijke prijs."
            ),
        ),
    ))

    return recs


# ── Helper: spiegelt Village._on_means_gap-logica ────────────────────────────

def _make_dispatcher(inbox: HumanInbox, recs: Records):
    """Inline handler identiek aan Village._on_means_gap (zonder bus/threads)."""
    def dispatch(e: Event) -> str:
        gap_key     = e.data.get("gap_key", "?")
        description = e.data.get("description", "")
        outcome, role_id, reason = classify_gap(description, recs.all())
        if outcome == "A":
            pass   # geen inbox-item
        elif outcome == "B":
            inbox.add_means_gap(gap_key, description)
        elif outcome == "C":
            inbox.add_suggestion(gap_key, description)
        return outcome
    return dispatch


# ── B: mandaat ja, middelen nee → means-gap in inbox ─────────────────────────

def test_b_gap_lands_as_means_gap(tmp_path, records):
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    e = Event("means_gap_sensed", {
        "gap_key":     "boek_evidentie_ontbreekt",
        "description": "boek-evidentie ontbreekt voor kandidaat-termen",
        "by":          "kennis_scout",
    }, "kennis_scout")

    outcome = dispatch(e)

    assert outcome == "B"
    pending = inbox.pending()
    assert len(pending) == 1
    item = pending[0]
    assert item["type"]    == "means_gap"
    assert item["subject"] == "boek_evidentie_ontbreekt"
    assert item["status"]  == "pending"


def test_b_gap_deduped_on_second_dispatch(tmp_path, records):
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    e = Event("means_gap_sensed", {
        "gap_key":     "boek_evidentie_ontbreekt",
        "description": "boek-evidentie ontbreekt voor kandidaat-termen",
        "by":          "kennis_scout",
    }, "kennis_scout")

    dispatch(e)
    dispatch(e)   # tweede dispatch → dedup

    assert len(inbox.pending()) == 1


# ── A: mandaat + middelen aanwezig → geen inbox-item ─────────────────────────

def test_a_gap_produces_no_inbox_item(tmp_path, records):
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    e = Event("means_gap_sensed", {
        "gap_key":     "site_health_monitoring",
        "description": "site health monitoring ontbreekt",
        "by":          "analyst",
    }, "analyst")

    outcome = dispatch(e)

    assert outcome == "A"
    assert inbox.pending() == [], "A-gap mag geen inbox-item opleveren"


# ── C: geen mandaatdekking → suggestie in inbox, geen geboorte ───────────────

def test_c_gap_lands_as_suggestion(tmp_path, records):
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    e = Event("means_gap_sensed", {
        "gap_key":     "legal_compliance",
        "description": "legal compliance audit required",
        "by":          "kennis_scout",
    }, "kennis_scout")

    outcome = dispatch(e)

    assert outcome == "C"
    pending = inbox.pending()
    assert len(pending) == 1
    item = pending[0]
    assert item["type"]    == "suggestion"
    assert item["subject"] == "legal_compliance"
    assert "suggestie" in item["context"]["note"].lower()
    assert "geboorte"  in item["context"]["note"].lower()


def test_c_gap_deduped_on_second_dispatch(tmp_path, records):
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    e = Event("means_gap_sensed", {
        "gap_key":     "legal_compliance",
        "description": "legal compliance audit required",
        "by":          "kennis_scout",
    }, "kennis_scout")

    dispatch(e)
    dispatch(e)   # tweede dispatch → dedup

    assert len(inbox.pending()) == 1


def test_c_suggestion_no_role_birth(tmp_path, records):
    """Suggestie voegt geen record toe aan governance — geen autonome geboorte."""
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    ids_before = {r.id for r in records.all()}

    e = Event("means_gap_sensed", {
        "gap_key":     "legal_compliance",
        "description": "legal compliance audit required",
        "by":          "kennis_scout",
    }, "kennis_scout")
    dispatch(e)

    ids_after = {r.id for r in records.all()}
    assert ids_before == ids_after, "C-gap mag geen governance-record aanmaken"


# ── A/B/C zijn exclusief per gap_key ─────────────────────────────────────────

def test_abc_inbox_types_are_distinct(tmp_path, records):
    """A levert geen item, B levert means_gap, C levert suggestion — nooit gemengd."""
    inbox    = HumanInbox(str(tmp_path / "inbox.json"))
    dispatch = _make_dispatcher(inbox, records)

    dispatch(Event("means_gap_sensed", {
        "gap_key": "site_health_monitoring",
        "description": "site health monitoring ontbreekt",
        "by": "analyst",
    }, "analyst"))  # A → geen item

    dispatch(Event("means_gap_sensed", {
        "gap_key": "boek_evidentie",
        "description": "boek-evidentie ontbreekt voor kandidaat-termen",
        "by": "kennis_scout",
    }, "kennis_scout"))  # B → means_gap

    dispatch(Event("means_gap_sensed", {
        "gap_key": "legal_compliance",
        "description": "legal compliance audit required",
        "by": "kennis_scout",
    }, "kennis_scout"))  # C → suggestion

    pending = inbox.pending()
    assert len(pending) == 2
    types = {i["type"] for i in pending}
    assert types == {"means_gap", "suggestion"}
