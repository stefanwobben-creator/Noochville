"""Tests voor project-afhandeling in Inhabitant — thread-vrij."""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger


def _make_inhabitant(tmp_path, ledger):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=ledger,
        records=None,
    )
    record = Record(
        id="website_watcher",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="groei meten",
            accountabilities=[],
            domains=[],
            skills=[],
        ),
        source="seed",
    )
    return Inhabitant(record, bus, registry, context)


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


@pytest.fixture
def inhabitant(tmp_path, ledger):
    return _make_inhabitant(tmp_path, ledger)


def test_claim_run_complete_sets_done(inhabitant, ledger):
    pid = ledger.create("website_watcher", "schrijf vegan-pagina", "human")
    inhabitant._claim_run_complete(pid)
    assert ledger.get(pid)["status"] == "done"


def test_claim_run_complete_calls_run_project(inhabitant, ledger):
    called = []

    def mock_run(project):
        called.append(project)
        return "custom_outcome"

    inhabitant.run_project = mock_run
    pid = ledger.create("website_watcher", "analyseer", "human")
    inhabitant._claim_run_complete(pid)
    assert len(called) == 1
    assert called[0]["id"] == pid


def test_claim_run_complete_outcome_from_run_project(inhabitant, ledger):
    inhabitant.run_project = lambda p: "prop_123"
    pid = ledger.create("website_watcher", "werk", "human")
    inhabitant._claim_run_complete(pid)
    assert ledger.get(pid)["outcome"] == "prop_123"


def test_claim_run_complete_default_stub_outcome(inhabitant, ledger):
    pid = ledger.create("website_watcher", "werk", "human")
    inhabitant._claim_run_complete(pid)
    assert ledger.get(pid)["outcome"] == "stub:done"


def test_on_project_queued_skips_wrong_owner(inhabitant, ledger):
    pid = ledger.create("website_watcher", "werk", "human")
    event = Event("project_queued", {"project_id": pid, "owner": "scout"}, "village")
    inhabitant._on_project_queued(event)
    assert ledger.get(pid)["status"] == "queued"


def test_on_project_queued_triggers_for_correct_owner(inhabitant, ledger):
    pid = ledger.create("website_watcher", "werk", "human")
    event = Event("project_queued", {"project_id": pid, "owner": "website_watcher"}, "village")
    inhabitant._on_project_queued(event)
    assert ledger.get(pid)["status"] == "done"
