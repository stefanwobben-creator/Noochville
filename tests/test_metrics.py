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


def test_rol_tab_eigen_kpi_en_meting(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Conversie"],
                                        "unit": ["%"], "next": ["/"]})
    mid = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]["id"]
    cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["4.2"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), RID, "metrics", csrf_token="t")
    # mini-Looker: wizard + eigen KPI's + periode
    assert "Conversie" in page and "+ KPI op dashboard" in page and "Periode:" in page
    assert "Eigen KPI's" in page and "+ Link" in page


def test_tile_wizard_combos(tmp_path):
    dd = _dd(tmp_path)
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    # zelf-beschrijvende bronnen verschijnen als combo's (bron: measure · dimensie)
    assert "Verkoop: Paren verkocht · per land" in page
    assert "Websitebezoekers: Bezoekers (7d) · over tijd" in page
    assert "tile_add" in page and "Vorm" in page


def test_tile_toevoegen_en_vormen(tmp_path):
    dd = _dd(tmp_path)
    # tegel: verkoop per land als verdeling (staaf)
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["shopify|orders|country"],
                                       "form": ["verdeling"], "target": [""], "next": ["/"]})
    t = cockpit2._Stores(dd).metrics.tiles_of(C)[0]
    assert t["source"] == "shopify" and t["dim"] == "country" and t["form"] == "verdeling"
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "tile" in page and ("bars" in page or "geen uitsplitsing" in page)
    # doelmeter met target
    cockpit2.dispatch(dd, "tile_add", {"node": [C], "combo": ["shopify|pairs_sold|none"],
                                       "form": ["doelmeter"], "target": ["1000"], "next": ["/"]})
    assert cockpit2._Stores(dd).metrics.tiles_of(C)[1]["target"] == 1000.0
    dash = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "goal" in dash and "/ 1000" in dash
    # verwijderen
    tid = cockpit2._Stores(dd).metrics.tiles_of(C)[0]["id"]
    cockpit2.dispatch(dd, "tile_remove", {"node": [C], "tid": [tid], "next": ["/"]})
    assert len(cockpit2._Stores(dd).metrics.tiles_of(C)) == 1


def test_grondslag_en_doelkoppeling(tmp_path):
    dd = _dd(tmp_path)
    # handmatige KPI met grondslag (definitie/richting/drempel)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [RID], "pick": ["manual"], "name": ["Conversie"],
                                        "unit": ["%"], "definition": ["betaalde orders / bezoekers"],
                                        "direction": ["up"], "threshold": ["2"], "next": ["/"]})
    it = [i for i in cockpit2._Stores(dd).metrics.for_node(RID) if i["kind"] == "kpi"][0]
    assert it["definition"] == "betaalde orders / bezoekers" and it["direction"] == "up" and it["threshold"] == 2.0
    g = cockpit2._grondslag(cockpit2._Stores(dd), f"kpi:{it['id']}", "value")
    assert g["definitie"] and g["richting"] == "up"
    # tegel met doel-koppeling aan een project
    st = cockpit2._Stores(dd)
    pid = st.projects.create(RID, "1000 paar in Q4", "human")
    cockpit2.dispatch(dd, "tile_add", {"node": [RID], "combo": ["shopify|pairs_sold|none"],
                                       "form": ["doelmeter"], "target": ["1000"], "goal_pid": [pid], "next": ["/"]})
    t = cockpit2._Stores(dd).metrics.tiles_of(RID)[0]
    assert t["goal_pid"] == pid and t["target"] == 1000.0
    page = cockpit2.render_node(cockpit2._Stores(dd), RID, "metrics", csrf_token="t")
    assert "tile-info" in page and "naar doel:" in page and "1000 paar in Q4" in page   # grondslag + doel zichtbaar


def test_built_in_grondslag(tmp_path):
    dd = _dd(tmp_path)
    g = cockpit2._grondslag(cockpit2._Stores(dd), "shopify", "pairs_sold")
    assert "paren" in g["eenheid"] and g["bron"] == "Shopify" and g["richting"] == "up"


def test_handmatige_kpi_wordt_bron_in_wizard(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_kpi", {"node": [MKT], "pick": ["manual"], "name": ["NPS"],
                                        "unit": ["score"], "next": ["/"]})
    # op de cirkel verschijnt de rol-KPI als bron in de wizard
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "NPS: NPS · over tijd" in page


def test_link_metric(tmp_path):
    dd = _dd(tmp_path)
    cockpit2.dispatch(dd, "m_add_link", {"node": [C], "name": ["Jaarcijfers"],
                                         "url": ["https://docs.example/x"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    assert "Jaarcijfers" in page and "kpi-link" in page
