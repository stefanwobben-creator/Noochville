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
