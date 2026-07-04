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


def test_extract_utm_sources():
    plausible = {
        "results": {"visitors": {"value": 50}},
        "utm_sources": [
            {"utm_source": "bluemarble", "visitors": 7},
            {"utm_source": "shopify_email", "visitors": 4},
        ],
    }
    result = dict(_extract_pulse_metrics(plausible))
    assert result["visitors"] == 50.0
    assert result["visitors_via_bluemarble"] == 7.0
    assert result["visitors_via_shopify_email"] == 4.0


def test_extract_utm_sources_skips_empty_source():
    plausible = {
        "results": {},
        "utm_sources": [
            {"utm_source": "", "visitors": 3},
            {"utm_source": None, "visitors": 2},
            {"utm_source": "bluemarble", "visitors": 7},
        ],
    }
    keys = [k for k, _ in _extract_pulse_metrics(plausible)]
    assert keys == ["visitors_via_bluemarble"]


def test_extract_utm_sources_absent_is_fine():
    plausible = {"results": {"visitors": {"value": 10}}}
    result = dict(_extract_pulse_metrics(plausible))
    assert "visitors" in result
    assert not any(k.startswith("visitors_via_") for k in result)


def test_pulse_schrijft_dagwaarde_als_observatie(tmp_path):
    """De puls schrijft de losse Plausible-dagwaarde als één datapunt/dag naar de observatie-store,
    met bron+datum, idempotent (tweede puls dezelfde dag → geen duplicaat)."""
    from types import SimpleNamespace
    from nooch_village.roles import WebsiteWatcherWorker
    from nooch_village.observations import ObservationStore
    obs = ObservationStore(str(tmp_path / "observations.jsonl"))
    fake = SimpleNamespace(id="analyst", context=SimpleNamespace(observations=obs, monitoring=None))
    plausible = {"results": {"visitors": {"value": 55}},
                 "visitors_day": {"date": "2026-07-03", "value": 7}}
    WebsiteWatcherWorker._log_pulse_metrics(fake, plausible)
    row = obs.latest("analyst", "visitors_day")
    assert row["value"] == 7 and row["bron"] == "plausible" and row["datum"] == "2026-07-03"
    WebsiteWatcherWorker._log_pulse_metrics(fake, plausible)                     # zelfde dag opnieuw
    assert len(obs.series("analyst", "visitors_day")) == 1               # geen duplicaat
