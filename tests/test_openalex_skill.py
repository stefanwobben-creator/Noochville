"""Tests voor OpenalexSkill — nep-urlopen, geen netwerk, geen key-waarden in code."""
from __future__ import annotations
import json
import urllib.error
from unittest.mock import patch
import pytest
from nooch_village.skills_impl.openalex import OpenalexSkill, _build_filter


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


# ── Frase-match query-fix (diagnose 2026-07-08) ─────────────────────────────────

def test_meerwoords_term_als_exacte_frase():
    """search=<term> matcht anders losse woorden → de term gaat als exacte frase (quotes) mee."""
    skill = OpenalexSkill()
    captured: list[str] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req.full_url)
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        skill.run({"term": "barefoot shoes", "locale": "en", "limit": 5}, _ctx_with_key())

    assert "search=%22barefoot%20shoes%22" in captured[0]      # frase (aanhalingstekens), niet losse woorden
    assert "sort=cited_by_count:desc" in captured[0]           # citatie-sort blijft behouden


def test_enkelwoord_term_werkt_geen_lege_quotes():
    skill = OpenalexSkill()
    captured: list[str] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req.full_url)
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        result = skill.run({"term": "mycelium", "locale": "en", "limit": 1}, _ctx_with_key())

    assert "search=%22mycelium%22" in captured[0]              # enkel woord: quotes neutraal, correct
    assert "%22%22" not in captured[0]                         # geen dubbele/lege quotes
    assert result["hits"]                                      # levert nog gewoon hits


def test_lege_term_fail_closed_geen_api_call():
    skill = OpenalexSkill()
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        result = skill.run({"term": "   ", "locale": "en"}, _ctx_with_key())   # whitespace → leeg na strip

    assert result.get("error") and calls["n"] == 0            # fail-closed: geen kale API-call, geen ""-frase


# ── Deterministische filters (_build_filter) ────────────────────────────────────
def test_build_filter_filterloos_is_leeg():
    assert _build_filter({"term": "x"}) == ("", None)          # geen filter-veld → filterloos


def test_build_filter_abstract_terms_één_filter_met_pipes():
    fs, err = _build_filter({"abstract_terms": ["ROM", "EMG", "loading rates"]})
    assert err is None and fs == "abstract.search:ROM|EMG|loading rates"   # OR BINNEN één filter


def test_build_filter_from_to_year():
    fs, err = _build_filter({"from_year": 2018, "to_year": 2024})
    assert err is None and fs == "from_publication_date:2018-01-01,to_publication_date:2024-12-31"


def test_build_filter_meerdere_velden_komma_gescheiden():
    fs, err = _build_filter({"work_type": "article", "journal_only": True,
                             "exclude_retracted": True, "min_citations": 10})
    assert err is None
    assert fs == "type:article,primary_location.source.type:journal,is_retracted:false,cited_by_count:>10"


def test_build_filter_pipe_tussen_twee_filters_geweigerd():
    fs, err = _build_filter({"work_type": "article|is_retracted:false"})   # OR over twee filters
    assert fs == "" and err and "twee filters" in err


def test_build_filter_komma_in_waarde_geweigerd():
    fs, err = _build_filter({"abstract_terms": ["loading rates, EMG"]})    # komma zou filters mengen
    assert fs == "" and err and "komma" in err


# ── run(): filter in de URL + in de output, ongeldige combinatie geweigerd ───────
def _capturing_run(payload):
    skill, captured, calls = OpenalexSkill(), [], {"n": 0}
    def fake_urlopen(req, timeout=None):
        calls["n"] += 1; captured.append(req.full_url); return _ok_response()
    with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep"):
        result = skill.run(payload, _ctx_with_key())
    return result, captured, calls


def test_run_filter_in_url_en_output():
    result, captured, _ = _capturing_run(
        {"term": "hennep", "abstract_terms": ["ROM", "EMG"], "from_year": 2019,
         "min_citations": 5, "locale": "en", "limit": 1})
    fs = "abstract.search:ROM|EMG,from_publication_date:2019-01-01,cited_by_count:>5"
    assert result["filter"] == fs                             # reproduceerbaar: HOE er gefilterd is
    assert "filter=" in captured[0] and "abstract.search:ROM|EMG" in captured[0]


def test_run_filterloos_geen_filter_param_in_url():
    result, captured, _ = _capturing_run({"term": "mycelium", "locale": "en", "limit": 1})
    assert "filter=" not in captured[0]                       # filterloos = huidige URL
    assert result["filter"] == ""


def test_run_ongeldige_combinatie_weigert_voor_de_call():
    result, captured, calls = _capturing_run(
        {"term": "x", "work_type": "article|is_retracted:false", "locale": "en"})
    assert result.get("error") and calls["n"] == 0            # geweigerd VÓÓR de API-call
    assert result["filter"] == "" and not captured
