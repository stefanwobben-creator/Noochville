"""Test _extract_pulse_metrics — pure helper, thread-vrij, geen bus."""
from nooch_village.roles import _extract_pulse_metrics


def test_extract_visitors_and_pageviews():
    plausible = {"results": {"visitors": {"value": 165}, "pageviews": {"value": 268}}}
    assert _extract_pulse_metrics(plausible) == [("visitors", 165.0), ("pageviews", 268.0)]


def test_extract_skips_none_values():
    plausible = {"results": {"visitors": {"value": None}, "pageviews": {"value": 42}}}
    assert _extract_pulse_metrics(plausible) == [("pageviews", 42.0)]


def test_extract_empty_results():
    assert _extract_pulse_metrics({}) == []
    assert _extract_pulse_metrics({"results": {}}) == []


def test_extract_failclosed_on_non_dict():
    assert _extract_pulse_metrics("error: no key") == []
    assert _extract_pulse_metrics({"error": "no token"}) == []


def test_extract_partial_missing_key():
    plausible = {"results": {"visitors": {"value": 99}}}
    assert _extract_pulse_metrics(plausible) == [("visitors", 99.0)]
