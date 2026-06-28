"""Metrics: store (link/kpi/samples/venster/pins) + tab/dispatch (rol-KPI's, cirkeldashboard, bron)."""
from __future__ import annotations
import time

from nooch_village import cockpit2
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples

C = "mother_earth__nooch"
RID = "mother_earth__nooch__website_developer"
MKT = "mother_earth__nooch__marketing_lead"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_store_link_kpi_sample(tmp_path):
    m = MetricStore(str(tmp_path / "m.json"))
    assert m.add_link(C, "Boekhouding", "https://x/y")
    assert m.add_link(C, "", "") is None
    k = m.add_kpi(RID, "Conversie", "%")
    assert m.add_sample(k["id"], "3.5") and m.add_sample(k["id"], "ab") is False
    assert m.get(k["id"])["samples"][0]["value"] == 3.5


def test_venster_filtert_samples():
    now = time.time()
    samples = [{"at": now - 100 * 86400, "value": 1}, {"at": now - 2 * 86400, "value": 2},
               {"at": now, "value": 3}]
    assert [v for _, v in filter_samples(samples, window_cutoff("7d", now))] == [2, 3]
    assert [v for _, v in filter_samples(samples, window_cutoff("alles", now))] == [1, 2, 3]


def test_bron_kpi_pulse_visitors(tmp_path):
    dd = _dd(tmp_path)
    # bron-KPI uit data toevoegen (pulse_visitors), bestaande data van het dorp
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [MKT], "pick": ["source:pulse_visitors"], "next": ["/"]})
    it = [i for i in cockpit2._Stores(dd).metrics.for_node(MKT) if i["kind"] == "kpi"][0]
    assert it["source"] == "pulse_visitors" and it["unit"] == "bezoekers"
    # bron-KPI's accepteren geen handmatige meting
    assert cockpit2._Stores(dd).metrics.add_sample(it["id"], 5) is False


def test_rol_tab_kpi_en_meting(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Conversie"],
                                        "unit": ["%"], "next": ["/"]})
    mid = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]["id"]
    cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["4.2"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), RID, "metrics", csrf_token="t")
    assert "Conversie" in page and "kpi-card" in page and "Periode:" in page
    assert "m_add_kpi" in page and "Link toevoegen" in page          # combi KPI + link


def test_cirkel_dashboard_pin_uit_rol_kpis(tmp_path):
    dd = _dd(tmp_path)
    # KPI op een rol -> verschijnt in de cirkel-selectie met provider-rol
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [MKT], "pick": ["source:pulse_visitors"], "next": ["/"]})
    mid = cockpit2._Stores(dd).metrics.for_node(MKT)[0]["id"]
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "KPI's selecteren" in page and "Marketing Lead" in page    # provider zichtbaar
    # Lead Link pint de KPI op het cirkeldashboard
    cockpit2.dispatch(dd, "m_pin", {"circle": [C], "mid": [mid], "next": ["/"]})
    assert cockpit2._Stores(dd).metrics.is_pinned(C, mid)
    dash = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "Cirkeldashboard" in dash and "levert:" in dash
    # weer losmaken
    cockpit2.dispatch(dd, "m_unpin", {"circle": [C], "mid": [mid], "next": ["/"]})
    assert not cockpit2._Stores(dd).metrics.is_pinned(C, mid)


def test_link_metric_op_cirkel(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_link", {"node": [C], "name": ["Jaarcijfers"],
                                         "url": ["https://docs.example/x"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "Jaarcijfers" in page and "kpi-link" in page
