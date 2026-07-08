"""Meetcatalogus-contract healthcheck: ongecatalogiseerde reeks → signaal; inactieve bron → stil;
gecatalogiseerde niet-vullende reeks → signaal na N; known-future/leeg → geen vals alarm."""
from __future__ import annotations

from nooch_village.meetcatalog import healthcheck, _in_catalog

NOW = 1_800_000_000.0
DAY = 86400


def _row(bron, metric, ts, datum="2026-07-07", value=1):
    return {"bron": bron, "metric": metric, "ts": ts, "datum": datum, "value": value}


def test_ongecatalogiseerde_reeks_signaal():
    rows = [_row("plausible", "plausible_visitors_day", NOW),
            _row("mystery", "brand_new_metric_day", NOW)]
    sigs = healthcheck(rows, now_ts=NOW)
    assert any(s["type"] == "ongecatalogiseerd" and s["metric"] == "brand_new_metric_day" for s in sigs)
    assert not any(s.get("metric") == "plausible_visitors_day" for s in sigs)   # bekend → geen signaal


def test_inactieve_bron_stil():
    # gdelt: inactief + 100 dagen oud → GÉÉN alarm (en het matcht de catalogus, dus geen ongecatalogiseerd)
    assert healthcheck([_row("gdelt_tone", "gdelt_sustainable_footwear_day", NOW - 100 * DAY)], now_ts=NOW) == []
    assert healthcheck([_row("shopify", "shopify_orders_day", NOW - 100 * DAY)], now_ts=NOW) == []


def test_niet_vullend_na_N():
    # actieve daily family, laatste schrijf 4 dagen oud (> 2.5d marge) → signaal
    sigs = healthcheck([_row("plausible", "plausible_visitors_day", NOW - 4 * DAY)], now_ts=NOW)
    assert any(s["type"] == "niet-vullend" and s["family"] == "plausible_visitors_day" for s in sigs)
    # verse schrijf (1 dag) → geen signaal
    assert healthcheck([_row("plausible", "plausible_visitors_day", NOW - 1 * DAY)], now_ts=NOW) == []


def test_weekly_marge_ruimer_dan_daily():
    # trends weekly: 6 dagen oud → nog OK (marge 8d); 10 dagen → signaal
    assert healthcheck([_row("trends", "trends_ratio_thrift_luxury_day", NOW - 6 * DAY)], now_ts=NOW) == []
    assert any(s["type"] == "niet-vullend"
               for s in healthcheck([_row("trends", "trends_ratio_thrift_luxury_day", NOW - 10 * DAY)], now_ts=NOW))


def test_geen_data_of_leeg_geen_alarm():
    assert healthcheck([], now_ts=NOW) == []            # lege store / known-future families → 0 signalen


def test_irregular_geen_recency_check():
    # werk_tevredenheid is irregular (per overleg): oude schrijf → GÉÉN niet-vullend-alarm
    assert healthcheck([_row("werkoverleg", "werk_tevredenheid_day", NOW - 100 * DAY)], now_ts=NOW) == []


def test_dimensie_en_dynamische_families_bekend():
    # per-land, page_path, visitors_via, keyword-dim, KE-dynamisch, openalex-concept, slow÷fast: gecatalogiseerd
    for bron, metric in [("plausible", "plausible_visitors_day::nl"),
                         ("plausible", "plausible_page_visitors_day::home"),
                         ("plausible", "visitors_via_ig"),
                         ("gsc", "gsc_impressions_day::nothing_shoes"),
                         ("keywordseverywhere", "keywordseverywhere_footwear_day"),
                         ("openalex", "openalex_works_90d::mycelium"),
                         ("trends", "trends_ratio_slow_fashion_fast_fashion_day")]:
        assert _in_catalog(metric, bron), (bron, metric)


def test_schone_store_nul_vals_alarm():
    """Een schone store met verse schrijf voor elke actieve family + gelabelde inactieve bron → 0 signalen."""
    rows = [
        _row("plausible", "plausible_visitors_day", NOW - DAY),
        _row("plausible", "plausible_visitors_day::nl", NOW - DAY),
        _row("plausible", "plausible_page_visitors_day::home", NOW - DAY),
        _row("plausible", "visitors_via_ig", NOW - DAY),
        _row("gsc", "gsc_impressions_day", NOW - DAY),
        _row("gsc", "gsc_impressions_day::nothing_shoes", NOW - DAY),
        _row("openalex", "openalex_works_90d::mycelium", NOW - 2 * DAY),
        _row("trends", "trends_ratio_thrift_luxury_day", NOW - 2 * DAY),
        _row("keywordseverywhere", "keywordseverywhere_footwear_day", NOW - 2 * DAY),
        _row("alphavantage", "alphavantage_spx_day", NOW - DAY),
        _row("werkoverleg", "werk_tevredenheid_day", NOW - 100 * DAY),   # irregular → geen alarm
        _row("gdelt_tone", "gdelt_x_day", NOW - 100 * DAY),              # inactief → geen alarm
    ]
    assert healthcheck(rows, now_ts=NOW) == []
