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


def test_unknown_data_source_valt_terug_op_default():
    """Onbekende bron crasht niet meer (skill voor álle rollen): stil terug op de vaste bron,
    zodat een rol-gok als 'xyz' de puls niet meer laat falen."""
    skill = KeywordsEverywhereSkill()
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        mock_post.return_value = _mock_response()
        result = skill.run({"kw": ["test"], "data_source": "xyz"}, _ctx())
    assert result["data_source"] == "gkp"          # default, geen crash
    mock_post.assert_called_once()


def test_synoniem_google_wordt_gkp():
    """De klassieke rol-gok 'google' wordt genormaliseerd naar de echte KE-code 'gkp'."""
    skill = KeywordsEverywhereSkill()
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        mock_post.return_value = _mock_response()
        result = skill.run({"kw": ["test"], "data_source": "google"}, _ctx())
    assert result["data_source"] == "gkp"


def test_settings_default_wint_bij_lege_input():
    """x-boven-y-beleid: de vaste bron uit settings geldt als de payload er geen meegeeft."""
    skill = KeywordsEverywhereSkill()
    ctx = _ctx()
    ctx.settings["keywordseverywhere_data_source"] = "cli"
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post") as mock_post:
        mock_post.return_value = _mock_response()
        result = skill.run({"kw": ["test"]}, ctx)      # geen data_source in payload
    assert result["data_source"] == "cli"


def test_resolve_data_source_helper():
    from nooch_village.skills_impl.keywords_everywhere import resolve_data_source
    assert resolve_data_source("google") == ("gkp", None)
    assert resolve_data_source("Clickstream") == ("cli", None)
    assert resolve_data_source("") == ("gkp", None)
    bron, waarschuwing = resolve_data_source("xyz", "gkp")
    assert bron == "gkp" and "xyz" in waarschuwing
    assert resolve_data_source("", "cli") == ("cli", None)   # aliasbare default genormaliseerd
