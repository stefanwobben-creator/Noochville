"""Fail-closed rekenlogica voor formule-KPI's over meerdere bronnen: mist één bron een dag, dan is
die dag no_data (nooit doorrekenen met een oude waarde, nooit stilzwijgend 0) — in grafiek én tabel."""
from __future__ import annotations
import datetime

from nooch_village import cockpit2
from nooch_village.views.metrics import _formula_daily, _render_formula_tile, _day_key

C = "mother_earth__nooch"
D1 = datetime.datetime(2026, 7, 1, 12, 0).timestamp()   # midden op de dag → geen tz-rand
D2 = datetime.datetime(2026, 7, 2, 12, 0).timestamp()


def _two_kpis(tmp_path):
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd); st = cockpit2._Stores(dd)
    a = st.metrics.add_kpi(C, "A", ""); b = st.metrics.add_kpi(C, "B", "")
    return dd, st, a["id"], b["id"]


def _tile(a, b, op="÷"):
    return {"id": "t1", "form": "formule", "measure": "Conversie",
            "f_a": f"kpi:{a}|value|none", "f_op": op, "f_b": f"kpi:{b}|value|none",
            "aggregatie": "gemiddelde"}


def test_ontbrekende_dag_bij_bron_b(tmp_path):
    dd, st, a, b = _two_kpis(tmp_path)
    st.metrics.add_sample(a, 100, at=D1); st.metrics.add_sample(a, 200, at=D2)
    st.metrics.add_sample(b, 10, at=D1)                 # B mist dag 2
    rows = {_day_key(r["at"]): r for r in _formula_daily(cockpit2._Stores(dd), _tile(a, b), None, None)}
    assert rows["2026-07-01"]["value"] == 10.0 and rows["2026-07-01"]["no_data"] is False   # 100 / 10
    assert rows["2026-07-02"]["no_data"] is True and rows["2026-07-02"]["value"] is None     # B mist → no_data


def test_ontbrekende_dag_bij_bron_a(tmp_path):
    dd, st, a, b = _two_kpis(tmp_path)
    st.metrics.add_sample(a, 100, at=D1)                # A mist dag 2
    st.metrics.add_sample(b, 10, at=D1); st.metrics.add_sample(b, 20, at=D2)
    rows = {_day_key(r["at"]): r for r in _formula_daily(cockpit2._Stores(dd), _tile(a, b), None, None)}
    assert rows["2026-07-01"]["value"] == 10.0 and rows["2026-07-01"]["no_data"] is False   # 100 / 10
    assert rows["2026-07-02"]["no_data"] is True and rows["2026-07-02"]["value"] is None     # A mist → no_data


def test_deling_door_nul_is_no_data(tmp_path):
    dd, st, a, b = _two_kpis(tmp_path)
    st.metrics.add_sample(a, 100, at=D1)
    st.metrics.add_sample(b, 0, at=D1)                  # deler 0 → geen verzonnen waarde
    rows = {_day_key(r["at"]): r for r in _formula_daily(cockpit2._Stores(dd), _tile(a, b), None, None)}
    assert rows["2026-07-01"]["no_data"] is True and rows["2026-07-01"]["value"] is None


def test_render_markeert_no_data_in_grafiek_en_tabel(tmp_path):
    dd, st, a, b = _two_kpis(tmp_path)
    st.metrics.add_sample(a, 100, at=D1); st.metrics.add_sample(a, 200, at=D2)
    st.metrics.add_sample(b, 10, at=D1)                 # dag 2 ontbreekt bij B
    html = _render_formula_tile(cockpit2._Stores(dd), st.records.get(C), _tile(a, b), "t", None, None)
    assert "geen data" in html                          # tabel markeert de ontbrekende dag
    # de grafiek plot maar één punt (dag 1) → geen lijn, en zeker geen 0 of doorgerekende waarde
    assert html.count("<polyline") == 0 and "kpi-val" in html


def test_dispatch_formule_dan_render_faalt_closed(tmp_path):
    # end-to-end: via de wizard-dispatch een formule-tegel maken en renderen
    dd, st, a, b = _two_kpis(tmp_path)
    st.metrics.add_sample(a, 100, at=D1); st.metrics.add_sample(a, 200, at=D2)
    st.metrics.add_sample(b, 10, at=D1)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "mode": ["formule"],
                                       "f_a": [f"kpi:{a}|value|none"], "f_op": ["÷"],
                                       "f_b": [f"kpi:{b}|value|none"], "f_name": ["Conversie"],
                                       "f_agg": ["gemiddelde"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t", mw="jaar")
    assert "Conversie" in page and "geen data" in page   # tegel toont de fail-closed dag
