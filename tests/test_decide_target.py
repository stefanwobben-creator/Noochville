"""Triage-prototype: doelwit-woorden krijgen dezelfde ja/nee-met-reden-flow.
✓ → content-project (projectbord); ✗ → laten vallen met reden (forbidden)."""
from __future__ import annotations

from nooch_village.library import Library
from nooch_village.projects import ProjectLedger
from nooch_village.inbox_actions import decide_target


def _setup(tmp_path):
    lib = Library(str(tmp_path / "library.json"))
    lib.curate("vegan sneakers dames", "approved", by="librarian")
    lib.set_function("vegan sneakers dames", "doelwit")
    projects = ProjectLedger(str(tmp_path / "projects.json"))
    return lib, projects


def test_ja_maakt_content_project(tmp_path):
    lib, projects = _setup(tmp_path)
    res = decide_target(lib, projects, "vegan sneakers dames", "project")
    assert res["ok"]
    ps = projects.all()
    assert len(ps) == 1 and "vegan sneakers dames" in ps[0]["scope"]
    assert ps[0]["owner"] == "librarian"
    # woord blijft een doelwit (niet verboden)
    assert lib.status("vegan sneakers dames")["status"] == "approved"
    # dedup: nog een keer → geen tweede project
    decide_target(lib, projects, "vegan sneakers dames", "project")
    assert len(projects.all()) == 1


def test_nee_laat_vallen_met_reden(tmp_path):
    lib, projects = _setup(tmp_path)
    res = decide_target(lib, projects, "vegan sneakers dames", "drop",
                        reason="te breed, past niet bij onze niche")
    assert res["ok"] and res["status"] == "forbidden"
    e = lib.status("vegan sneakers dames")
    assert e["status"] == "forbidden" and "te breed" in e["rationale"]
    assert projects.all() == []


def test_onbekend_woord_faalt(tmp_path):
    lib, projects = _setup(tmp_path)
    assert decide_target(lib, projects, "bestaatniet", "project")["ok"] is False
