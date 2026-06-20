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
