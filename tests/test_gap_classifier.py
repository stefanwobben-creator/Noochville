"""Tests voor gap_classifier.classify_gap — thread-vrij, geen I/O.

Fixture bouwt records via seed_records (echte definities) + minimale
sensed-rol-stubs die de sleuteleigenschappen uit de productiecode weerspiegelen.

Scenario's:
  B1  "boek-evidentie ontbreekt"          → B, kennis_scout
  A/B "missie-alignment bewaken"          → NIET C  (Noochie dekt het mandaat)
  REG de drie rommel-rol-beschrijvingen   → NIET C  (regressietest)
  C   "legal compliance checking"         → C
  B2  "pairs_sold meten"                  → B, analyst
"""
from __future__ import annotations
import pytest

from nooch_village.gap_classifier import classify_gap
from nooch_village.governance import Records
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.seeds import seed_records, migrate_records


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def records(tmp_path):
    """Records met echte seed-definities + sleutel sensed-rollen."""
    recs = Records(str(tmp_path / "governance_records.json"))
    seed_records(recs)
    migrate_records(recs)

    # analyst: voeg pairs_sold accountability toe (in productie via governance)
    analyst = recs.get("analyst")
    analyst.definition.accountabilities.append(
        "meting van pairs_sold (verkochte paren schoenen) bijhouden en rapporteren"
    )
    recs.put(analyst)

    # kennis_scout (sensed) — weerspiegelt de echte definitie uit roles.py
    recs.put(Record(
        id="kennis_scout", type=RecordType.ROLE, parent="noochville", source="sensed",
        definition=RoleDefinition(
            purpose=(
                "Kandidaat-termen gronden in boeken en wetenschap: duiden wat hun "
                "inhoudelijke en wetenschappelijke relevantie is."
            ),
            accountabilities=[
                "de gevonden evidentie distilleren tot een relevantie-duiding en "
                "die voeden aan Librarian en GrowthAnalyst",
                "OpenLibrary voltekst-grounding evalueren en toevoegen als v2",
                "de inhoudelijke context van een term ophalen uit voltekst-boeken "
                "en uit de wetenschappelijke literatuur",
            ],
            skills=["openalex_evidence", "semscholar_tldr"],
        ),
    ))

    # tijdgeest_wachter (sensed)
    recs.put(Record(
        id="tijdgeest_wachter", type=RecordType.ROLE, parent="noochville", source="sensed",
        definition=RoleDefinition(
            purpose="De lange culturele taalverschuiving volgen die voor de missie relevant is.",
            accountabilities=[
                "culturele verschuivingen richting of weg van het burgerframe signaleren",
                "aanvullende recente bron voor tijdgeest-observaties periodiek evalueren",
                "NL corpus dekking periodiek valideren",
            ],
            domains=["tijdgeest-observaties"],
            skills=["ngram_culture"],
        ),
    ))

    # noochie (sensed) — missie-stem; geen skills
    recs.put(Record(
        id="noochie", type=RecordType.ROLE, parent="noochville", source="sensed",
        definition=RoleDefinition(
            purpose=(
                "De missie belichamen en bepleiten in het dorp, en het geheel "
                "creatief richting de missie duwen."
            ),
            accountabilities=[
                "creatieve ideeën en voorstellen genereren die de missie vooruit helpen",
                "de missie levend houden: eraan herinneren en het werk van het dorp "
                "aan het waarom toetsen",
                "missie-alignment bewaken en bepleiten via governance, nooit zelf uitvoeren",
                "de stem van het merk zijn: veganistisch en duurzaam standpunt bewaken",
            ],
        ),
    ))

    return recs


def _all(recs: Records):
    return recs.all()


# ── B1: boek-evidentie → kennis_scout ────────────────────────────────────────

def test_boek_evidentie_ontbreekt(records):
    outcome, role_id, reason = classify_gap("boek-evidentie ontbreekt", _all(records))
    assert outcome == "B", f"verwacht B, kreeg {outcome!r} ({reason})"
    assert role_id == "kennis_scout", f"verwacht kennis_scout, kreeg {role_id!r} ({reason})"


# ── A/B: missie-alignment bewaken → NIET C ───────────────────────────────────

def test_missie_alignment_bewaken_niet_c(records):
    outcome, role_id, reason = classify_gap("missie-alignment bewaken", _all(records))
    assert outcome != "C", f"verwacht NIET C, kreeg C ({reason})"


# ── REG: rommel-rol-beschrijvingen → NIET C ──────────────────────────────────

@pytest.mark.parametrize("description", [
    "Beheert en bewaakt missie-alignment, missie-gedreven, transparantie, kernwaarden.",
    "Beheert en bewaakt veganistisch, missie-lens, niche-label, doorbreken.",
    "Beheert en bewaakt missie-alignment, marketingtruc, veganistisch, onderscheid.",
])
def test_rommel_rol_niet_c(records, description):
    """Regressietest: deze beschrijvingen vallen binnen bestaand mandaat — nooit C."""
    outcome, role_id, reason = classify_gap(description, _all(records))
    assert outcome != "C", (
        f"beschrijving '{description[:50]}…' gaf C ({reason}); "
        f"classifier had de role-creatie moeten blokkeren"
    )


# ── C: echt nieuw gat → C ────────────────────────────────────────────────────

def test_legal_compliance_checking_is_c(records):
    outcome, role_id, reason = classify_gap("legal compliance checking", _all(records))
    assert outcome == "C", f"verwacht C, kreeg {outcome!r} ({reason})"


# ── B2: pairs_sold meten → analyst ───────────────────────────────────────────

def test_pairs_sold_meten(records):
    outcome, role_id, reason = classify_gap("pairs_sold meten", _all(records))
    assert outcome == "B", f"verwacht B, kreeg {outcome!r} ({reason})"
    assert role_id == "analyst", f"verwacht analyst, kreeg {role_id!r} ({reason})"


# ── Gearchiveerde records worden overgeslagen ─────────────────────────────────

def test_archived_records_skipped(records):
    """Een gearchiveerde rol telt niet mee, ook niet als zijn definitie perfect matcht."""
    # Archiveer kennis_scout
    rec = records.get("kennis_scout")
    rec.archived = True
    records.put(rec)

    outcome, role_id, reason = classify_gap("boek-evidentie ontbreekt", _all(records))
    assert role_id != "kennis_scout", "gearchiveerde rol mag niet als winnaar verschijnen"


# ── Lege beschrijving ─────────────────────────────────────────────────────────

def test_empty_description_is_c(records):
    outcome, _, _ = classify_gap("", _all(records))
    assert outcome == "C"
