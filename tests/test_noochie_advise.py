"""Tests voor Noochie discovery-advies — thread-vrij."""
from __future__ import annotations
import pytest
from types import SimpleNamespace
from nooch_village.roles import Noochie, advise_metrics
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger


def _make_noochie(tmp_path, ledger):
    bus = EventBus(name="test")
    registry = SkillRegistry()
    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=ledger,
        records=None,
        observations=None,
    )
    record = Record(
        id="noochie",
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(purpose="missiestem", accountabilities=[], domains=[], skills=[]),
        source="seed",
    )
    return Noochie(record, bus, registry, context), bus


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


@pytest.fixture
def noochie_bus(tmp_path, ledger):
    return _make_noochie(tmp_path, ledger)


# ── advise_metrics ──────────────────────────────────────────────────────────

def test_advise_metrics_all_have_verdict_and_rationale():
    advice = advise_metrics(["visitors", "pageviews", "bounce_rate"], None)
    assert len(advice) == 3
    for item in advice:
        assert item["verdict"] in ("keep", "skip")
        assert item["rationale"]


def test_advise_metrics_known_keep():
    lookup = {a["metric"]: a for a in advise_metrics(["visitors", "pageviews"], None)}
    assert lookup["visitors"]["verdict"] == "keep"
    assert lookup["pageviews"]["verdict"] == "keep"


def test_advise_metrics_known_skip():
    lookup = {a["metric"]: a for a in advise_metrics(["bounce_rate", "visit_duration"], None)}
    assert lookup["bounce_rate"]["verdict"] == "skip"
    assert lookup["visit_duration"]["verdict"] == "skip"


def test_advise_metrics_unknown_defaults_to_skip():
    advice = advise_metrics(["onbekend_ding"], None)
    assert advice[0]["verdict"] == "skip"


def test_advise_metrics_deterministic():
    catalog = ["visitors", "pageviews", "bounce_rate"]
    assert advise_metrics(catalog, None) == advise_metrics(catalog, None)


# ── Noochie._on_discovery_ready ────────────────────────────────────────────

def _send_discovery(noochie, pid, catalog):
    event = Event("project_discovery_ready",
                  {"project_id": pid, "catalog": catalog}, "website_watcher")
    noochie._on_discovery_ready(event)


def test_advice_event_published(noochie_bus, ledger):
    noochie, bus = noochie_bus
    received = []
    bus.subscribe("project_advice_ready", received.append)
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    ledger.block(pid, "noochie")
    _send_discovery(noochie, pid, ["visitors", "pageviews"])
    assert len(received) == 1
    assert received[0].data["project_id"] == pid
    assert len(received[0].data["advice"]) == 2


def test_project_no_longer_blocked_on_noochie(noochie_bus, ledger):
    noochie, _ = noochie_bus
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    ledger.block(pid, "noochie")
    _send_discovery(noochie, pid, ["visitors"])
    assert ledger.get(pid)["blocked_on"] != "noochie"


def test_project_returned_to_owner(noochie_bus, ledger):
    noochie, _ = noochie_bus
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    ledger.block(pid, "noochie")
    _send_discovery(noochie, pid, [])
    assert ledger.get(pid)["blocked_on"] == "website_watcher"


def test_no_governance_proposal_raised(noochie_bus, ledger):
    noochie, bus = noochie_bus
    proposals = []
    bus.subscribe("proposal_raised", proposals.append)
    pid = ledger.create("website_watcher", {"kind": "discovery", "skill": "plausible_stats"}, "human")
    ledger.block(pid, "noochie")
    _send_discovery(noochie, pid, ["visitors"])
    assert proposals == []
