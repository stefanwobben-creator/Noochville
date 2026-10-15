"""Checklist-items zonder AI-restanten (besluit Stefan, 15 oktober 2026).

De AI-uitvoerder voor checklist-items bestaat sinds #516 (19-20 september 2026) niet meer. Alles
wat hem beloofde of voorbereidde is weg: het skill-aanbod ("can pick this up") met zijn LLM-call,
het accepteren, de hand-off naar een rol, "no skill · needs a human", de akkoord-poort ("go ahead",
"the role is working — N to go") en de uitvoerlijst-keuze ("the role works this list"). Een item is
een tekstregel met een vinkje. De `skill`- en `payload`-velden op oude items blijven in de opslag.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2

WEG_IN_HTML = ("can pick this up", "picked up by the role", "no skill", "needs a human", "hand off",
               "the role is working", "the role works this list", "the role doesn't work this list",
               "go ahead", "waiting for your go-ahead", "make this the role's list",
               "check_accept", "check_handoff", "plan_akkoord", "checklist_uitvoer",
               "data-bezig", "ck-skill", "ck-payload", "ck-gate", "ck-noskill", "ck-warn", "ck-leeg")


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create("mother_earth__nooch__website_developer", "Permalinks", "human",
                             status="running")
    cl = st.projects.checklist_add(pid, title="tasks", akkoord=False)
    st.projects.check_add(pid, cl["id"], "GS1 masterdata uitzoeken", skill="web_zoek",
                          payload={"term": "GS1 masterdata", "aantal": 8, "lees": 5})
    st.projects.check_add(pid, cl["id"], "Shopify leading maken")
    st.projects.check_add(pid, cl["id"], "Onvolledig", skill="competitor_news", payload_ok=False)
    tweede = st.projects.checklist_add(pid, title="Andere lijst")
    st.projects.check_add(pid, tweede["id"], "Nog iets", skill="haal_pagina")
    # een oud aanbod en een oud leeg-resultaat in de opslag
    p = st.projects._projects[pid]
    p["checklists"][0]["items"][1]["offer"] = {"skill": "web_zoek", "payload": {}, "payload_ok": True}
    p["checklists"][1]["items"][0].update(done=True, leeg=True, leeg_bron="gemeld", leeg_reden="niets")
    st.projects._save()
    return dd, pid


def test_een_item_is_een_tekstregel_met_een_vinkje(dorp):
    dd, pid = dorp
    html = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t")
    for tekst in ("GS1 masterdata uitzoeken", "Shopify leading maken", "Onvolledig", "Nog iets"):
        assert tekst in html
    for weg in WEG_IN_HTML:
        assert weg not in html, weg
    assert html.count("value='check_toggle'") == 4
    # de opslag blijft zoals hij was: skill en payload staan er nog
    it = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]
    assert it["skill"] == "web_zoek" and it["payload"]["aantal"] == 8


@pytest.mark.parametrize("actie", ["check_accept", "check_handoff", "plan_akkoord", "checklist_uitvoer"])
def test_de_acties_bestaan_niet_meer(actie):
    assert actie not in cockpit2.ACTIONS


def test_een_item_toevoegen_vraagt_geen_model_meer(dorp, monkeypatch):
    dd, pid = dorp
    from nooch_village import llm

    def _nooit(*a, **k):
        raise AssertionError("check_add mag geen LLM meer aanroepen")
    monkeypatch.setattr(llm, "reason", _nooit)
    clid = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["id"]
    _n, msg = cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["Nieuw"],
                                                  "next": ["/"]}, username="guest")
    assert msg == "✓ item added"
    it = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][-1]
    assert it["text"] == "Nieuw" and "offer" not in it


def test_de_kaart_volgt_niets_meer():
    import inspect
    from nooch_village.views import projects as P
    bron = inspect.getsource(P)
    assert "volgStart" not in bron and "[data-bezig]" not in bron
    assert not hasattr(cockpit2, "_offer_skill") and not hasattr(cockpit2, "_act_check_handoff")


def test_human_task_label_en_uitzondering_zijn_weg(dorp):
    """15 oktober 2026: "Human task — does not count towards done" klopt niet meer nu elk item
    mensenwerk is. Geen label, en het item telt mee in de voortgangsbalk."""
    dd, pid = dorp
    st = cockpit2._Stores(dd)
    p = st.projects._projects[pid]
    p["checklists"][0]["items"][1].update(human_task=True, reason="needs a factory visit")
    st.projects._save()
    html = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t")
    assert "human task" not in html.lower() and "does not count towards done" not in html
    assert "b-human" not in html and "ck-human" not in html
    # 3 open items in de eerste lijst, ook het item met de oude vlag
    assert "0% (0/3)" in html
