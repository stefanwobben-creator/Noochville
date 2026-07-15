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
    assert "Nog niks op je dashboard" not in html
    assert "class='star on'" in html and "metrics2_unfav" in html   # gevuld sterretje = favoriet


def test_unfavoriet_haalt_tegel_weg(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["pulse_visitors"], "measure": ["visitors"],
                       "dim": ["time"], "form": ["trend"], "next": ["/"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    tid = st2.metrics.tiles_of(_NODE)[0]["id"]
    cockpit2.dispatch(dd, "metrics2_unfav", {"node": [_NODE], "tid": [tid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).metrics.tiles_of(_NODE) == []


# ── deel 2: echte tegels + tijdvenster + vergelijken + weergave-schakelaar ──────

def test_favoriet_wordt_echte_tegel_met_venster_en_vergelijken(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["pulse_visitors"], "measure": ["visitors"],
                       "dim": ["time"], "form": ["trend"], "next": [f"/metrics2?node={_NODE}"]},
                      username="guest")
    st = cockpit2._Stores(dd)
    html = cockpit2.render_metrics2(st, st.records.get(_NODE), csrf_token="t", win="28d", compare=True)
    assert "class='tile'" in html                          # de favoriet rendert als grafiek-tegel
    assert "tile-wrap" in html and "tile-foot" in html     # met eigen bediening eronder
    assert "Vergelijk" in html and "Periode" in html       # tijdvenster + vergelijk-schakelaar
    assert "28 dagen" in html                              # actieve periode zichtbaar
    assert "js-flip" in html                               # kaart-omdraaien (ⓘ → definitie/bron)


def test_weergave_schakelaar_wisselt_de_vorm(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["pulse_visitors"], "measure": ["visitors"],
                       "dim": ["time"], "form": ["trend"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    tid = st.metrics.tiles_of(_NODE)[0]["id"]
    html = cockpit2.render_metrics2(st, st.records.get(_NODE), csrf_token="t")
    assert "metrics2_form" in html and "Staaf" in html     # reeks → trend/staaf/getal kiesbaar
    cockpit2.dispatch(dd, "metrics2_form",
                      {"node": [_NODE], "tid": [tid], "form": ["staaf"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).metrics.tiles_of(_NODE)[0]["form"] == "staaf"


def test_moment_tegel_heeft_geen_weergave_keuze(tmp_path):
    dd = _dd(tmp_path)
    # 'laatste waarde' (dim none) is een moment → alleen 'getal', dus geen weergave-dropdown.
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["shopify"], "measure": ["pairs_sold"],
                       "dim": ["none"], "form": ["getal"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    from nooch_village.views import metrics2
    assert metrics2._weergave_menu(_NODE, st.metrics.tiles_of(_NODE)[0], "t") == ""


# ── deel 3: segmentatie ────────────────────────────────────────────────────────

def test_segment_schakelaar_wisselt_de_dimensie(tmp_path):
    dd = _dd(tmp_path)
    # shopify heeft meerdere dims (totaal/over tijd/per land/per product) → segment-schakelaar zichtbaar.
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["shopify"], "measure": ["pairs_sold"],
                       "dim": ["none"], "form": ["getal"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    tid = st.metrics.tiles_of(_NODE)[0]["id"]
    html = cockpit2.render_metrics2(st, st.records.get(_NODE), csrf_token="t")
    assert "metrics2_dim" in html and "per land" in html and "per product" in html
    cockpit2.dispatch(dd, "metrics2_dim",
                      {"node": [_NODE], "tid": [tid], "dim": ["country"], "form": ["horizontaal"],
                       "next": ["/"]}, username="guest")
    t2 = cockpit2._Stores(dd).metrics.tiles_of(_NODE)[0]
    assert t2["dim"] == "country" and t2["form"] == "horizontaal"


# ── deel 4: metric-vs-metric combo ─────────────────────────────────────────────

def test_compare_koppelt_tweede_meting_en_rendert_combo(tmp_path):
    dd = _dd(tmp_path)
    # reeks-tegel (over tijd) → 'vergelijk met'-menu beschikbaar met een andere reeks-meting.
    cockpit2.dispatch(dd, "metrics2_fav",
                      {"node": [_NODE], "source": ["pulse_visitors"], "measure": ["visitors"],
                       "dim": ["time"], "form": ["trend"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    tid = st.metrics.tiles_of(_NODE)[0]["id"]
    html = cockpit2.render_metrics2(st, st.records.get(_NODE), csrf_token="t")
    assert "metrics2_compare" in html                       # vergelijk-menu aanwezig op reeks-tegel
    cockpit2.dispatch(dd, "metrics2_compare",
                      {"node": [_NODE], "tid": [tid], "cmp_source": ["shopify"],
                       "cmp_measure": ["orders"], "cmp_dim": ["over_tijd"], "next": ["/"]},
                      username="guest")
    t2 = cockpit2._Stores(dd).metrics.tiles_of(_NODE)[0]
    assert t2["cmp_measure"] == "orders" and t2["cmp_source"] == "shopify"
    # leeg → vergelijking eraf
    cockpit2.dispatch(dd, "metrics2_compare",
                      {"node": [_NODE], "tid": [tid], "cmp_source": [""], "cmp_measure": [""],
                       "cmp_dim": [""], "next": ["/"]}, username="guest")
    assert "cmp_measure" not in cockpit2._Stores(dd).metrics.tiles_of(_NODE)[0]


def test_combo_svg_faalt_luid_zonder_twee_reeksen(tmp_path):
    from nooch_village.views.metrics import _combo_svg
    assert "geen twee reeksen" in _combo_svg([], [(1, 2)], "a", "b")
    out = _combo_svg([(1, 5), (2, 7)], [(1, 3), (2, 4)], "Bezoekers", "Orders")
    assert "combochart" in out and "staaf" in out and "lijn" in out
