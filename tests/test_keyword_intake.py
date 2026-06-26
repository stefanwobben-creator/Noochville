"""Keyword-intake-brug: zoekwoorden uit een rol-oplevering (project-gesprek) door de Librarian-
review laten lopen → ze landen echt in de bibliotheek en worden zichtbaar ter review."""
from __future__ import annotations
import json

from nooch_village.keyword_intake import extract_candidates, review_words
from nooch_village import cockpit
from nooch_village.projects import ProjectLedger


def test_extract_candidates():
    txt = ("**Kwaliteit & Duurzaamheid**\n"
           "- vegan sneakers zonder leer\n"
           "- sneakers gemaakt van gerecyclede materialen (eerste selectie)\n"
           "1) duurzame hardloopschoenen\n"
           "**Een kopje dat geen woord is:**\n"
           "- te lange zin met veel te veel woorden die geen zoekwoord meer is echt niet nee\n")
    c = extract_candidates(txt)
    assert "vegan sneakers zonder leer" in c
    assert "sneakers gemaakt van gerecyclede materialen" in c     # parenthetical gestript
    assert "duurzame hardloopschoenen" in c
    assert not any(len(t.split()) > 8 for t in c)                 # te lange regel eruit


def test_review_words_curateert_library(tmp_path):
    (tmp_path / "library.json").write_text("{}", encoding="utf-8")
    res = review_words(["duurzame sneakers", "vegan schoenen"], str(tmp_path))
    assert res["reviewed"] == 2
    lib = json.load(open(tmp_path / "library.json"))
    assert set(lib) == {"duurzame sneakers", "vegan schoenen"}
    assert all(v["status"] in ("approved", "forbidden", "escalated") for v in lib.values())


def test_kw_offer_vanuit_project_naar_library(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    (data / "library.json").write_text("{}", encoding="utf-8")
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    led = ProjectLedger(str(data / "projects.json"))
    pid = led.create("librarian", "keywordlist beoordelen", "human")
    led.add_role_message(pid, "**Lijst**\n- duurzame hardloopschoenen\n- vegan sneakers zonder leer")
    res = cockpit._dispatch_action(str(data), "kw_offer", pid, "", extra={})
    assert res["ok"] and res["kw_offer"]["reviewed"] == 2
    lib = json.load(open(data / "library.json"))
    assert "duurzame hardloopschoenen" in lib                     # echt in de bibliotheek
    # en het verzoek staat in het projectgesprek
    assert any("aan de Librarian aangeboden" in m["text"]
               for m in ProjectLedger(str(data / "projects.json")).get(pid)["log"])
    # lege oplevering → nette fout
    pid2 = led.create("librarian", "leeg", "human")
    assert cockpit._dispatch_action(str(data), "kw_offer", pid2, "", extra={})["ok"] is False
