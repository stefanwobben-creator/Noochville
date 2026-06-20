"""Tests voor HarryHemp (The Scientist) — thread-vrij.

Zes scenario's:
1. PULS: ngram geeft stijgende term → keyword_proposed gepubliceerd +
   tijdgeest_pulse_completed met ok=True.
2. PULS-FOUT: ngram geeft error → tijdgeest_pulse_completed met ok=False,
   geen keyword_proposed.
3. GROUNDING: keyword_proposed event → keyword_evidence gepubliceerd
   (drie skills gemockt).
4. GROUNDING-DEDUP: twee keyword_proposed voor dezelfde term terwijl de eerste
   nog in _busy_terms zit → tweede wordt genegeerd.
5. REFLECT: _reflect publiceert precies drie means_gap_sensed-events
   (ngram_2019_cutoff, nl_corpus_coverage, openlibrary_v2).
6. EIGEN TERMEN: Harry's puls publiceert keyword_proposed voor een stijgende
   term; zijn eigen grounding-handler pikt dit op en publiceert keyword_evidence.
   Bevestigt dat de lus precies één keer doorlopen wordt (geen oneindige herhaling).
"""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from nooch_village.roles import HarryHemp
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill


# ── Helpers ───────────────────────────────────────────────────────────────────

class _StubSkill(Skill):
    """Generieke stub-skill die een configureerbaar resultaat retourneert."""
    def __init__(self, name: str, result: dict):
        self.name = name
        self.description = f"stub:{name}"
        self._result = result

    def run(self, payload: dict, context) -> dict:
        return self._result


def _make_harry(tmp_path, *,
                tijdgeest_interval: int = 0,
                ngram_result: dict | None = None,
                openalex_result: dict | None = None,
                semscholar_result: dict | None = None,
                openlibrary_result: dict | None = None):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    registry.register(_StubSkill("ngram_culture",
        ngram_result or {"rows": [], "terms": {}}))
    registry.register(_StubSkill("openalex_evidence",
        openalex_result or {"no_data": True}))
    registry.register(_StubSkill("semscholar_tldr",
        semscholar_result or {"no_data": True}))
    registry.register(_StubSkill("openlibrary_search_inside",
        openlibrary_result or {"hits": []}))
    context = SimpleNamespace(
        settings={
            "tijdgeest_interval_seconds": str(tijdgeest_interval),
            "reflect_interval_seconds": "0",
        },
        data_dir=str(tmp_path),
        records=None,
        library=None,
    )
    record = Record(
        id="harry_hemp",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="The Scientist: combineert tijdgeest-observatie en academische grounding",
            skills=["ngram_culture", "openalex_evidence", "semscholar_tldr",
                    "openlibrary_search_inside"],
        ),
        source="seed",
    )
    record.persona = "Harry Hemp"
    harry = HarryHemp(record, bus, registry, context)
    return harry, bus


def _drain(harry) -> None:
    while harry.inbox.pending() > 0:
        job = harry.inbox.take(timeout=0.05)
        if job and callable(job):
            job()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_puls_stijgende_term_publiceert_keyword_proposed(tmp_path):
    """Puls met één stijgende term → keyword_proposed + tijdgeest_pulse_completed."""
    ngram_result = {
        "rows": [
            {"term": "regeneratief", "locale": "nl", "no_data": False,
             "signal": {"direction": "stijgend"}, "freq_last": 0.0003},
        ],
        "terms": {},
    }
    harry, bus = _make_harry(tmp_path, ngram_result=ngram_result)

    proposed: list[dict] = []
    completed: list[dict] = []
    bus.subscribe("keyword_proposed",         lambda e: proposed.append(dict(e.data)))
    bus.subscribe("tijdgeest_pulse_completed", lambda e: completed.append(dict(e.data)))

    harry._run_pulse(Event("tijdgeest_pulse", {}, "test"))

    assert len(proposed) == 1
    assert proposed[0]["word"] == "regeneratief"
    assert proposed[0]["demand"]["direction"] == "stijgend"

    assert len(completed) == 1
    assert completed[0]["ok"] is True
    assert "regeneratief" in completed[0]["stijgend"]


def test_puls_fout_publiceert_completed_niet_ok(tmp_path):
    """Ngram-fout → tijdgeest_pulse_completed met ok=False, geen keyword_proposed."""
    harry, bus = _make_harry(tmp_path, ngram_result={"error": "netwerk-timeout"})

    proposed: list[str] = []
    completed: list[dict] = []
    bus.subscribe("keyword_proposed",         lambda e: proposed.append(e.data["word"]))
    bus.subscribe("tijdgeest_pulse_completed", lambda e: completed.append(dict(e.data)))

    harry._run_pulse(Event("tijdgeest_pulse", {}, "test"))

    assert proposed == []
    assert len(completed) == 1
    assert completed[0]["ok"] is False
    assert "netwerk-timeout" in completed[0]["error"]


