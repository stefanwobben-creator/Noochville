"""Loop-integratietest: discovery-keten zonder netwerk-latency.

Runt analyst + Noochie op echte threads met gemockte skills.
Verifieert de volledige keten:
  queued → (analyst) running → blocked(noochie) → (Noochie adviseert)
  → blocked(analyst) → (analyst verwerkt advies) → done.
"""
from __future__ import annotations
import time
import pytest
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.roles import WebsiteWatcherWorker, Noochie
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.projects import ProjectLedger
from nooch_village.monitoring import MonitoringStore

_FAKE_PLAUSIBLE = {"results": {"visitors": {"value": 42}, "pageviews": {"value": 88}}}
_FAKE_TRENDS    = {"keywords": {}, "related": []}
_FAKE_NOTE      = {"path": None, "tension": False, "reason": ""}
_TIMEOUT        = 20  # seconden max


def _record(role_id, skills=None):
    return Record(
        id=role_id,
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="test",
            accountabilities=[],
            domains=[],
            skills=skills or [],
        ),
        source="seed",
    )


@pytest.fixture()
def loop_setup(tmp_path):
    bus      = EventBus(name="loop-test")
    registry = SkillRegistry()
    for skill in (PlausibleSkill(), TrendsSkill(), FieldNoteSkill()):
        registry.register(skill)

    ledger     = ProjectLedger(str(tmp_path / "projects.json"))
    monitoring = MonitoringStore(str(tmp_path / "role_metrics.json"))

    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=ledger,
        records=None,
        observations=None,
        monitoring=monitoring,
        library=None,
        strategy={},
    )

    analyst = WebsiteWatcherWorker(
        _record("website_watcher", ["plausible_stats", "google_trends", "field_note"]),
        bus, registry, context,
    )
    noochie = Noochie(
        _record("noochie"),
        bus, registry, context,
    )

    return SimpleNamespace(
        bus=bus, ledger=ledger, monitoring=monitoring,
        analyst=analyst, noochie=noochie,
    )


def test_discovery_loop(loop_setup):
    s = loop_setup

    with (
        patch.object(PlausibleSkill, "run", return_value=_FAKE_PLAUSIBLE),
        patch.object(TrendsSkill,    "run", return_value=_FAKE_TRENDS),
        patch.object(FieldNoteSkill, "run", return_value=_FAKE_NOTE),
        patch("nooch_village.llm.reason", return_value=None),
    ):
        s.analyst.start()
        s.noochie.start()
        try:
            pid = s.ledger.create(
                "website_watcher",
                {"kind": "discovery", "skill": "plausible_stats"},
                "human",
            )
            s.bus.publish(Event("dag_begint", {"label": "test"}, "test"))

            deadline = time.time() + _TIMEOUT
            while time.time() < deadline:
                p = s.ledger.get(pid)
                if p and p["status"] == "done":
                    break
                time.sleep(0.05)
        finally:
            s.analyst.stop()
            s.noochie.stop()
            s.analyst.join(timeout=5)
            s.noochie.join(timeout=5)

    p = s.ledger.get(pid)
    assert p is not None
    assert p["status"] == "done", f"Verwacht 'done', got '{p['status']}'"
    assert p["outcome"] and "monitoring" in p["outcome"]

    metrics = s.monitoring.get_metrics("website_watcher")
    assert len(metrics) > 0, "Geen metrics in monitoring na discovery"
    assert any(m in metrics for m in ("visitors", "pageviews"))
