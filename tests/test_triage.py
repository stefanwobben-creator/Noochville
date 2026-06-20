"""Tests voor TriageEngine — zonder threads, bus of I/O."""
from __future__ import annotations
import pytest
from nooch_village.triage_engine import TriageEngine, TriageContext, TriageResult


@pytest.fixture
def engine():
    return TriageEngine()


def _ctx(role_id="website_watcher", purpose="bewaakt de groei van nooch.earth",
         accountabilities=None, domains=None, records=None) -> TriageContext:
    return TriageContext(
        role_id=role_id,
        purpose=purpose,
        accountabilities=accountabilities or ["bezoekersdata duiden", "field note schrijven"],
        domains=domains or [],
        records=records,
    )


# ── Structurele keywords ──────────────────────────────────────────────────────

class TestStructureel:
    def test_niemand_bezit(self, engine):
        r = engine.classify("niemand bezit de materiaal-policy", _ctx())
        assert r.classification == "structureel"

    def test_accountability_kw(self, engine):
        r = engine.classify("accountability voor taalcontrole ontbreekt", _ctx())
        assert r.classification == "structureel"

    def test_structureel_kw(self, engine):
        r = engine.classify("structureel terugkerende klacht over onboarding", _ctx())
        assert r.classification == "structureel"

    def test_policy_kw(self, engine):
        r = engine.classify("er is geen policy voor externe partners", _ctx())
        assert r.classification == "structureel"

    def test_llm_override_structural(self, engine):
        # LLM zegt "structural" → altijd structureel, ook al is er geen keyword
        r = engine.classify("gewoon een opmerking", _ctx(), llm_result="structural")
        assert r.classification == "structureel"

    def test_no_target_for_structureel(self, engine):
        r = engine.classify("niemand bezit het bijwerken van de locale-policy", _ctx())
        assert r.target_role_id is None
        assert r.target_capability is None


# ── Eigen werk ────────────────────────────────────────────────────────────────

class TestEigenWerk:
    def test_own_word_in_description(self, engine):
        # "bezoekersdata" is langer dan 6 tekens en staat in accountabilities
        r = engine.classify("bezoekersdata van afgelopen week analyseren", _ctx())
        assert r.classification == "eigen-werk"

    def test_own_word_from_purpose(self, engine):
        # "bewaakt" staat in de purpose
        r = engine.classify("de groei bewaakt worden via de juiste dashboards", _ctx())
        assert r.classification == "eigen-werk"

    def test_llm_own_override(self, engine):
        r = engine.classify("vreemde tekst die normaal niet matcht", _ctx(), llm_result="own")
        assert r.classification == "eigen-werk"


# ── Andere rol ────────────────────────────────────────────────────────────────

class SimpleRecords:
    """Minimale stub voor TriageContext.records."""
    def __init__(self, records):
        self._recs = records

    def all(self):
        return self._recs

    def get(self, rid):
        for r in self._recs:
            if r.id == rid:
                return r
        return None


def _make_record(rid, domains=None, accountabilities=None, skills=None, archived=False):
    from nooch_village.models import Record, RoleDefinition, RecordType
    return Record(
        id=rid, type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(
            purpose=f"purpose van {rid}",
            accountabilities=accountabilities or [],
            domains=domains or [],
            skills=skills or [],
        ),
        archived=archived,
    )


class TestAndereRol:
    def test_domain_match(self, engine):
        librarian = _make_record("librarian", domains=["bibliotheek"],
                                 accountabilities=["kandidaat-woorden beoordelen"],
                                 skills=["keyword_review"])
        records = SimpleRecords([librarian])
        r = engine.classify("kandidaatwoord voor de bibliotheek: biobased", _ctx(records=records))
        assert r.classification == "andere-rol:librarian"
        assert r.target_role_id == "librarian"
        assert r.target_capability == "keyword_review"

    def test_accountability_overlap(self, engine):
        trends = _make_record("trends",
                              accountabilities=["gsc-queries ophalen", "rapportage maandelijks"],
                              skills=["gsc_performance"])
        records = SimpleRecords([trends])
        r = engine.classify("rapportage maandelijks opmaken voor stakeholders", _ctx(records=records))
        assert r.classification == "andere-rol:trends"
        assert r.target_role_id == "trends"

    def test_domain_beats_accountability(self, engine):
        # Librarian heeft domein-match; trends heeft accountability-overlap → librarian wint
        librarian = _make_record("librarian", domains=["bibliotheek"], skills=["keyword_review"])
        trends = _make_record("trends",
                              accountabilities=["kandidaat beoordelen"], skills=["gsc_performance"])
        records = SimpleRecords([librarian, trends])
        r = engine.classify("kandidaatwoord voor de bibliotheek", _ctx(records=records))
        assert r.target_role_id == "librarian"

    def test_skip_self(self, engine):
        # De analyst staat in records maar mag zichzelf niet selecteren
        analyst = _make_record("website_watcher",
                               accountabilities=["bezoekersdata duiden"],
                               skills=["plausible_stats"])
        records = SimpleRecords([analyst])
        # beschrijving matcht "bezoekersdata" maar rol_id is ook "website_watcher"
        r = engine.classify("bezoekersdata duiden vanuit GSC", _ctx(role_id="website_watcher", records=records))
        # eigen-werk match wint vóór andere-rol-scan
        assert r.classification in ("eigen-werk", "tactisch")  # nooit "andere-rol:analyst"
        assert r.target_role_id != "website_watcher" if r.target_role_id else True

    def test_skip_archived(self, engine):
        archived = _make_record("old_role", domains=["bibliotheek"], archived=True)
        records = SimpleRecords([archived])
        r = engine.classify("kandidaatwoord voor de bibliotheek", _ctx(records=records))
        # gearchiveerd record telt niet mee
        assert r.classification == "tactisch"

    def test_llm_other_role(self, engine):
        librarian = _make_record("librarian", skills=["keyword_review"])
        records = SimpleRecords([librarian])
        ctx = _ctx(records=records)
        r = engine.classify("iets raars", ctx, llm_result="librarian")
        assert r.classification == "andere-rol:librarian"
        assert r.target_role_id == "librarian"
        assert r.target_capability == "keyword_review"

    def test_llm_other_role_no_skills(self, engine):
        facilitator = _make_record("facilitator", skills=[])
        records = SimpleRecords([facilitator])
        ctx = _ctx(records=records)
        r = engine.classify("iets raars", ctx, llm_result="facilitator")
        assert r.classification == "andere-rol:facilitator"
        assert r.target_capability is None


# ── Tactisch ─────────────────────────────────────────────────────────────────

class TestTactisch:
    def test_no_match(self, engine):
        r = engine.classify("de serverruimte heeft een airconditioning storing", _ctx())
        assert r.classification == "tactisch"

    def test_no_match_with_empty_records(self, engine):
        records = SimpleRecords([])
        r = engine.classify("palet vol onbekende taken", _ctx(records=records))
        assert r.classification == "tactisch"

    def test_llm_tactical(self, engine):
        r = engine.classify("korte eenmalige taak", _ctx(), llm_result="tactical")
        assert r.classification == "tactisch"

    def test_no_records(self, engine):
        r = engine.classify("onbekend werk zonder records", _ctx(records=None))
        assert r.classification in ("eigen-werk", "tactisch")
