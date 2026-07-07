"""A1: dashboard-tegel toonde bron-data niet (KPI met lege source/veld). Fix: generieke bron-veld-route
(<source>_<veld>_day), create-flow zet veld/categorie/aard, wees-sweep repareert oude systeem-KPI's, en
systeembron-KPI's verdwijnen uit de handmatige invoer-sectie. Incl. de vier review-aanvullingen."""
from __future__ import annotations
import types

from nooch_village import cockpit2
from nooch_village.metrics import MetricStore
from nooch_village.observations import ObservationStore
from nooch_village.views import metrics as vm

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


# ── aanvulling 1: is_sys op meetwijze/auto/origin, niet alleen source ────────────────────────────
def test_is_system_kpi_herkent_auto_zonder_source():
    assert vm._is_system_kpi({"auto": True, "source": ""})            # pre-fix KPI: source leeg, auto True
    assert vm._is_system_kpi({"meetwijze": "systeem"})
    assert vm._is_system_kpi({"origin": "plausible"})
    assert not vm._is_system_kpi({"source": "", "auto": False, "meetwijze": "handmatig"})


# ── create-flow: add_kpi bewaart de binding ──────────────────────────────────────────────────────
def test_add_kpi_bewaart_veld_categorie_aard(tmp_path):
    m = MetricStore(str(tmp_path / "m.json"))
    k = m.add_kpi(C, "Paginaweergaven", "n", origin="plausible", veld="pageviews",
                  categorie="Website", aard="reeks", meetwijze="systeem", auto=True)
    assert k["veld"] == "pageviews" and k["categorie"] == "Website" and k["aard"] == "reeks"


# ── de kern-fix: bron-KPI (origin+veld) leest de bestaande dagreeks uit de store ──────────────────
def test_bron_kpi_leest_dagreeks_generiek(tmp_path):
    dd = _dd(tmp_path)
    obs = ObservationStore(f"{dd}/observations.jsonl")
    for d, v in [("2026-07-04", 17), ("2026-07-05", 20), ("2026-07-06", 20)]:
        obs.record_daily("plausible", "plausible_pageviews_day", v, bron="plausible", datum=d)
    st = cockpit2._Stores(dd)
    it = st.metrics.add_kpi(C, "Paginaweergaven (Plausible)", "n", origin="plausible", veld="pageviews",
                            categorie="Website", aard="reeks", meetwijze="systeem", auto=True)
    assert [s["value"] for s in vm._kpi_samples(st, it)] == [17, 20, 20]
    res = vm._fetch(st, f"kpi:{it['id']}", "value", "time", None)
    assert res["kind"] == "series" and [p[1] for p in res["points"]] == [17, 20, 20]


# ── aanvulling 4: bezoekers via DEZELFDE generieke route → identieke sleutel/waardes (regressie) ──
def test_bezoekers_via_generieke_route_identiek(tmp_path):
    assert vm._daily_obs_key("pulse_visitors", "visitors") == ("plausible_visitors_day", "plausible")
    dd = _dd(tmp_path)
    obs = ObservationStore(f"{dd}/observations.jsonl")
    for d, v in [("2026-07-05", 15), ("2026-07-06", 16)]:
        obs.record_daily("plausible", "plausible_visitors_day", v, bron="plausible", datum=d)
    st = cockpit2._Stores(dd)
    res = vm._fetch(st, "pulse_visitors", "visitors", "time", None)
    assert [p[1] for p in res["points"]] == [15, 16]                  # identiek aan de ruwe reeks


# ── aanvulling 2: wees-sweep repareert uit de def, rapporteert het niet-afleidbare, idempotent ────
def test_wezen_sweep_repareert_rapporteert_idempotent(tmp_path):
    m = MetricStore(str(tmp_path / "m.json"))
    # wees zoals op prod: systeem-KPI, meettype 'venster' (→ aard=reeks), lege veld/categorie, mét def_id
    orphan = m.add_kpi(C, "Paginaweergaven (Plausible)", "n", origin="plausible", meetwijze="systeem",
                       auto=True, meettype="venster", def_id="D1")
    assert not orphan["veld"] and not orphan["categorie"] and orphan["aard"] == "reeks"
    m.add_tile(C, f"kpi:{orphan['id']}", "value", "none", "getal")     # reeks-tegel met dim=none
    # tweede wees zónder def → niet afleidbaar
    orphan2 = m.add_kpi(C, "Losse systeem-KPI", "n", auto=True, meetwijze="systeem")
    fake_defs = types.SimpleNamespace(current=lambda did: (
        {"veld": "pageviews", "categorie": "Website", "aard": "reeks"} if did == "D1" else None))

    rep = m.migrate_metric_bindings(fake_defs)
    fixed = m.get(orphan["id"])
    assert fixed["veld"] == "pageviews" and fixed["categorie"] == "Website"        # afgeleid uit de def
    assert [t["dim"] for t in m.tiles_of(C) if t["source"] == f"kpi:{orphan['id']}"] == ["time"]  # none→time
    assert rep["repaired"] and rep["tiles_fixed"]
    assert any(u["id"] == orphan2["id"] for u in rep["unresolved"])   # geen def → gerapporteerd, niet gegokt
    rep2 = m.migrate_metric_bindings(fake_defs)                        # idempotent
    assert not rep2["repaired"] and not rep2["tiles_fixed"]


# ── sectie-split: systeembron-KPI verdwijnt uit "Eigen KPI's (data invoeren)" ─────────────────────
def test_systeem_kpi_niet_in_invoer_sectie(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.metrics.add_kpi(C, "Systeem paginaweergaven", "n", origin="plausible", veld="pageviews",
                       categorie="Website", aard="reeks", meetwijze="systeem", auto=True)
    st.metrics.add_kpi(C, "Handmatige conversie", "%")                 # echte handmatige KPI
    page = cockpit2.render_node(cockpit2._Stores(dd), C, "metrics", csrf_token="t")
    inv = page.split("Eigen KPI's (data invoeren)")[1].split("Systeem-KPI's")[0]
    assert "Handmatige conversie" in inv and "Systeem paginaweergaven" not in inv
    assert "Systeem paginaweergaven" in page.split("Systeem-KPI's")[1]
