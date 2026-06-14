"""Tests voor Stap 9: advies → monitoring, pulse logt gemonitorde metrics."""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from nooch_village.roles import GrowthAnalyst
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger
from nooch_village.observations import ObservationStore
from nooch_village.monitoring import MonitoringStore


def _make_analyst(tmp_path, ledger, obs, monitoring):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=ledger,
        records=None,
        observations=obs,
        monitoring=monitoring,
        strategy=None,
    )
    record = Record(
        id="analyst",
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
    return GrowthAnalyst(record, bus, registry, context), bus


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


@pytest.fixture
def obs(tmp_path):
    return ObservationStore(str(tmp_path / "observations.jsonl"))


@pytest.fixture
def monitoring(tmp_path):
    return MonitoringStore(str(tmp_path / "role_metrics.json"))


@pytest.fixture
def analyst_bus(tmp_path, ledger, obs, monitoring):
    return _make_analyst(tmp_path, ledger, obs, monitoring)


def _advice_event(project_id, keep_metrics, skip_metrics=None):
    advice = [{"metric": m, "verdict": "keep", "rationale": "test"} for m in keep_metrics]
    if skip_metrics:
        advice += [{"metric": m, "verdict": "skip", "rationale": "test"} for m in skip_metrics]
    return Event("project_advice_ready", {"project_id": project_id, "advice": advice}, "noochie")


def _blocked_project(ledger, owner="analyst"):
    pid = ledger.create(owner, {"kind": "discovery"}, "human")
    ledger.block(pid, owner)
    return pid


# ── advies → monitoring ──────────────────────────────────────────────────────

def test_keep_metrics_added_to_monitoring(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors", "pageviews"], skip_metrics=["bounce_rate"]))
    assert set(monitoring.get_metrics("analyst")) == {"visitors", "pageviews"}


def test_skip_metrics_not_in_monitoring(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors"], skip_metrics=["bounce_rate"]))
    assert "bounce_rate" not in monitoring.get_metrics("analyst")


def test_project_completed_with_outcome(analyst_bus, ledger):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors", "pageviews"]))
    p = ledger.get(pid)
    assert p["status"] == "done"
    assert "visitors" in p["outcome"]
    assert "pageviews" in p["outcome"]


def test_monitoring_dedup(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    monitoring.add_metrics("analyst", ["visitors"])
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors", "pageviews"]))
    assert monitoring.get_metrics("analyst").count("visitors") == 1


def test_wrong_owner_ignored(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger, owner="scout")
    analyst._on_advice_ready(_advice_event(pid, ["visitors"]))
    assert ledger.get(pid)["status"] != "done"
    assert monitoring.get_metrics("analyst") == []


def test_no_governance_proposal(analyst_bus, ledger):
    analyst, bus = analyst_bus
    proposals = []
    bus.subscribe("proposal_raised", proposals.append)
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors"]))
    assert proposals == []


# ── pulse logt gemonitorde metrics ───────────────────────────────────────────

def test_pulse_logs_monitored_metrics(analyst_bus, obs, monitoring):
    analyst, _ = analyst_bus
    monitoring.add_metrics("analyst", ["visitors", "pageviews"])
    plausible = {"results": {"visitors": {"value": 42}, "pageviews": {"value": 88}}}
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("analyst", "visitors")["value"] == 42.0
    assert obs.latest("analyst", "pageviews")["value"] == 88.0


def test_pulse_skips_unmonitored_metrics(analyst_bus, obs, monitoring):
    analyst, _ = analyst_bus
    monitoring.add_metrics("analyst", ["visitors"])
    plausible = {"results": {"visitors": {"value": 10}, "pageviews": {"value": 20}}}
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("analyst", "visitors") is not None
    assert obs.latest("analyst", "pageviews") is None


def test_pulse_skips_absent_metrics(analyst_bus, obs, monitoring):
    analyst, _ = analyst_bus
    monitoring.add_metrics("analyst", ["visitors", "pageviews"])
    plausible = {"results": {"visitors": {"value": 5}}}
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("analyst", "visitors") is not None
    assert obs.latest("analyst", "pageviews") is None


def test_pulse_no_monitoring_store_is_noop(analyst_bus, obs):
    analyst, _ = analyst_bus
    analyst.context.monitoring = None
    plausible = {"results": {"visitors": {"value": 99}}}
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("analyst", "visitors") is None
