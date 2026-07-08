"""Tests voor KeywordsEverywhereSkill — geen echte API-calls."""
from __future__ import annotations
import json, os, types
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill

FIXTURE = Path(__file__).parent / "fixtures" / "keywords_everywhere" / "get_keyword_data.json"


def _ctx(key="test-key"):
    ctx = types.SimpleNamespace(settings={})
    if key:
        ctx.settings["KEYWORDS_EVERYWHERE_API_KEY"] = key
    return ctx


def _mock_response(fixture_path=FIXTURE, status=200):
    raw = json.loads(fixture_path.read_text())
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = raw
    resp.raise_for_status = MagicMock()
    return resp


def test_normalizes_response():
    skill = KeywordsEverywhereSkill()
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        mock_post.return_value = _mock_response()
        result = skill.run({"kw": ["digital marketing"]}, _ctx())

    assert result == {
        "source":             "keywords_everywhere",
        "country":            "",                     # default leeg = global (geen 'nl'-default meer)
        "currency":           "eur",
        "data_source":        "gkp",
        "credits_consumed":   1,
        "credits_remaining":  148520,
        "keywords": [
            {
                "keyword":     "digital marketing",
                "vol":         90500,
                "cpc":         9.96,
                "competition": 0.62,
                "trend":       [{"month": "January", "year": 2026, "value": 110000}],
            }
        ],
    }


def test_no_key_fails_closed(monkeypatch):
    monkeypatch.delenv("KEYWORDS_EVERYWHERE_API_KEY", raising=False)
    skill = KeywordsEverywhereSkill()
    with pytest.raises(RuntimeError, match="KEYWORDS_EVERYWHERE_API_KEY"):
        skill.run({"kw": ["test"]}, _ctx(key=None))


def test_http_error_raises():
    skill = KeywordsEverywhereSkill()
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("HTTP 402 Payment Required")
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post", return_value=resp):
        with pytest.raises(Exception, match="402"):
            skill.run({"kw": ["test"]}, _ctx())


def test_too_many_keywords_raises():
    skill = KeywordsEverywhereSkill()
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        with pytest.raises(ValueError, match="max 100"):
            skill.run({"kw": [f"kw{i}" for i in range(101)]}, _ctx())
        mock_post.assert_not_called()


def test_empty_keywords_raises():
    skill = KeywordsEverywhereSkill()
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        with pytest.raises(ValueError, match="leeg"):
            skill.run({"kw": []}, _ctx())
        mock_post.assert_not_called()


def test_unknown_data_source_raises():
    skill = KeywordsEverywhereSkill()
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        with pytest.raises(ValueError, match="data_source"):
            skill.run({"kw": ["test"], "data_source": "xyz"}, _ctx())
        mock_post.assert_not_called()
