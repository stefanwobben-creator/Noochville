"""Metrieken 2 — deel 1: de catalogus rendert en favoriet/unfavoriet zet een tegel op de node."""
from __future__ import annotations

from nooch_village import cockpit2

_NODE = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_catalogus_rendert_met_leesbare_labels(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    rec = st.records.get(_NODE)
    html = cockpit2.render_metrics2(st, rec, csrf_token="t")
    assert "Catalogus" in html and "Mijn dashboard" in html
    assert "Websitebezoekers" in html and "Bezoekers" in html      # leesbaar label, niet technisch
    assert "metrics2_fav" in html                                  # favoriet-knop
    assert "Nog niks op je dashboard" in html                      # leeg dashboard-startstaat


def test_favoriet_zet_tegel_op_node_en_toont_op_dashboard(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["pulse_visitors"], "measure": ["visitors"],
                       "dim": ["time"], "form": ["trend"], "next": [f"/metrics2?node={_NODE}"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    tiles = st2.metrics.tiles_of(_NODE)
    assert any(t["source"] == "pulse_visitors" and t["measure"] == "visitors" for t in tiles)
    html = cockpit2.render_metrics2(st2, st2.records.get(_NODE), csrf_token="t")
    assert "Nog niks op je dashboard" not in html and "★ favoriet" in html   # nu gemarkeerd als favoriet


def test_unfavoriet_haalt_tegel_weg(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["pulse_visitors"], "measure": ["visitors"],
                       "dim": ["time"], "form": ["trend"], "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    tid = st2.metrics.tiles_of(_NODE)[0]["id"]
    cockpit2.dispatch(dd, "metrics2_unfav", {"node": [_NODE], "tid": [tid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).metrics.tiles_of(_NODE) == []
