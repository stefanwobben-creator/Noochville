"""Tests voor PlausibleSkill — fixture-gebaseerd, geen echte API-calls."""
from __future__ import annotations
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from nooch_village.skills_impl.plausible import PlausibleSkill

_FIXTURES = Path(__file__).parent / "fixtures" / "plausible"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


def _ctx():
    return SimpleNamespace(settings={
        "PLAUSIBLE_API_KEY": "test-key",
        "PLAUSIBLE_SITE_ID": "nooch.earth",
    })


def _mock_get(url, **kwargs):
    params = kwargs.get("params", {})
    prop   = params.get("property", "")
    resp   = MagicMock()
    resp.raise_for_status = MagicMock()
    if "aggregate" in url:
        resp.json.return_value = _load("aggregate.json")
    elif prop == "event:page":
        resp.json.return_value = _load("top_pages.json")
    elif prop == "visit:source":
        resp.json.return_value = _load("sources.json")
    elif prop == "visit:country":
        resp.json.return_value = _load("countries.json")
    elif prop == "visit:utm_source":
        resp.json.return_value = _load("utm_sources.json")
    else:
        resp.json.return_value = {"results": []}
    return resp


class TestPlausibleSkillHappyPath:
    def test_results_visitors_value_leesbaar(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_mock_get):
            result = PlausibleSkill().run({}, _ctx())
        visitors = result["results"]["visitors"]["value"]
        assert isinstance(visitors, int)
        assert isinstance(result["results"]["visit_duration"]["value"], (int, float))

    def test_top_pages_aanwezig_en_gevuld(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_mock_get):
            result = PlausibleSkill().run({}, _ctx())
        assert "top_pages" in result
        assert len(result["top_pages"]) > 0
        assert result["top_pages"][0]["page"] == "/"

    def test_sources_aanwezig_en_gevuld(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_mock_get):
            result = PlausibleSkill().run({}, _ctx())
        assert "sources" in result
        assert any(r["source"] == "Google" for r in result["sources"])

    def test_countries_aanwezig_en_gevuld(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_mock_get):
            result = PlausibleSkill().run({}, _ctx())
        assert "countries" in result
        assert any(r["country"] == "NL" for r in result["countries"])

    def test_utm_sources_aanwezig_en_gevuld(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_mock_get):
            result = PlausibleSkill().run({}, _ctx())
        assert "utm_sources" in result
        assert any(r["utm_source"] == "bluemarble" for r in result["utm_sources"])


class TestPlausibleSkillResilience:
    def test_falende_breakdown_geeft_lege_lijst_results_intact(self):
        call_count = 0

        def _mock_get_met_fout(url, **kwargs):
            nonlocal call_count
            call_count += 1
            params = kwargs.get("params", {})
            prop   = params.get("property", "")
            resp   = MagicMock()
            resp.raise_for_status = MagicMock()
            if "aggregate" in url:
                resp.json.return_value = _load("aggregate.json")
                return resp
            if prop == "event:page":
                raise ConnectionError("netwerk timeout")
            resp.json.return_value = _load("sources.json") if prop == "visit:source" else {"results": []}
            return resp

        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=_mock_get_met_fout):
            result = PlausibleSkill().run({}, _ctx())

        # Aggregate intact
        assert isinstance(result["results"]["visitors"]["value"], int)
        # Falende breakdown geeft []
        assert result["top_pages"] == []
        # Overige breakdowns onaangetast
        assert len(result["sources"]) > 0


class TestPlausibleSkillDagwaarde:
    def _mock(self, dag_value=7, dag_faalt=False):
        def _get(url, **kwargs):
            params = kwargs.get("params", {})
            resp = MagicMock(); resp.raise_for_status = MagicMock()
            if "aggregate" in url and params.get("period") == "day":
                if dag_faalt:
                    raise ConnectionError("dag-call down")
                resp.json.return_value = {"results": {"visitors": {"value": dag_value}}}
            elif "aggregate" in url:
                resp.json.return_value = _load("aggregate.json")
            else:
                resp.json.return_value = {"results": []}
            return resp
        return _get

    def test_visitors_day_losse_dagwaarde_vorige_dag(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=self._mock(7)):
            result = PlausibleSkill().run({}, _ctx())
        import datetime as dt
        gisteren = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
        assert result["visitors_day"] == {"date": gisteren, "value": 7}

    def test_visitors_day_falen_is_niet_kritiek(self):
        with patch("nooch_village.skills_impl.plausible.requests.get", side_effect=self._mock(dag_faalt=True)):
            result = PlausibleSkill().run({}, _ctx())
        assert isinstance(result["results"]["visitors"]["value"], int)   # 7d-call intact
        assert result["visitors_day"]["value"] is None                   # dagwaarde faalt closed
