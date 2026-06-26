"""Stuur-opmerkingen per project: de mens stuurt bij, de eigenaar-rol leest ze mee bij het werken,
en het project wordt opnieuw opgepakt."""
from __future__ import annotations
import os
import tempfile

from nooch_village.projects import ProjectLedger
from nooch_village.project_worker import work_projects, work_one
from nooch_village import cockpit


def test_add_comment_en_herpak():
    led = ProjectLedger(os.path.join(tempfile.mkdtemp(), "p.json"))
    pid = led.create("harry_hemp", "Zoek elastaan-vervanger", "human")
    led.record_progress(pid, "ronde 1")           # zet 'worked' = True
    assert led.get(pid)["worked"] is True
    assert led.add_comment(pid, "richt je op technisch onderzoek naar een natuurlijke elastaan-vervanger")
    p = led.get(pid)
    assert p["comments"][0]["text"].startswith("richt je op technisch")
    assert p["worked"] is False                    # nieuwe sturing → opnieuw oppakken
    assert led.add_comment(pid, "   ") is False     # lege opmerking telt niet


def test_steer_komt_in_de_prompt():
    led = ProjectLedger(os.path.join(tempfile.mkdtemp(), "p.json"))
    pid = led.create("harry_hemp", "Zoek elastaan-vervanger", "human")
    led.add_comment(pid, "focus op natuurlijke elastaan-vervanger")
    seen = {}
    work_projects(led, llm_reason=lambda pr: (seen.__setitem__("p", pr) or "LEVER: ok"))
    assert "STURING" in seen["p"] and "elastaan-vervanger" in seen["p"]


def test_work_one_zonder_steer_geen_sturingsregel():
    seen = {}
    work_one("doe iets", "scout", "p", llm_reason=lambda pr: (seen.__setitem__("p", pr) or "LEVER: ok"))
    assert "STURING" not in seen["p"]


def test_cockpit_proj_comment_dispatch(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    led = ProjectLedger(str(data / "projects.json"))
    pid = led.create("harry_hemp", "Zoek elastaan-vervanger", "human")
    res = cockpit._dispatch_action(str(data), "proj_comment", pid, "",
                                   extra={"comment": "stuur naar technisch onderzoek"})
    assert res["ok"] and res.get("proj_comment")
    assert ProjectLedger(str(data / "projects.json")).get(pid)["comments"][0]["text"] \
        == "stuur naar technisch onderzoek"
    # lege opmerking → nette fout
    assert cockpit._dispatch_action(str(data), "proj_comment", pid, "", extra={"comment": ""})["ok"] is False


def test_render_project_edit_toont_comment_en_done_uitleg():
    p = {"id": "p1", "owner": "harry_hemp", "scope": "Zoek X", "status": "running",
         "comments": [{"text": "focus op elastaan", "at": 1}]}
    page = cockpit.render_project_edit(p, [{"id": "harry_hemp", "type": "role", "archived": False}], "t")
    assert "Bijsturen" in page and "focus op elastaan" in page
    assert 'value="proj_comment"' in page
    assert "een rol sluit zichzelf nooit af" in page.lower()
