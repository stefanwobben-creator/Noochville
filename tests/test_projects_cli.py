"""Tests voor projects_cli.human_create — thread-vrij, tmp_path, geen bus."""
from __future__ import annotations
import pytest
from nooch_village.projects import ProjectLedger
from nooch_village.projects_cli import human_create


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def test_human_create_queued(ledger):
    pid = human_create(ledger, "analyst", "schrijf vegan-pagina")
    p = ledger.get(pid)
    assert p is not None
    assert p["status"]  == "queued"
    assert p["owner"]   == "analyst"
    assert p["scope"]   == "schrijf vegan-pagina"
    assert p["trigger"] == "human"


def test_human_create_returns_id(ledger):
    pid = human_create(ledger, "scout", "analyseer zoekwoorden")
    assert isinstance(pid, str) and len(pid) == 12


def test_open_bevat_vers_project(ledger):
    pid = human_create(ledger, "scout", "analyseer zoekwoorden")
    assert any(p["id"] == pid for p in ledger.open())


def test_open_niet_na_complete(ledger):
    pid = human_create(ledger, "analyst", "werk")
    ledger.complete(pid)
    assert not any(p["id"] == pid for p in ledger.open())
