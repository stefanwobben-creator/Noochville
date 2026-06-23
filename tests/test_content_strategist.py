"""Tests voor de ContentStrategist-inwoner (Fase 2 brokje 13c). Thread-vrij.

Spot content-waardige clusters → content_opportunity; goedgekeurde suggestie → draft
via content_schrijven → content_draft_ready.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village.roles import ContentStrategist
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry, Skill
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


class _Stub(Skill):
    def __init__(self, name, result):
        self.name = name
        self.description = f"stub:{name}"
        self._result = result

    def run(self, payload, context):
        return self._result


def _make(tmp_path, draft_result=None):
    bus = EventBus(name="test")
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="trend", claim="barefoot stijgt", source="t",
                      word="barefoot shoes", grounding_count=4))
    notes.add(Insight(id="b", claim="barefoot is gezond", source="t",
                      word="barefoot health", grounding_count=1, links_to=["trend"]))
    registry = SkillRegistry()
    registry.register(_Stub("content_schrijven",
        draft_result if draft_result is not None
        else {"text": "EERSTE DRAFT", "claim_insight_ids": ["trend", "b"], "kind": "blog"}))
    ctx = SimpleNamespace(settings={"content_budget": "2", "reflect_interval_seconds": "0"},
                          data_dir=str(tmp_path), records=None, notes=notes)
    record = Record(id="content_strategist", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="content", skills=["content_schrijven"]),
                    source="sensed")
    return ContentStrategist(record, bus, registry, ctx), bus


def test_spot_content_publiceert_kans(tmp_path):
    cs, bus = _make(tmp_path)
    events = []
    bus.subscribe("content_opportunity", lambda e: events.append(dict(e.data)))
    cs._spot_content(Event("dag_begint", {}, "facilitator"))
    assert len(events) == 1
    assert events[0]["seed_id"] == "trend"
    assert set(events[0]["cluster_ids"]) == {"trend", "b"}


def test_goedgekeurde_suggestie_levert_draft(tmp_path):
    cs, bus = _make(tmp_path)
    drafts = []
    bus.subscribe("content_draft_ready", lambda e: drafts.append(dict(e.data)))
    cs._on_suggestion_approved(Event("content_suggestion_approved",
        {"seed_id": "trend", "kind": "blog", "audience": "Yasmine"}, "human"))
    assert len(drafts) == 1
    assert drafts[0]["text"] == "EERSTE DRAFT"
    assert drafts[0]["kind"] == "blog"


def test_geen_draft_zonder_tekst(tmp_path):
    cs, bus = _make(tmp_path, draft_result={"text": None, "claim_insight_ids": [], "kind": "blog"})
    drafts = []
    bus.subscribe("content_draft_ready", lambda e: drafts.append(dict(e.data)))
    cs._on_suggestion_approved(Event("content_suggestion_approved",
        {"seed_id": "trend", "kind": "blog"}, "human"))
    assert drafts == []


def test_geen_draft_voor_onbekende_seed(tmp_path):
    cs, bus = _make(tmp_path)
    drafts = []
    bus.subscribe("content_draft_ready", lambda e: drafts.append(dict(e.data)))
    cs._on_suggestion_approved(Event("content_suggestion_approved",
        {"seed_id": "bestaat_niet", "kind": "blog"}, "human"))
    assert drafts == []
