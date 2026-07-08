"""Tests voor discovery-project flow in GrowthAnalyst — thread-vrij."""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from nooch_village.roles import WebsiteWatcherWorker
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger

_STUB_CATALOG = ["visitors", "pageviews"]


class _StubPlausible:
    name = "plausible_stats"

    def available_metrics(self):
        return list(_STUB_CATALOG)

    def run(self, payload, context):
        return {}


def _make_analyst(tmp_path, ledger):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    registry._skills["plausible_stats"] = _StubPlausible()
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=ledger,
        records=None,
        observations=None,
        strategy=None,
    )
    record = Record(
        id="website_watcher",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="groei meten",
            accountabilities=[],
            domains=[],
            skills=["plausible_stats"],
        ),
        source="seed",
    )
    return WebsiteWatcherWorker(record, bus, registry, context), bus


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


@pytest.fixture
def analyst_bus(tmp_path, ledger):
    return _make_analyst(tmp_path, ledger)


def test_discovery_blocks_project_on_noochie(analyst_bus, ledger):
    analyst, _ = analyst_bus
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    analyst._claim_run_complete(pid)
    p = ledger.get(pid)
    assert p["status"] == "blocked"
    assert p["blocked_on"] == "noochie"


def test_discovery_event_carries_catalog(analyst_bus, ledger):
    analyst, bus = analyst_bus
    received = []
    bus.subscribe("project_discovery_ready", received.append)
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    analyst._claim_run_complete(pid)
    assert len(received) == 1
    assert received[0].data["project_id"] == pid
    assert received[0].data["catalog"] == _STUB_CATALOG


def test_catalog_not_stored_in_ledger(analyst_bus, ledger):
    analyst, _ = analyst_bus
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    analyst._claim_run_complete(pid)
    p = ledger.get(pid)
    assert "catalog" not in p
    assert "visitors" not in str(p.get("outcome") or "")


def test_non_discovery_zonder_checklist_geen_valse_done(analyst_bus, ledger):
    # string-scope zonder voorbereiding → geen uitvoering, geen valse done (stub:done vervangen door de
    # checklist-flow: uitvoer-primitief fase 1). Met checklist zou het wél uitvoeren.
    analyst, _ = analyst_bus
    pid = ledger.create("website_watcher", "gewoon schrijfwerk", "human")
    analyst._claim_run_complete(pid)
    p = ledger.get(pid)
    assert p["status"] != "done" and p.get("outcome") != "stub:done"
