"""Tests voor ProjectLedger — thread-vrij, tmp_path, geen bus."""
from __future__ import annotations
import pytest
from nooch_village.projects import ProjectLedger


@pytest.fixture
def ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def test_create_returns_id_and_queued(ledger):
    pid = ledger.create("website_watcher", {"doel": "vegan-pagina"}, "clock")
    p = ledger.get(pid)
    assert p is not None
    assert p["id"] == pid
    assert p["owner"] == "website_watcher"
    assert p["scope"] == {"doel": "vegan-pagina"}
    assert p["trigger"] == "clock"
    assert p["status"] == "queued"
    assert p["blocked_on"] is None
    assert p["outcome"] is None


def test_lifecycle(ledger):
    pid = ledger.create("website_watcher", "schrijf pagina", "human")

    assert ledger.start(pid) is True
    assert ledger.get(pid)["status"] == "running"

    assert ledger.block(pid, "noochie") is True
    p = ledger.get(pid)
    assert p["status"] == "blocked"
    assert p["blocked_on"] == "noochie"

    assert ledger.unblock(pid) is True
    p = ledger.get(pid)
    assert p["status"] == "running"
    assert p["blocked_on"] is None

    assert ledger.complete(pid, "prop_123") is True
    p = ledger.get(pid)
    assert p["status"] == "done"
    assert p["outcome"] == "prop_123"


def test_open_excludes_done(ledger):
    pid = ledger.create("website_watcher", "werk", "tension")
    assert any(p["id"] == pid for p in ledger.open())

    ledger.complete(pid)
    assert not any(p["id"] == pid for p in ledger.open())


def test_complete_done_is_noop(ledger):
    pid = ledger.create("website_watcher", "werk", "clock")
    ledger.complete(pid, "prop_1")

    result = ledger.complete(pid, "prop_2")
    assert result is False
    assert ledger.get(pid)["outcome"] == "prop_1"


def test_by_status(ledger):
    p1 = ledger.create("website_watcher", "a", "clock")
    p2 = ledger.create("scout",   "b", "human")
    ledger.start(p1)
    assert any(p["id"] == p1 for p in ledger.by_status("running"))
    assert any(p["id"] == p2 for p in ledger.by_status("queued"))


def test_invalid_trigger_raises(ledger):
    with pytest.raises(ValueError):
        ledger.create("website_watcher", "werk", "onbekend")


def test_mutate_nonexistent_returns_false(ledger):
    assert ledger.start("bestaat-niet") is False
    assert ledger.block("bestaat-niet", "x") is False
    assert ledger.complete("bestaat-niet") is False
