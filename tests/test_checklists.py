"""Checklists: store (cadans/periode/due/historie) + tab/dispatch (rapporteren, governance-poort)."""
from __future__ import annotations
from datetime import datetime, timezone

from nooch_village import cockpit2
from nooch_village.checklists import ChecklistStore, period_key

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_period_key_per_cadans():
    now = datetime(2026, 6, 28, tzinfo=timezone.utc)
    assert period_key("dag", now) == "2026-06-28"
    assert period_key("maand", now) == "2026-06"
    assert period_key("kwartaal", now) == "2026-Q2"
    assert period_key("week", now).startswith("2026-W")


def test_store_due_en_historie(tmp_path):
    st = ChecklistStore(str(tmp_path / "cl.json"))
    it = st.add(C, "Facturen verstuurd", "week", by="sw")
    assert it and ChecklistStore.is_due(it)              # nog niet gerapporteerd -> due
    st.report(it["id"], True, by="sw")
    it = st.get(it["id"])
    assert not ChecklistStore.is_due(it) and ChecklistStore.current_status(it) is True
    # historie: injecteer een paar oude periodes
    it["reports"]["2026-W01"] = {"ok": True, "at": 1, "by": "x"}
    it["reports"]["2026-W02"] = {"ok": False, "at": 2, "by": "x"}
    assert ChecklistStore.history(it, 6)[:2] == [True, False]


def test_governance_poort_blokkeert_zonder_bestaand(tmp_path):
    dd = _dd(tmp_path)
    # zonder de 'bestaande actie'-checkbox wordt niets toegevoegd
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Iets nieuws"],
                                     "cadence": ["week"], "doel": ["all"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).checklists.for_node(C) == []
    # mét de poort wel
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Facturen verstuurd"],
                                     "cadence": ["week"], "doel": ["all"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    items = cockpit2._Stores(dd).checklists.for_node(C)
    assert len(items) == 1 and items[0]["description"] == "Facturen verstuurd"


def test_doel_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Code gereviewd"], "cadence": ["week"],
                                     "doel": [f"role:{RID}"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    it = cockpit2._Stores(dd).checklists.for_node(C)[0]
    assert it["target_type"] == "role" and it["target_id"] == RID


def test_tab_render_groepen_geen_filter(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Dagcheck"], "cadence": ["dag"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Weekcheck"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "checklists", csrf_token="t")
    assert "Dagelijks" in page and "Wekelijks" in page          # groepering per cadans
    assert "cl_report" in page                                   # rapporteer-knoppen
    # U4: geen filter-toggle meer; te-doen items worden gehighlight met .cl-todo
    assert "Nu te doen" not in page and "class='cl-filter" not in page
    assert "cl-row cl-todo" in page                              # twee due items -> highlight aanwezig
    assert "bestaande" in page                                   # governance-poort in het formulier
    assert "visibility" not in page.lower() and "(optional)" not in page.lower()


def test_rapporteren_due_en_aandacht(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Weekcheck"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    cid = cockpit2._Stores(dd).checklists.for_node(C)[0]["id"]
    # ✗ rapporteren -> gemist: geen bubble meer; de rij in zijn cadans-groep krijgt .cl-attn (coral)
    cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["0"], "next": ["/"]}, username="guest")
    due = cockpit2.render_node(cockpit2._Stores(dd), C, "checklists", csrf_token="t")
    assert "Aandacht nodig" not in due                  # bubble vervallen
    assert due.count("Weekcheck") == 1                  # eenmaal, in zijn cadans-groep
    assert "cl-row cl-attn" in due                      # gemist -> coral op rij-niveau
    # ✓ rapporteren -> gedaan: neutraal, geen rij-markering meer
    cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "checklists", csrf_token="t")
    assert "cl-row cl-attn" not in page and "cl-row cl-todo" not in page


def test_checklist_op_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [RID], "description": ["PRs gereviewd"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), RID, "checklists", csrf_token="t")
    assert "PRs gereviewd" in page and "Checklists" in page
