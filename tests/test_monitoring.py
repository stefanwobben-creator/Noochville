"""Tests voor Stap 9: advies → monitoring, pulse logt gemonitorde metrics."""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from nooch_village.roles import WebsiteWatcherWorker
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
    return WebsiteWatcherWorker(record, bus, registry, context), bus


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


def _blocked_project(ledger, owner="website_watcher"):
    pid = ledger.create(owner, {"kind": "discovery"}, "human")
    ledger.block(pid, owner)
    return pid


# ── advies → monitoring ──────────────────────────────────────────────────────

def test_keep_metrics_added_to_monitoring(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors", "pageviews"], skip_metrics=["bounce_rate"]))
    assert set(monitoring.get_metrics("website_watcher")) == {"visitors", "pageviews"}


def test_skip_metrics_not_in_monitoring(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors"], skip_metrics=["bounce_rate"]))
    assert "bounce_rate" not in monitoring.get_metrics("website_watcher")


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
    monitoring.add_metrics("website_watcher", ["visitors"])
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors", "pageviews"]))
    assert monitoring.get_metrics("website_watcher").count("visitors") == 1


def test_wrong_owner_ignored(analyst_bus, ledger, monitoring):
    analyst, _ = analyst_bus
    pid = _blocked_project(ledger, owner="trends")
    analyst._on_advice_ready(_advice_event(pid, ["visitors"]))
    assert ledger.get(pid)["status"] != "done"
    assert monitoring.get_metrics("website_watcher") == []


def test_no_governance_proposal(analyst_bus, ledger):
    analyst, bus = analyst_bus
    proposals = []
    bus.subscribe("proposal_raised", proposals.append)
    pid = _blocked_project(ledger)
    analyst._on_advice_ready(_advice_event(pid, ["visitors"]))
    assert proposals == []


# ── pulse: reference, don't copy — GEEN kopie van gemonitorde metrics ─────────

def test_pulse_geen_kopie_van_monitored_metrics(analyst_bus, obs, monitoring):
    """De rol VOLGT metrics (curatie), maar schrijft de rauwe waarden NIET meer onder role_id — de
    canonieke plausible_*_day loopt via de collector. De curatie-lijst blijft intact als referentie."""
    analyst, _ = analyst_bus
    monitoring.add_metrics("website_watcher", ["visitors", "pageviews"])
    plausible = {"results": {"visitors": {"value": 42}, "pageviews": {"value": 88}}}
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("website_watcher", "visitors") is None        # geen rauwe-naam-kopie onder role_id
    assert obs.latest("website_watcher", "pageviews") is None
    assert set(monitoring.get_metrics("website_watcher")) == {"visitors", "pageviews"}   # curatie intact


def test_pulse_no_monitoring_store_is_noop(analyst_bus, obs):
    analyst, _ = analyst_bus
    analyst.context.monitoring = None
    plausible = {"results": {"visitors": {"value": 99}}}
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("website_watcher", "visitors") is None


def test_pulse_logs_utm_sources_without_monitoring_store(analyst_bus, obs):
    analyst, _ = analyst_bus
    analyst.context.monitoring = None
    plausible = {
        "results": {"visitors": {"value": 50}},
        "utm_sources": [
            {"utm_source": "bluemarble", "visitors": 7},
            {"utm_source": "ig", "visitors": 2},
        ],
    }
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("website_watcher", "visitors_via_bluemarble")["value"] == 7.0
    assert obs.latest("website_watcher", "visitors_via_ig")["value"] == 2.0
    assert obs.latest("website_watcher", "visitors") is None


def test_pulse_logs_utm_sources_geen_monitored_kopie(analyst_bus, obs, monitoring):
    """UTM-kanaaldata (visitors_via_*) wordt wél gelogd (eigen bron, geen collector-pad); een gemonitorde
    canonieke metric (visitors) wordt NIET gekopieerd onder role_id."""
    analyst, _ = analyst_bus
    monitoring.add_metrics("website_watcher", ["visitors"])
    plausible = {
        "results": {"visitors": {"value": 50}},
        "utm_sources": [{"utm_source": "bluemarble", "visitors": 7}],
    }
    analyst._log_pulse_metrics(plausible)
    assert obs.latest("website_watcher", "visitors") is None        # geen kopie van de canonieke metric
    assert obs.latest("website_watcher", "visitors_via_bluemarble")["value"] == 7.0   # UTM-kanaal wél