def test_grounding_keyword_proposed_publiceert_evidence(tmp_path):
    """keyword_proposed → drie skills aanroepen → keyword_evidence gepubliceerd."""
    openalex  = {"hits": [{"title": "Regenerative Farming", "year": 2021,
                            "source": "openalex", "tldr": ""}]}
    semscholar = {"hits": [{"title": "Regen. Design Principles", "year": 2019,
                             "source": "semantic_scholar", "tldr": "regeneratief is goed"}]}
    harry, bus = _make_harry(tmp_path,
                             openalex_result=openalex,
                             semscholar_result=semscholar)

    evidence_events: list[dict] = []
    bus.subscribe("keyword_evidence", lambda e: evidence_events.append(dict(e.data)))

    with patch("nooch_village.llm.reason", return_value="Goed onderbouwd."):
        harry._on_keyword_proposed(Event("keyword_proposed", {
            "word": "regeneratief",
            "demand": {"locale": "nl", "source": "ngram_culture"},
        }, "tijdgeest_wachter"))

    assert len(evidence_events) == 1
    ev = evidence_events[0]
    assert ev["word"] == "regeneratief"
    assert ev["locale"] == "nl"
    assert len(ev["evidence"]) == 2   # openalex + semscholar; openlibrary → no hits
    assert ev["assessment"] == "Goed onderbouwd."
    assert ev["from"] == "harry_hemp"


def test_grounding_dedup_tweede_term_genegeerd(tmp_path):
    """Tweede keyword_proposed voor dezelfde term terwijl eerste in _busy_terms → genegeerd."""
    harry, bus = _make_harry(tmp_path)

    evidence_events: list[dict] = []
    bus.subscribe("keyword_evidence", lambda e: evidence_events.append(dict(e.data)))

    # Simuleer dat de term al wordt verwerkt
    harry._busy_terms.add("regeneratief")

    harry._on_keyword_proposed(Event("keyword_proposed", {
        "word": "regeneratief",
        "demand": {"locale": "nl"},
    }, "test"))

    assert evidence_events == [], "tweede aanroep moet stil worden genegeerd"
    assert "regeneratief" in harry._busy_terms   # nog steeds erin (extern ingesteld)


def test_reflect_publiceert_drie_means_gaps(tmp_path):
    """_reflect publiceert precies drie means_gap_sensed: ngram_2019, nl_corpus, openlibrary."""
    harry, bus = _make_harry(tmp_path)

    gaps: list[str] = []
    bus.subscribe("means_gap_sensed", lambda e: gaps.append(e.data["gap_key"]))

    harry._reflect()

    assert "ngram_2019_cutoff"   in gaps
    assert "nl_corpus_coverage"  in gaps
    assert "openlibrary_v2"      in gaps
    assert len(gaps) == 3


def test_eigen_termen_worden_gegrond_zonder_lus(tmp_path):
    """Harry's puls publiceert keyword_proposed; zijn grounding-handler pikt het op.
    keyword_evidence wordt gepubliceerd; er komt geen tweede keyword_proposed (geen lus).
    """
    ngram_result = {
        "rows": [
            {"term": "vegan", "locale": "en", "no_data": False,
             "signal": {"direction": "stijgend"}, "freq_last": 0.0005},
        ],
        "terms": {},
    }
    openalex = {"hits": [{"title": "Vegan Leather Alternatives", "year": 2022,
                           "source": "openalex", "tldr": ""}]}
    harry, bus = _make_harry(tmp_path, ngram_result=ngram_result, openalex_result=openalex)

    proposed: list[str] = []
    evidence: list[str] = []
    bus.subscribe("keyword_proposed", lambda e: proposed.append(e.data["word"]))
    bus.subscribe("keyword_evidence",  lambda e: evidence.append(e.data["word"]))

    with patch("nooch_village.llm.reason", return_value=None):
        # Stap 1: puls → publiceert keyword_proposed voor "vegan"
        harry._run_pulse(Event("tijdgeest_pulse", {}, "test"))
        # Stap 2: drain → _on_keyword_proposed draait voor "vegan"
        _drain(harry)

    assert proposed == ["vegan"], "precies één keyword_proposed verwacht"
    assert evidence == ["vegan"],  "keyword_evidence voor 'vegan' verwacht"
    # Geen tweede ronde: de grounding publiceert geen keyword_proposed terug
