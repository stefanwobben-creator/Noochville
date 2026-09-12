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


def test_claim_run_complete_zonder_checklist_geen_valse_done(inhabitant, ledger):
    # ACTIEF zonder voorbereiding → geen uitvoering, geen valse done, geen stub:done-marker
    pid = ledger.create("website_watcher", "schrijf vegan-pagina", "human")
    inhabitant._claim_run_complete(pid)
    p = ledger.get(pid)
    assert p["status"] != "done"
    assert p.get("outcome") != "stub:done"


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


def test_run_project_zonder_checklist_geeft_geen_stub(inhabitant, ledger):
    # de stub:done-marker is vervangen: geen checklist → run_project geeft None (geen valse success)
    pid = ledger.create("website_watcher", "werk", "human")
    assert inhabitant.run_project(ledger.get(pid)) is None


def test_een_nieuw_project_slaapt_en_de_rol_raakt_het_niet_aan(inhabitant, ledger):
    """Scope 49: er is geen `project_queued`-reactie meer. Een nieuw project staat in TOEKOMST en
    blijft daar tot een mens het naar Active sleept (`project_activated`); de dagpuls loopt alleen
    LOPEND langs. De rol heeft dus geen ingang meer om ongevraagd aan nieuw werk te beginnen."""
    assert not hasattr(inhabitant, "_on_project_queued") and not hasattr(inhabitant, "_scan_queued_projects")
    pid = ledger.create("website_watcher", "werk", "human")
    assert ledger.get(pid)["status"] == "future"
    inhabitant._tend_projects(None)
    assert ledger.get(pid)["status"] == "future" and not ledger.get(pid).get("worked")


def test_on_project_activated_zonder_checklist_geen_valse_done(inhabitant, ledger):
    # correcte eigenaar, maar geen voorbereiding → geen valse done (niet meer de oude stub:done-flow)
    pid = ledger.create("website_watcher", "werk", "human", status="running")
    event = Event("project_activated", {"pid": pid, "owner": "website_watcher"}, "village")
    inhabitant._on_project_activated(event)
    assert ledger.get(pid)["status"] != "done"
