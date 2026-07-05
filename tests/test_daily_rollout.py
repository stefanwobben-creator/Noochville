"""Uitrol dag-observatie-aanpak naar werkoverleg + Shopify: elke bron schrijft per dag één datapunt
(idempotent), naast de bestaande aggregaten. 'Actueel' = laatste bekende dagwaarde, grijs bij niet-live."""
from __future__ import annotations
import time

from nooch_village import cockpit2
from nooch_village.observations import ObservationStore, record_werk_daily, record_shopify_daily
from nooch_village.views.metrics import _metrics_tab_html, _daily_obs_key

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_record_werk_daily_idempotent(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    now = time.time()
    record_werk_daily(obs, C, {"at": now, "tevredenheid": 8.4, "duur_min": 12})
    record_werk_daily(obs, C, {"at": now, "tevredenheid": 9.9, "duur_min": 30})  # zelfde dag → skip
    assert [r["value"] for r in obs.daily_series("werk_tevredenheid_day", bron="werkoverleg")] == [8.4]
    assert [r["value"] for r in obs.daily_series("werk_duur_day", bron="werkoverleg")] == [12]


def test_record_shopify_daily_failclosed(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    record_shopify_daily(obs, {"pairs_sold": 40, "orders": 25, "revenue": 1200})  # aov ontbreekt
    assert [r["value"] for r in obs.daily_series("shopify_pairs_sold_day", bron="shopify")] == [40]
    assert obs.daily_series("shopify_aov_day", bron="shopify") == []              # ontbrekende metric → niets
    record_shopify_daily(obs, {"pairs_sold": 99})                                 # zelfde dag → skip
    assert [r["value"] for r in obs.daily_series("shopify_pairs_sold_day", bron="shopify")] == [40]


def test_wo_close_schrijft_dagwaarde(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    st.werk.open(C)
    st.werk.set_checkout(C, "p1", 8)
    st.werk._save()
    cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]}, username="guest")
    obs = cockpit2._Stores(dd).observations
    assert obs.daily_series("werk_tevredenheid_day", bron="werkoverleg")          # dagwaarde geschreven
    # de all-time log blijft bestaan (niet ter vervanging)
    assert cockpit2._Stores(dd).werk.log(C)


def test_daily_obs_key_mapping():
    assert _daily_obs_key("pulse_visitors", "visitors") == ("visitors_day", "plausible")
    assert _daily_obs_key(f"werk:{C}", "tevredenheid") == ("werk_tevredenheid_day", "werkoverleg")
    assert _daily_obs_key("shopify", "aov") == ("shopify_aov_day", "shopify")
    assert _daily_obs_key("kpi:x", "value") == (None, None)


def test_actueel_toont_laatste_dagwaarde_en_grijs(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    record_werk_daily(st.observations, C, {"at": now, "tevredenheid": 8.4, "duur_min": 12})
    st.metrics.add_tile(C, f"werk:{C}", "tevredenheid", "gemiddeld", "getal")
    h = _metrics_tab_html(cockpit2._Stores(dd), st.records.get(C), csrf="t", win="actueel")
    assert "8.4" in h and "mw=actueel" in h                                       # laatste dagwaarde + Actueel klikbaar
    # een bron zonder dag-observaties → 'geen live data'
    st.metrics.add_tile(C, "kpi:none", "value", "none", "getal")
    h2 = _metrics_tab_html(cockpit2._Stores(dd), st.records.get(C), csrf="t", win="actueel")
    assert "geen live data" in h2
