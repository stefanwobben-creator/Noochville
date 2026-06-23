"""Tests voor HarryHemp (The Scientist) — thread-vrij.

Zeven scenario's:
1. PULS: ngram geeft stijgende term → keyword_proposed gepubliceerd +
   tijdgeest_pulse_completed met ok=True.
2. PULS-FOUT: ngram geeft error → tijdgeest_pulse_completed met ok=False,
   geen keyword_proposed.
3. GROUNDING: keyword_proposed event → keyword_evidence gepubliceerd
   (twee skills: OpenAlex + Semantic Scholar; OpenLibrary niet meer in DNA).
4. GROUNDING-DEDUP: twee keyword_proposed voor dezelfde term terwijl de eerste
   nog in _busy_terms zit → tweede wordt genegeerd.
5. REFLECT: _reflect publiceert precies twee means_gap_sensed-events
   (ngram_2019_cutoff, nl_corpus_coverage); openlibrary_v2 verdwenen uit _reflect.
6. EIGEN TERMEN: Harry's puls publiceert keyword_proposed voor een stijgende
   term; zijn eigen grounding-handler pikt dit op en publiceert keyword_evidence.
   Bevestigt dat de lus precies één keer doorlopen wordt (geen oneindige herhaling).
7. SETUP_EVENTS: dag_begint op de bus → inbox-job enqueued → na drain start de
   puls (tijdgeest_pulse_completed volgt). Bevestigt dat _setup_events
   dag_begint → _maybe_pulse wiert en NIET de default dag_begint → _maybe_reflect.
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
                semscholar_result: dict | None = None):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    registry.register(_StubSkill("ngram_culture",
        ngram_result or {"rows": [], "terms": {}}))
    registry.register(_StubSkill("openalex_evidence",
        openalex_result or {"no_data": True}))
    registry.register(_StubSkill("semscholar_tldr",
        semscholar_result or {"no_data": True}))
    context = SimpleNamespace(
        settings={
            "tijdgeest_interval_seconds": str(tijdgeest_interval),
            "reflect_interval_seconds": "0",
        },
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(status=lambda w: None),
    )
    record = Record(
        id="harry_hemp",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="The Scientist: combineert tijdgeest-observatie en academische grounding",
            skills=["ngram_culture", "openalex_evidence", "semscholar_tldr"],
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
    """keyword_proposed → OpenAlex + Semantic Scholar → keyword_evidence gepubliceerd."""
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


def test_reflect_publiceert_twee_means_gaps(tmp_path):
    """_reflect publiceert precies twee means_gap_sensed: ngram_2019_cutoff en nl_corpus_coverage.

    openlibrary_v2 is verwijderd uit _reflect: de skill staat niet meer in Harry's DNA
    en OpenLibrary-grounding is een toekomstige v2-beslissing.
    """
    harry, bus = _make_harry(tmp_path)

    gaps: list[str] = []
    bus.subscribe("means_gap_sensed", lambda e: gaps.append(e.data["gap_key"]))

    harry._reflect()

    assert "ngram_2019_cutoff"  in gaps
    assert "nl_corpus_coverage" in gaps
    assert "openlibrary_v2"     not in gaps
    assert len(gaps) == 2


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


def test_setup_events_dag_begint_start_puls(tmp_path):
    """SETUP_EVENTS: dag_begint op de bus → _maybe_pulse via inbox → puls draait.

    Bevestigt:
    - dag_begint is gewired op _maybe_pulse (niet op _maybe_reflect).
    - Na drain volgt tijdgeest_pulse_completed (puls heeft daadwerkelijk gedraaid).
    - _maybe_reflect is NIET direct aangeroepen via dag_begint (die route bestaat niet).
    """
    ngram_result = {
        "rows": [
            {"term": "vegan", "locale": "en", "no_data": False,
             "signal": {"direction": "stijgend"}, "freq_last": 0.0005},
        ],
        "terms": {},
    }
    # _pulse_interval=0 zodat _maybe_pulse altijd doorschakelt naar _run_pulse
    harry, bus = _make_harry(tmp_path, tijdgeest_interval=0, ngram_result=ngram_result)

    completed: list[dict] = []
    bus.subscribe("tijdgeest_pulse_completed", lambda e: completed.append(dict(e.data)))

    # Geen handmatige _run_pulse aanroep — alleen dag_begint via de bus
    assert harry.inbox.pending() == 0
    bus.publish(Event("dag_begint", {"label": "test"}, "facilitator"))
    assert harry.inbox.pending() > 0, "dag_begint moet een inbox-job opleveren"

    with patch("nooch_village.llm.reason", return_value=None):
        _drain(harry)

    assert len(completed) == 1, "tijdgeest_pulse_completed verwacht na dag_begint-drain"
    assert completed[0]["ok"] is True
    assert "vegan" in completed[0]["stijgend"]


# ── brokje 5: vraag onderzoeken via bestaande grounding-skills ────────────────

def test_gather_evidence_voegt_beide_bronnen_samen(tmp_path):
    """_gather_evidence bundelt hits van OpenAlex én Semantic Scholar."""
    harry, _ = _make_harry(
        tmp_path,
        openalex_result={"hits": [{"title": "OpenAlex-werk", "source": "openalex"}]},
        semscholar_result={"hits": [{"title": "SemScholar-paper", "source": "semscholar"}]},
    )
    evidence = harry._gather_evidence("barefoot running benefits")
    titels = {e["title"] for e in evidence}
    assert titels == {"OpenAlex-werk", "SemScholar-paper"}


def test_gather_evidence_geen_data_geeft_lege_lijst(tmp_path):
    """Beide bronnen no_data → geen hits, geen crash (fail-closed per bron)."""
    harry, _ = _make_harry(tmp_path)  # stubs geven standaard {"no_data": True}
    assert harry._gather_evidence("iets obscuurs") == []


def test_research_question_geeft_evidence_en_assessment(tmp_path):
    """_research_question onderzoekt een vraag en levert (evidence, assessment)."""
    harry, _ = _make_harry(
        tmp_path,
        openalex_result={"hits": [{"title": "Werk A", "source": "openalex", "year": 2021}]},
        semscholar_result={"hits": [{"title": "Paper B", "source": "semscholar", "year": 2022}]},
    )
    with patch("nooch_village.llm.reason", return_value="Barefoot lopen versterkt voetspieren."):
        evidence, assessment = harry._research_question(
            "Welke voordelen drijven de opkomst van barefoot schoenen?")
    assert len(evidence) == 2
    assert assessment == "Barefoot lopen versterkt voetspieren."


def test_research_question_zonder_bronnen_meldt_dat(tmp_path):
    """Geen bronnen → assessment zegt expliciet dat er niets gevonden is."""
    harry, _ = _make_harry(tmp_path)  # no_data
    with patch("nooch_village.llm.reason", return_value=None):
        evidence, assessment = harry._research_question("een vraag zonder literatuur")
    assert evidence == []
    assert "Geen academische bronnen" in assessment
