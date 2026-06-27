"""Roloverleg in cockpit 2 — brok 1: modal-frame + agenda links."""
from __future__ import annotations

from nooch_village import cockpit2

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_meeting_knop_op_cirkel(tmp_path):
    dd = _dd(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert f"/roloverleg2?circle={C}" in node and "Governance meeting" in node
    # een rol heeft geen meeting-knop
    role = cockpit2.render_node(cockpit2._Stores(dd), RID, "overview", csrf_token="t")
    assert "roloverleg2" not in role


def test_agendapunt_bestaande_rol_en_nieuwe_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Data Analist"], "next": ["/"]})
    items = cockpit2._Stores(dd).agenda.open()
    kinds = {it["kind"] for it in items}
    assert kinds == {"amend_role", "add_role"} and len(items) == 2
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Website Developer" in frag and "Data Analist" in frag and "Agenda" in frag


def test_editor_prefil_en_change_diff(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    # editor prefilt de huidige rol
    assert "rov-editor" in frag and "Rolnaam" in frag and "Building new features" in frag
    # naam wijzigen -> rename in change; accountability toevoegen -> add_accountabilities
    cockpit2.dispatch(dd, "rov2_set", {"iid": [iid], "field": ["name"], "value": ["Web Developer"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van performance"], "next": ["/"]})
    ch = cockpit2._Stores(dd).agenda.get(iid)["change"]
    assert ch.get("rename") == "Web Developer"
    assert "Bewaken van performance" in ch.get("add_accountabilities", [])
    # bestaande accountability verwijderen -> remove_accountabilities
    cockpit2.dispatch(dd, "rov2_acc_remove", {"iid": [iid], "idx": ["0"], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.get(iid)["change"].get("remove_accountabilities")


def test_editor_nieuwe_rol(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Data Analist"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_set", {"iid": [iid], "field": ["purpose"], "value": ["Inzicht uit data"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Rapporteren van trends"], "next": ["/"]})
    ch = cockpit2._Stores(dd).agenda.get(iid)["change"]
    assert ch.get("purpose") == "Inzicht uit data" and "Rapporteren van trends" in ch.get("add_accountabilities", [])


def test_layout_toevoegen_boven_en_groene_knop(tmp_path):
    dd = _dd(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert "btn ok js-modal" in node                      # groene meeting-knop
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Welke spanning" not in frag                    # spanning-veld weg
    assert frag.find("rov-add") < frag.find("rov-list")    # toevoegen boven de lijst
    assert "rov-grid" in frag and "rov-foot" in frag and "Vergadering sluiten" in frag


def test_sluiten_voert_consented_door(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    cockpit2.dispatch(dd, "rov2_acc_add", {"iid": [iid], "text": ["Bewaken van performance"], "next": ["/"]})
    cockpit2._Stores(dd).agenda.set_status(iid, "consented")
    cockpit2.dispatch(dd, "rov2_end", {"circle": [C], "next": ["/node?id=" + C]})
    # doorgevoerd in de records + van de agenda af
    rec = cockpit2._Stores(dd).records.get(RID)
    assert "Bewaken van performance" in rec.definition.accountabilities
    assert cockpit2._Stores(dd).agenda.all() == []


def test_select_en_verwijderen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "naam": ["Website Developer"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    sel = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "rov-item on" in sel and "Voorstel" in sel
    cockpit2.dispatch(dd, "rov2_remove", {"iid": [iid], "circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.open() == []
