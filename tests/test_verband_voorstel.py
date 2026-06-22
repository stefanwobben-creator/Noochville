from __future__ import annotations
import logging
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.verband_voorstel import VerbandVoorstelSkill
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


_KAART_A = {"word": "vegan running shoes", "claim": "Vegan schoenen zijn plasticvrij."}
_KAART_B = {"word": "vegan trail shoes",   "claim": "Trail schoenen mijden synthetisch materiaal."}
_KAART_C = {"word": "leather boots",       "claim": "Leren laarzen zijn duurzaam."}


def _run(kaart_a, kaart_b, reason_return):
    skill = VerbandVoorstelSkill()
    with patch("nooch_village.llm.reason", return_value=reason_return):
        return skill.run({"kaart_a": kaart_a, "kaart_b": kaart_b}, context=None)


def test_verband_ja_geeft_claim():
    """LLM bevestigt verband → verband True, claim gevuld."""
    uitslag = _run(_KAART_A, _KAART_B,
                   "VERBAND: ja | CLAIM: Beide kaarten gaan over plasticvrij schoenmateriaal.")
    assert uitslag["verband"] is True
    assert uitslag["claim"] == "Beide kaarten gaan over plasticvrij schoenmateriaal."


def test_verband_nee_geeft_false():
    """LLM zegt nee → verband False, geen claim."""
    uitslag = _run(_KAART_A, _KAART_C, "VERBAND: nee | CLAIM: geen")
    assert uitslag["verband"] is False
    assert "claim" not in uitslag


def test_verband_geen_llm_fail_closed():
    """Geen LLM-key (reason returns None) → fail-closed, verband False."""
    uitslag = _run(_KAART_A, _KAART_B, None)
    assert uitslag["verband"] is False
    assert "claim" not in uitslag


def test_verband_onparseerbaar_fail_closed():
    """Rommel-output van LLM → fail-closed, verband False."""
    uitslag = _run(_KAART_A, _KAART_B, "Dit is totaal onleesbare output zonder formaat.")
    assert uitslag["verband"] is False
    assert "claim" not in uitslag


# ── Librarian _on_dag_eindigt integratietest ────────────────────────────────

def _make_librarian(tmp_path, notes=None, skill_decision="approve"):
    from nooch_village.roles import Librarian
    from nooch_village.models import Record, RoleDefinition, RecordType
    from nooch_village.event_bus import EventBus
    from nooch_village.skills import SkillRegistry, Skill

    class FakeReviewSkill(Skill):
        name = "keyword_review"
        description = "nep"
        def run(self, payload, context):
            return {"decision": skill_decision, "reason": "test", "basis": "heuristic"}

    bus = EventBus(name="test")
    record = Record(
        id="librarian", type=RecordType.ROLE, parent="noochville",
        definition=RoleDefinition(purpose="test", skills=["keyword_review", "verband_voorstel"]),
        source="seed",
    )
    registry = SkillRegistry()
    registry.register(FakeReviewSkill())
    registry.register(VerbandVoorstelSkill())

    ctx_notes = notes if notes is not None else NotesStore(str(tmp_path / "notes.json"))
    context = SimpleNamespace(
        settings={},
        data_dir=str(tmp_path),
        records=None,
        library=SimpleNamespace(status=lambda w: None, curate=lambda *a, **kw: None),
        lexicon=SimpleNamespace(concept_for_word=lambda w: None),
        notes=ctx_notes,
        observations=None,
    )
    return Librarian(record, bus, registry, context), bus


def _dag_eindigt_event():
    from nooch_village.event_bus import Event
    return Event("dag_eindigt", {"label": "2026-06-22"}, "facilitator")


def test_dag_eindigt_publiceert_human_decision_bij_verband(tmp_path):
    """Twee verwante kaarten + LLM bevestigt verband → human_decision_needed gepubliceerd."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim="Vegan schoenen zijn plasticvrij.", source="test",
                      word="vegan running shoes"))
    notes.add(Insight(id="b", claim="Trail schoenen mijden synthetisch materiaal.", source="test",
                      word="vegan trail shoes"))

    librarian, bus = _make_librarian(tmp_path, notes=notes)

    gepubliceerd = []
    bus.subscribe("human_decision_needed", lambda e: gepubliceerd.append(e))

    llm_antwoord = "VERBAND: ja | CLAIM: Beide kaarten gaan over plasticvrij schoenmateriaal."
    with patch("nooch_village.llm.reason", return_value=llm_antwoord):
        librarian._on_dag_eindigt(_dag_eindigt_event())

    assert len(gepubliceerd) == 1
    evt = gepubliceerd[0]
    assert evt.data["topic"] == "verband"
    assert evt.data["kaart_a_id"] == "a"
    assert evt.data["kaart_b_id"] == "b"
    assert "plasticvrij" in evt.data["voorstel_claim"]


def test_dag_eindigt_geen_event_bij_geen_verband(tmp_path):
    """LLM zegt nee → geen human_decision_needed."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim="Vegan schoenen zijn plasticvrij.", source="test",
                      word="vegan running shoes"))
    notes.add(Insight(id="b", claim="Trail schoenen mijden synthetisch materiaal.", source="test",
                      word="vegan trail shoes"))

    librarian, bus = _make_librarian(tmp_path, notes=notes)

    gepubliceerd = []
    bus.subscribe("human_decision_needed", lambda e: gepubliceerd.append(e))

    with patch("nooch_village.llm.reason", return_value="VERBAND: nee | CLAIM: geen"):
        librarian._on_dag_eindigt(_dag_eindigt_event())

    assert gepubliceerd == []


def test_dag_eindigt_geen_event_bij_geen_llm(tmp_path):
    """Geen LLM-key (reason=None) → fail-closed, geen human_decision_needed."""
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim="Vegan schoenen zijn plasticvrij.", source="test",
                      word="vegan running shoes"))
    notes.add(Insight(id="b", claim="Trail schoenen mijden synthetisch materiaal.", source="test",
                      word="vegan trail shoes"))

    librarian, bus = _make_librarian(tmp_path, notes=notes)

    gepubliceerd = []
    bus.subscribe("human_decision_needed", lambda e: gepubliceerd.append(e))

    with patch("nooch_village.llm.reason", return_value=None):
        librarian._on_dag_eindigt(_dag_eindigt_event())

    assert gepubliceerd == []
