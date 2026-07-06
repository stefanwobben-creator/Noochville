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
    p2 = ledger.create("trends",   "b", "human")
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


# ── optionele impact-labels (hulpmiddel, geen verplichting) ──────────────────────────────────────
def test_impact_velden_default_leeg(ledger):
    """Additief: zonder opgave zijn beide velden leeg (ongelabeld)."""
    p = ledger.get(ledger.create("website_watcher", {"doel": "x"}, "clock"))
    assert p["missie_impact"] == "" and p["business_impact"] == ""


def test_impact_velden_accepteren_geldige_waarden(ledger):
    p = ledger.get(ledger.create("website_watcher", {"doel": "x"}, "clock",
                                 missie_impact="versterkt", business_impact="hoog"))
    assert p["missie_impact"] == "versterkt" and p["business_impact"] == "hoog"


def test_ongelabeld_project_mag_naar_actief(ledger):
    """Geen labeling afgedwongen: een ongelabeld project mag gewoon starten (→ running)."""
    pid = ledger.create("website_watcher", {"doel": "x"}, "clock")
    assert ledger.start(pid) is True and ledger.get(pid)["status"] == "running"


def test_ongeldige_niet_lege_waarde_wordt_geweigerd(ledger):
    with pytest.raises(ValueError):
        ledger.create("website_watcher", {"doel": "x"}, "clock", missie_impact="banaan")
    with pytest.raises(ValueError):
        ledger.create("website_watcher", {"doel": "x"}, "clock", business_impact="enorm")


def test_bestaand_record_zonder_veld_blijft_geldig(tmp_path):
    """Legacy-project zonder de nieuwe keys blijft geldig; lezers vallen terug op ''."""
    import json
    path = str(tmp_path / "projects.json")
    json.dump({"p1": {"id": "p1", "owner": "ww", "scope": {}, "trigger": "clock", "status": "queued"}},
              open(path, "w"))
    p = ProjectLedger(path).get("p1")
    assert p.get("missie_impact", "") == "" and p.get("business_impact", "") == ""


def test_effort_veld_default_leeg_en_geldig(ledger):
    p = ledger.get(ledger.create("website_watcher", {"doel": "x"}, "clock"))
    assert p["effort"] == ""                                        # optioneel, default leeg
    p2 = ledger.get(ledger.create("website_watcher", {"doel": "x"}, "clock", effort="1w"))
    assert p2["effort"] == "1w"


def test_effort_ongeldige_waarde_geweigerd(ledger):
    with pytest.raises(ValueError):
        ledger.create("website_watcher", {"doel": "x"}, "clock", effort="3d")


def test_effort_edit_zet_en_wist(ledger):
    pid = ledger.create("website_watcher", {"doel": "x"}, "clock", effort="1d")
    assert ledger.edit(pid, effort="2d") and ledger.get(pid)["effort"] == "2d"
    assert ledger.edit(pid, effort="") and ledger.get(pid)["effort"] == ""   # leegmaken
