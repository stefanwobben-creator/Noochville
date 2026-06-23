"""Tests voor SerpapiTrendsSkill. Geen netwerk: de SerpApi-getter wordt vervangen."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from nooch_village.skills_impl.serpapi_trends import (
    SerpapiTrendsSkill, _parse_timeseries, _parse_related,
)


# ── pure parsers ──────────────────────────────────────────────────────────────

def test_parse_timeseries_richting_stijgend():
    resp = {"interest_over_time": {"timeline_data": [
        {"values": [{"extracted_value": 40}]},
        {"values": [{"extracted_value": 75}]},
    ]}}
    latest, direction = _parse_timeseries(resp)
    assert latest == 75
    assert direction == "stijgend"


def test_parse_timeseries_leeg_geeft_none():
    latest, direction = _parse_timeseries({"interest_over_time": {"timeline_data": []}})
    assert latest is None
    assert direction == "vlak"


def test_parse_related_top_en_rising_met_breakout():
    resp = {"related_queries": {
        "top": [{"query": "vegan sneakers", "value": "100", "extracted_value": 100}],
        "rising": [
            {"query": "barefoot vegan", "value": "+450%", "extracted_value": 450},
            {"query": "new vegan brand", "value": "Breakout", "extracted_value": 0},
        ],
    }}
    top, rising = _parse_related(resp)
    assert top == [{"query": "vegan sneakers", "value": 100}]
    assert rising[0] == {"query": "barefoot vegan", "value": 450, "breakout": False}
    assert rising[1]["breakout"] is True


# ── run() met nep-getter ──────────────────────────────────────────────────────

class _FakeSerpapi(SerpapiTrendsSkill):
    """Vervangt _get door canned responses, telt aanroepen."""
    def __init__(self):
        self.calls = []

    def _get(self, params):
        self.calls.append(params)
        if params["data_type"] == "TIMESERIES":
            return {"interest_over_time": {"timeline_data": [
                {"values": [{"extracted_value": 30}]},
                {"values": [{"extracted_value": 60}]},
            ]}}
        return {"related_queries": {
            "top": [{"query": f"{params['q']} duurzaam", "extracted_value": 80}],
            "rising": [{"query": f"{params['q']} barefoot", "value": "Breakout", "extracted_value": 0}],
        }}


def _ctx(tmp_path, key="serp-key"):
    return SimpleNamespace(
        data_dir=str(tmp_path),
        settings={"SERPAPI_API_KEY": key, "serpapi_keywords_per_run": "5", "trends_geo": "GB"},
        lexicon=None, library=None,
    )


def test_zonder_key_faalt_closed(tmp_path):
    ctx = _ctx(tmp_path, key="")
    with pytest.raises(RuntimeError, match="SERPAPI_API_KEY"):
        _FakeSerpapi().run({"keywords": ["vegan shoes"]}, ctx)


def test_run_normaliseert_naar_keywords_dict(tmp_path):
    skill = _FakeSerpapi()
    out = skill.run({"keywords": ["vegan shoes"], "geos": ["GB"]}, _ctx(tmp_path))
    kw = out["keywords"]["vegan shoes"]
    assert kw["interest_latest"] == 60
    assert kw["direction"] == "stijgend"
    assert kw["top_related"] == [{"query": "vegan shoes duurzaam", "value": 80}]
    assert kw["rising_related"][0]["breakout"] is True
    assert out["source"] == "serpapi"


def test_run_doet_twee_searches_per_keyword(tmp_path):
    skill = _FakeSerpapi()
    skill.run({"keywords": ["a", "b"], "geos": ["GB"]}, _ctx(tmp_path))
    types = sorted(c["data_type"] for c in skill.calls)
    assert types == ["RELATED_QUERIES", "RELATED_QUERIES", "TIMESERIES", "TIMESERIES"]


def test_run_vangt_fout_per_keyword(tmp_path):
    class _Boom(_FakeSerpapi):
        def _get(self, params):
            raise RuntimeError("503 serpapi down")
    out = _Boom().run({"keywords": ["vegan shoes"], "geos": ["GB"]}, _ctx(tmp_path))
    assert "error" in out["keywords"]["vegan shoes"]
