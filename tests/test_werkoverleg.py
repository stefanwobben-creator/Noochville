"""Werkoverleg brok 1: store + modalframe (secretaris-gated) + hergebruik bestaande schermen."""
from __future__ import annotations

from nooch_village import cockpit2

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_store_open_close(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    assert not st.werk.is_open(C)
    st.werk.open(C)
    assert cockpit2._Stores(dd).werk.is_open(C)
    cockpit2._Stores(dd).werk.close(C)
    assert not cockpit2._Stores(dd).werk.is_open(C)


def test_startscherm_secretaris_gate(tmp_path):
    dd = _dd(tmp_path)
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, csrf_token="t", fragment=True)
    assert "Werkoverleg" in frag and "Alleen de secretaris" in frag and "wo_open" in frag
    assert "wo-step" not in frag                      # nog niet gestart -> geen stappen


def test_knop_op_cirkel_en_niet_op_rol(tmp_path):
    dd = _dd(tmp_path)
    node = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    assert "/werkoverleg?circle=" in node and "Tactical meeting" in node
    role = cockpit2.render_node(cockpit2._Stores(dd), RID, "overview", csrf_token="t")
    assert "werkoverleg" not in role


def test_open_toont_stappen_en_checkin_members(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "checkin", csrf_token="t", fragment=True)
    # vaste volgorde van 7 stappen
    for lbl in ("Check-in", "Checklist", "Metrics", "Projecten", "Agenda", "Check-out", "Sluiten"):
        assert lbl in frag
    assert "wo-step on" in frag and "Sluit overleg" in frag
    assert "Members" in frag                          # check-in = hergebruik members-scherm


def test_stappen_hergebruiken_bestaande_schermen(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    st = cockpit2._Stores(dd)
    cl = cockpit2.render_werkoverleg(st, C, "checklist", csrf_token="t", fragment=True)
    assert "Checklists" in cl and "+ Checklist-item" in cl          # echte checklist-scherm
    me = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "metrics", csrf_token="t", fragment=True)
    assert "+ Tegel" in me and "Periode:" in me                     # echte metrics-scherm
    pr = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "projecten", csrf_token="t", fragment=True)
    assert "proj" in pr.lower()                                     # echte projecten-scherm


def test_sluiten(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]})
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]})
    assert not cockpit2._Stores(dd).werk.is_open(C)
