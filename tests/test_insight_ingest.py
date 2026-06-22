from __future__ import annotations
import logging
import pytest
from types import SimpleNamespace
from nooch_village.insight_ingest import insight_from_grounding, _slug
from nooch_village.insight import Insight, GroundingStatus
from nooch_village.notes_store import NotesStore


def test_assessment_levert_unresolved_insight():
    kaartje = insight_from_grounding("vegan", "Vegan schoenen zijn veelal plasticvrij.")
    assert kaartje is not None
    assert kaartje.status == GroundingStatus.UNRESOLVED
    assert kaartje.claim == "Vegan schoenen zijn veelal plasticvrij."


def test_leeg_assessment_levert_none():
    assert insight_from_grounding("vegan", "") is None
    assert insight_from_grounding("vegan", "   ") is None


def test_concept_id_op_kaartje():
    kaartje = insight_from_grounding("vegan", "Relevant voor de missie.", concept_id="vegan")
    assert kaartje is not None
    assert kaartje.concept_id == "vegan"


def test_evidence_titels_in_reference_en_deterministische_id():
    evidence = [
        {"title": "Paper A", "year": 2020},
        {"title": "Paper B", "year": 2021},
        {"title": "Paper C", "year": 2022},
        {"title": "Paper D", "year": 2023},
    ]
    kaartje1 = insight_from_grounding("duurzaam", "Duurzaamheid groeit.", evidence=evidence)
    kaartje2 = insight_from_grounding("duurzaam", "Andere tekst.", evidence=evidence)
    assert kaartje1 is not None
    assert "Paper A" in kaartje1.reference
    assert "Paper B" in kaartje1.reference
    assert "Paper C" in kaartje1.reference
    assert "Paper D" not in kaartje1.reference  # alleen eerste 3
    assert kaartje1.id == kaartje2.id            # deterministisch op word


def test_word_veld_gevuld_na_grounding():
    kaartje = insight_from_grounding("vegan shoes", "Relevant voor missie-schoenen.")
    assert kaartje is not None
    assert kaartje.word == "vegan shoes"


def test_insight_zonder_word_veld_laadt_backward_compat():
    from nooch_village.insight import Insight
    kaartje = Insight(id="test_id", claim="een claim", source="handmatig")
    assert kaartje.word is None


def test_tweede_grounding_verrijkt_kaart(tmp_path):
    """_on_evidence twee keer voor hetzelfde woord → kaart verrijkt: 1 kaart, claim intact,
    grounding_count == 2, last_updated_at gezet."""
    from nooch_village.roles import Librarian
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.event_bus import EventBus, Event
    from nooch_village.skills import SkillRegistry
    from nooch_village.notes_store import NotesStore

    bus = EventBus(name="test")
    record = Record(
        id="librarian",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="test"),
        source="seed",
    )
    notes = NotesStore(str(tmp_path / "notes.json"))
    context = SimpleNamespace(
        settings={},
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(status=lambda w: None),
        lexicon=SimpleNamespace(concept_for_word=lambda w: None),
        notes=notes,
    )
    librarian = Librarian(record, bus, SkillRegistry(), context)

    event = Event("keyword_evidence", {
        "word": "vegan",
        "assessment": "Relevant voor de missie.",
        "evidence": [],
        "from": "harry_hemp",
    }, "harry_hemp")

    librarian._on_evidence(event)
    librarian._on_evidence(event)  # tweede grounding → verrijking

    assert len(notes.all()) == 1
    kaart = notes.all()[0]
    assert kaart.claim == "Relevant voor de missie."
    assert kaart.grounding_count == 2
    assert kaart.last_updated_at is not None


def _make_librarian(tmp_path, notes=None, skill_decision="approve"):
    """Helper: bouw een Librarian met nep-context en instelbaar keyword_review-oordeel."""
    from nooch_village.roles import Librarian
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.event_bus import EventBus
    from nooch_village.skills import SkillRegistry, Skill

    class FakeReviewSkill(Skill):
        name = "keyword_review"
        description = "nep"
        def run(self, payload, context):
            return {"decision": skill_decision, "reason": "test", "basis": "heuristic"}

    bus    = EventBus(name="test")
    record = Record(
        id="librarian", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="test", skills=["keyword_review", "verband_voorstel"]),
        source="seed",
    )
    registry = SkillRegistry()
    registry.register(FakeReviewSkill())
    from nooch_village.skills_impl.verband_voorstel import VerbandVoorstelSkill
    registry.register(VerbandVoorstelSkill())

    ctx_notes = notes if notes is not None else NotesStore(str(tmp_path / "notes.json"))
    context = SimpleNamespace(
        settings={},
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(
            status=lambda w: None,
            curate=lambda *a, **kw: None,
        ),
        lexicon=SimpleNamespace(concept_for_word=lambda w: None),
        notes=ctx_notes,
        observations=None,
    )
    return Librarian(record, bus, registry, context), bus


