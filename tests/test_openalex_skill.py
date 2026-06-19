"""Tests voor OpenalexSkill — nep-urlopen, geen netwerk, geen key-waarden in code."""
from __future__ import annotations
import json
import urllib.error
from unittest.mock import patch
import pytest
from nooch_village.skills_impl.openalex import OpenalexSkill


class _Ctx:
    def __init__(self, settings=None):
        self.settings = settings or {}


class _FakeResp:
    """Nep-HTTP-response die als context manager werkt."""
    def __init__(self, data: dict):
        self._body = json.dumps(data).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _ok_response(results=None) -> _FakeResp:
    results = results or [_fake_work()]
    return _FakeResp({"results": results, "meta": {"count": len(results)}})


def _fake_work() -> dict:
    return {
        "title":                    "Sustainable Footwear Lifecycle",
        "publication_year":         2022,
        "cited_by_count":           57,
        "abstract_inverted_index":  {"vegan": [0], "materials": [1]},
        "primary_topic":            {"display_name": "Sustainability"},
        "authorships":              [{"author": {"display_name": "A. Researcher"}}],
    }


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url="", code=code, msg="", hdrs=None, fp=None)


def _ctx_with_key(key: str = "test-sentinel-key") -> _Ctx:
    return _Ctx(settings={"OPENALEX_API_KEY": key})


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_ontbrekende_key_raised_runtime_error():
    skill = OpenalexSkill()
    ctx   = _Ctx(settings={})
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="OPENALEX_API_KEY"):
            skill.run({"term": "vegan shoes", "locale": "en"}, ctx)


def test_api_key_zit_in_aangeroepen_url():
    skill = OpenalexSkill()
    ctx   = _ctx_with_key("test-sentinel-key")
    captured: list[str] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req.full_url)
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        skill.run({"term": "vegan", "locale": "en", "limit": 1}, ctx)

    assert captured, "urlopen is niet aangeroepen"
    assert "api_key=test-sentinel-key" in captured[0]


def test_429_gevolgd_door_200_levert_hits():
    skill  = OpenalexSkill()
    ctx    = _ctx_with_key()
    calls  = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429)
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        result = skill.run({"term": "sustainability", "locale": "en", "limit": 1}, ctx)

    assert "hits" in result
    assert len(result["hits"]) >= 1
    assert calls["n"] == 2


def test_hits_structuur_ongewijzigd():
    skill = OpenalexSkill()
    ctx   = _ctx_with_key()

    with patch("urllib.request.urlopen", lambda req, timeout=None: _ok_response()), \
         patch("time.sleep"):
        result = skill.run({"term": "vegan shoes", "locale": "en", "limit": 1}, ctx)

    assert "hits" in result
    hit = result["hits"][0]
    for key in ("source", "locale", "title", "authors", "year", "citations", "topic", "abstract"):
        assert key in hit, f"verwachte key '{key}' ontbreekt in hit"
    assert hit["source"]    == "openalex"
    assert hit["locale"]    == "en"
    assert hit["title"]     == "Sustainable Footwear Lifecycle"
    assert hit["citations"] == 57
