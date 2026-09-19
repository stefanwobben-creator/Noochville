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










def test_een_nieuw_project_slaapt_en_de_rol_raakt_het_niet_aan(inhabitant, ledger):
    """Scope 49: er is geen `project_queued`-reactie meer. Een nieuw project staat in TOEKOMST en
    blijft daar tot een mens het naar Active sleept (`project_activated`); de dagpuls loopt alleen
    LOPEND langs. De rol heeft dus geen ingang meer om ongevraagd aan nieuw werk te beginnen."""
    assert not hasattr(inhabitant, "_on_project_queued") and not hasattr(inhabitant, "_scan_queued_projects")
    pid = ledger.create("website_watcher", "werk", "human")
    assert ledger.get(pid)["status"] == "future"
    inhabitant._tend_projects(None)
    assert ledger.get(pid)["status"] == "future" and not ledger.get(pid).get("worked")


