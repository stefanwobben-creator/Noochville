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
                                     "cadence": ["week"], "doel": ["all"], "next": ["/"]})
    assert cockpit2._Stores(dd).checklists.for_node(C) == []
    # mét de poort wel
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Facturen verstuurd"],
                                     "cadence": ["week"], "doel": ["all"], "bestaand": ["1"], "next": ["/"]})
    items = cockpit2._Stores(dd).checklists.for_node(C)
    assert len(items) == 1 and items[0]["description"] == "Facturen verstuurd"


def test_doel_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Code gereviewd"], "cadence": ["week"],
                                     "doel": [f"role:{RID}"], "bestaand": ["1"], "next": ["/"]})
    it = cockpit2._Stores(dd).checklists.for_node(C)[0]
    assert it["target_type"] == "role" and it["target_id"] == RID


def test_tab_render_groepen_en_filter(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Dagcheck"], "cadence": ["dag"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]})
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Weekcheck"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "checklists", csrf_token="t")
    assert "Dagelijks" in page and "Wekelijks" in page          # groepering per cadans
    assert "Nu te doen" in page and "cl_report" in page          # filter + rapporteer-knoppen
    assert "bestaande" in page                                   # governance-poort in het formulier
    assert "visibility" not in page.lower() and "(optional)" not in page.lower()


def test_rapporteren_due_en_aandacht(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [C], "description": ["Weekcheck"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]})
    cid = cockpit2._Stores(dd).checklists.for_node(C)[0]["id"]
    # ✗ rapporteren -> niet meer 'due', wel in 'Aandacht nodig'
    cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["0"], "next": ["/"]})
    due = cockpit2.render_node(cockpit2._Stores(dd), C, "checklists", csrf_token="t", clf="due")
    assert "Aandacht nodig" in due and "Weekcheck" in due
    # onder 'Nu te doen' staat het niet meer in de gewone groepen (al gerapporteerd)
    assert "🎉" in due or due.count("Weekcheck") == 1          # alleen in de aandacht-sectie
    # ✓ rapporteren haalt het uit de aandacht
    cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "checklists", csrf_token="t", clf="all")
    assert "Aandacht nodig" not in page


def test_checklist_op_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "cl_add", {"node": [RID], "description": ["PRs gereviewd"], "cadence": ["week"],
                                     "doel": ["all"], "bestaand": ["1"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), RID, "checklists", csrf_token="t")
    assert "PRs gereviewd" in page and "Checklists" in page
