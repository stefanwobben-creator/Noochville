"""Tests voor ObservationStore — thread-vrij, tmp_path, geen bus."""
from __future__ import annotations
import pytest
from nooch_village.observations import ObservationStore


@pytest.fixture
def store(tmp_path):
    return ObservationStore(str(tmp_path / "observations.jsonl"))


def test_record_and_series_in_order(store):
    store.record("website_watcher", "bezoekers", 100, ts=1000.0)
    store.record("website_watcher", "bezoekers", 120, ts=2000.0)
    store.record("website_watcher", "bezoekers",  90, ts=3000.0)
    rows = store.series("website_watcher", "bezoekers")
    assert len(rows) == 3
    assert [r["value"] for r in rows] == [100, 120, 90]
    assert rows[0]["ts"] < rows[1]["ts"] < rows[2]["ts"]


def test_latest_returns_last(store):
    store.record("website_watcher", "bezoekers", 100, ts=1000.0)
    store.record("website_watcher", "bezoekers", 200, ts=2000.0)
    assert store.latest("website_watcher", "bezoekers")["value"] == 200


def test_series_filters_by_role_and_metric(store):
    store.record("website_watcher", "bezoekers", 50,  ts=1.0)
    store.record("trends",   "bezoekers", 99,  ts=2.0)
    store.record("website_watcher", "pageviews", 80,  ts=3.0)
    rows = store.series("website_watcher", "bezoekers")
    assert len(rows) == 1 and rows[0]["value"] == 50


def test_empty_series_returns_empty_list(store):
    assert store.series("onbekend", "metric") == []


def test_latest_on_empty_returns_none(store):
    assert store.latest("onbekend", "metric") is None


def test_meta_is_stored_and_returned(store):
    store.record("website_watcher", "bezoekers", 42, ts=1.0, meta={"locale": "nl"})
    row = store.latest("website_watcher", "bezoekers")
    assert row["meta"]["locale"] == "nl"


def test_series_sorted_even_if_written_out_of_order(store):
    store.record("website_watcher", "bezoekers", 300, ts=3000.0)
    store.record("website_watcher", "bezoekers", 100, ts=1000.0)
    store.record("website_watcher", "bezoekers", 200, ts=2000.0)
    rows = store.series("website_watcher", "bezoekers")
    assert [r["value"] for r in rows] == [100, 200, 300]


# ── datum + bron + één-datapunt-per-dag (record_daily) ───────────────────────
def test_datum_en_bron_worden_opgeslagen(store):
    store.record("ww", "visitors_day", 55, ts=1000.0, bron="plausible", datum="2026-07-03")
    row = store.latest("ww", "visitors_day")
    assert row["bron"] == "plausible" and row["datum"] == "2026-07-03"


def test_datum_afgeleid_uit_ts_bij_ontbreken(store):
    import datetime as dt
    ts = dt.datetime(2026, 7, 3, 12, 0, tzinfo=dt.timezone.utc).timestamp()
    store.record("ww", "visitors_day", 55, ts=ts)          # geen datum → UTC-dag van ts
    assert store.latest("ww", "visitors_day")["datum"] == "2026-07-03"


def test_record_daily_een_datapunt_per_bron_per_dag(store):
    assert store.record_daily("ww", "visitors_day", 55, bron="plausible", datum="2026-07-03", ts=1.0) is True
    assert store.record_daily("ww", "visitors_day", 99, bron="plausible", datum="2026-07-03", ts=2.0) is False  # zelfde dag+bron → skip
    assert store.record_daily("ww", "visitors_day", 60, bron="plausible", datum="2026-07-04", ts=3.0) is True   # andere dag → schrijft
    assert store.record_daily("ww", "visitors_day", 70, bron="andere",   datum="2026-07-03", ts=4.0) is True    # andere bron → schrijft
    assert [r["value"] for r in store.series("ww", "visitors_day")] == [55, 60, 70]     # 99 overgeslagen


