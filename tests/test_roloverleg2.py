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
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "owner": [RID], "reason": ["mist iets"], "next": ["/"]})
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "owner": ["__new__"],
                                       "rolnaam": ["Data Analist"], "reason": ["meten"], "next": ["/"]})
    items = cockpit2._Stores(dd).agenda.open()
    kinds = {it["kind"] for it in items}
    assert kinds == {"amend_role", "add_role"} and len(items) == 2
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Website Developer" in frag and "Data Analist" in frag and "Agenda" in frag


def test_select_en_verwijderen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "rov2_add", {"circle": [C], "owner": [RID], "reason": ["x"], "next": ["/"]})
    iid = cockpit2._Stores(dd).agenda.open()[0]["id"]
    sel = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, iid=iid, csrf_token="t", fragment=True)
    assert "rov-item on" in sel and "Voorstel" in sel
    cockpit2.dispatch(dd, "rov2_remove", {"iid": [iid], "circle": [C], "next": ["/"]})
    assert cockpit2._Stores(dd).agenda.open() == []