def test_librarian_logt_verwante_kennis_bij_voorstel(tmp_path, caplog):
    """Bij een proposal voor 'vegan trail shoes' vindt de Librarian twee verwante
    kaartjes (vegan running shoes, barefoot shoes) en logt de 📚-regel."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim=".", source="test", word="vegan running shoes"))
    notes.add(Insight(id="b", claim=".", source="test", word="barefoot shoes"))

    librarian, _ = _make_librarian(tmp_path, notes=notes)

    from nooch_village.event_bus import Event
    event = Event("keyword_proposed", {
        "word": "vegan trail shoes",
        "demand": {"signal": "positive"},
        "from": "website_watcher",
    }, "website_watcher")

    with caplog.at_level(logging.INFO, logger="village.librarian"):
        librarian._on_proposal(event)

    assert any("📚" in r.message and "vegan trail shoes" in r.message
               for r in caplog.records), (
        f"Verwachtte 📚-logregel; gevonden: {[r.message for r in caplog.records]}"
    )


def test_librarian_geen_fout_bij_lege_kennis(tmp_path, caplog):
    """Bij een proposal zonder verwante kennis loopt _on_proposal zonder fout en
    zonder 📚-logregel door."""
    librarian, _ = _make_librarian(tmp_path)

    from nooch_village.event_bus import Event
    event = Event("keyword_proposed", {
        "word": "leather boots",
        "demand": {"signal": "positive"},
        "from": "website_watcher",
    }, "website_watcher")

    with caplog.at_level(logging.INFO, logger="village.librarian"):
        librarian._on_proposal(event)

    assert not any("📚" in r.message for r in caplog.records)


# ── Tests voor Librarian dag-reflectie (_on_dag_eindigt) ─────────────────────

def _dag_eindigt_event():
    from nooch_village.event_bus import Event
    return Event("dag_eindigt", {"label": "2026-06-22"}, "facilitator")


def test_dag_reflectie_vindt_vegan_paar(tmp_path, caplog):
    """Drie kaarten: vegan running shoes en vegan trail shoes delen 'vegan' → paar gevonden.
    leather boots deelt niets met de vegan-kaarten → geen paar met hen."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim=".", source="test", word="vegan running shoes"))
    notes.add(Insight(id="b", claim=".", source="test", word="vegan trail shoes"))
    notes.add(Insight(id="c", claim=".", source="test", word="leather boots"))

    librarian, _ = _make_librarian(tmp_path, notes=notes)

    with caplog.at_level(logging.INFO, logger="village.librarian"):
        librarian._on_dag_eindigt(_dag_eindigt_event())

    berichten = [r.message for r in caplog.records]
    assert any("🔗" in m and "kandidaat-verband" in m for m in berichten), (
        f"Verwachtte 🔗-kandidaat-verband; got: {berichten}"
    )
    assert not any("leather boots" in m and "vegan" in m for m in berichten), (
        f"leather boots mag geen paar vormen met vegan; got: {berichten}"
    )


def test_dag_reflectie_geen_verbanden_bij_geen_overlap(tmp_path, caplog):
    """Twee kaarten zonder gedeelde woorden → geen kandidaat-verbanden."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim=".", source="test", word="vegan shoes"))
    notes.add(Insight(id="b", claim=".", source="test", word="leather gloves"))

    librarian, _ = _make_librarian(tmp_path, notes=notes)

    with caplog.at_level(logging.INFO, logger="village.librarian"):
        librarian._on_dag_eindigt(_dag_eindigt_event())

    berichten = [r.message for r in caplog.records]
    assert any("geen kandidaat-verbanden" in m for m in berichten), (
        f"Verwachtte 'geen kandidaat-verbanden'; got: {berichten}"
    )


def test_dag_reflectie_te_weinig_kaarten_geen_crash(tmp_path, caplog):
    """Minder dan twee kaarten-met-word → handler loopt zonder fout, geen paren."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim=".", source="test", word="vegan shoes"))

    librarian, _ = _make_librarian(tmp_path, notes=notes)

    with caplog.at_level(logging.INFO, logger="village.librarian"):
        librarian._on_dag_eindigt(_dag_eindigt_event())

    berichten = [r.message for r in caplog.records]
    assert not any("🔗" in m for m in berichten)