def test_oude_rijen_zonder_datum_bron_blijven_leesbaar(store):
    store.record("ww", "bezoekers", 42, ts=1.0)            # legacy-vorm (geen bron/datum meegegeven)
    assert store.latest("ww", "bezoekers")["value"] == 42  # series/latest werken nog


# ── scope 2 punt 5: in-memory index (dedup O(1), incrementele update, invalidatie na migratie) ────
def test_index_dedup_en_incrementeel(tmp_path):
    from nooch_village.observations import ObservationStore
    o = ObservationStore(str(tmp_path / "o.jsonl"))
    assert o.record_daily("plausible", "plausible_visitors_day", 10, bron="plausible", datum="2026-07-06")
    assert not o.record_daily("plausible", "plausible_visitors_day", 99, bron="plausible", datum="2026-07-06")  # dup → O(1) via index
    assert o.record_daily("plausible", "plausible_visitors_day", 11, bron="plausible", datum="2026-07-07")
    # de reeks klopt (incrementeel geïndexeerd, geen file-herlees per call)
    assert [r["value"] for r in o.daily_series("plausible_visitors_day", bron="plausible")] == [10, 11]


def test_index_ziet_bestaande_data_bij_nieuwe_instance(tmp_path):
    from nooch_village.observations import ObservationStore
    p = str(tmp_path / "o.jsonl")
    ObservationStore(p).record_daily("gsc", "gsc_impressions_day", 77, bron="gsc", datum="2026-07-06")
    o2 = ObservationStore(p)                                   # verse instance leest het bestand één keer
    assert not o2.record_daily("gsc", "gsc_impressions_day", 5, bron="gsc", datum="2026-07-06")  # idempotent over instances
    assert [r["value"] for r in o2.daily_series("gsc_impressions_day", bron="gsc")] == [77]


def test_index_invalidatie_na_rename(tmp_path):
    from nooch_village.observations import ObservationStore
    o = ObservationStore(str(tmp_path / "o.jsonl"))
    o.record_daily("plausible", "visitors_day", 10, bron="plausible", datum="2026-07-06")
    _ = o.daily_series("visitors_day", bron="plausible")      # bouwt de index
    o.rename_metric("visitors_day", "plausible_visitors_day", bron="plausible")
    # na de herschrijf leest de index de nieuwe sleutel (geen stale index)
    assert o.daily_series("visitors_day", bron="plausible") == []
    assert [r["value"] for r in o.daily_series("plausible_visitors_day", bron="plausible")] == [10]


def test_remove_bron_behoudt_prefix(tmp_path):
    """remove_bron verwijdert alle rijen van een bron behalve een keep_prefix (opruimen verworpen ontwerp)."""
    from nooch_village.observations import ObservationStore
    o = ObservationStore(str(tmp_path / "o.jsonl"))
    o.record_daily("trends", "trends_footwear_day", 5, bron="trends", datum="2026-07-06")       # oud ontwerp
    o.record_daily("trends", "trends_vegan_shoes_day", 2, bron="trends", datum="2026-07-06")    # oud ontwerp
    o.record_daily("trends", "trends_ratio_thrift_luxury_day", 0.25, bron="trends", datum="2026-07-13")  # nieuw
    o.record_daily("plausible", "plausible_visitors_day", 10, bron="plausible", datum="2026-07-06")      # andere bron
    n = o.remove_bron("trends", keep_prefix="trends_ratio_")
    assert n == 2                                                # de 2 oude trends-reeksen weg
    left = {(r["bron"], r["metric"]) for r in o._read_all()}
    assert ("trends", "trends_ratio_thrift_luxury_day") in left and ("plausible", "plausible_visitors_day") in left
    assert not any(m in ("trends_footwear_day", "trends_vegan_shoes_day") for _, m in left)
    assert o.remove_bron("trends", keep_prefix="trends_ratio_") == 0    # idempotent
