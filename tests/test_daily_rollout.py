"""Uitrol dag-observatie-aanpak naar werkoverleg + Shopify: elke bron schrijft per dag één datapunt
(idempotent), naast de bestaande aggregaten. 'Actueel' = laatste bekende dagwaarde, grijs bij niet-live."""
from __future__ import annotations
import time

from nooch_village import cockpit2
from nooch_village.observations import ObservationStore, record_werk_daily
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
    assert _daily_obs_key("pulse_visitors", "visitors") == ("plausible_visitors_day", "plausible")
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


def test_werk_over_tijd_fallback_dan_dagreeks(tmp_path):
    from nooch_village.views.metrics import _fetch
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    # ZONDER dag-observaties → val terug op de oude log-route (geen blinde periode)
    st.werk._m.setdefault(C, {})["log"] = [
        {"at": now - 1 * 86400, "tevredenheid": 7.0}, {"at": now - 2 * 86400, "tevredenheid": 8.0}]
    st.werk._save()
    r = _fetch(cockpit2._Stores(dd), f"werk:{C}", "tevredenheid", "over_tijd", None, None)
    assert r["kind"] == "series" and r.get("chart") is None and len(r["points"]) == 2   # log-aggregaat-route
    # MÉT dag-observaties → nieuwe dagreeks-route (chart:line, uit observations)
    st.observations.record_daily(C, "werk_tevredenheid_day", 8.5, bron="werkoverleg", datum="2026-07-01", ts=now - 2 * 86400)
    st.observations.record_daily(C, "werk_tevredenheid_day", 7.5, bron="werkoverleg", datum="2026-07-02", ts=now - 1 * 86400)
    r2 = _fetch(cockpit2._Stores(dd), f"werk:{C}", "tevredenheid", "over_tijd", None, None)
    assert r2["chart"] == "line" and [p[1] for p in r2["points"]] == [8.5, 7.5]           # uit de dagreeks


def test_shopify_over_tijd_leest_dagreeks(tmp_path):
    from nooch_village.views.metrics import _fetch
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    leeg = _fetch(st, "shopify", "pairs_sold", "over_tijd", None, None)
    assert leeg["chart"] == "line" and leeg["points"] == []                                # leeg tot creds → geen data
    st.observations.record_daily("shopify", "shopify_pairs_sold_day", 40, bron="shopify", datum="2026-07-01", ts=now - 2 * 86400)
    st.observations.record_daily("shopify", "shopify_pairs_sold_day", 55, bron="shopify", datum="2026-07-02", ts=now - 1 * 86400)
    r = _fetch(cockpit2._Stores(dd), "shopify", "pairs_sold", "over_tijd", None, None)
    assert r["chart"] == "line" and [p[1] for p in r["points"]] == [40, 55]


def test_dagreeks_render_geen_data_1_punt_2_punten(tmp_path):
    from nooch_village.views.metrics import _render_form, _fetch
    dd = _dd(tmp_path); st = cockpit2._Stores(dd); now = time.time()
    # 0 punten → 'geen data' (zelfde afhandeling als bij Plausible)
    r0 = _fetch(st, f"werk:{C}", "duur", "over_tijd", None, None)  # geen dag-obs, geen log → leeg
    # zorg dat de log óók leeg is zodat de fallback niets teruggeeft
    st.werk._m.setdefault(C, {})["log"] = []; st.werk._save()
    r0 = _fetch(cockpit2._Stores(dd), "shopify", "aov", "over_tijd", None, None)
    assert "geen data" in _render_form(r0, "trend")
    # 1 punt → 'te weinig voor een lijn'
    st.observations.record_daily("shopify", "shopify_aov_day", 48, bron="shopify", datum="2026-07-01", ts=now - 86400)
    r1 = _fetch(cockpit2._Stores(dd), "shopify", "aov", "over_tijd", None, None)
    assert "te weinig" in _render_form(r1, "trend")
    # ≥2 punten → een lijn
    st.observations.record_daily("shopify", "shopify_aov_day", 52, bron="shopify", datum="2026-07-02", ts=now)
    r2 = _fetch(cockpit2._Stores(dd), "shopify", "aov", "over_tijd", None, None)
    assert "<polyline" in _render_form(r2, "trend")
