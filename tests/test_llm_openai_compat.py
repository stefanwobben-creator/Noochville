"""Tests voor de generieke OpenAI-compatibele adapter (`_try_openai_compatible`) + registry `_OPENAI_COMPAT`.

Eén generieke trede bedient alle vendors met een OpenAI-compatibele /chat/completions-API. Mistral is
een dunne delegator ernaartoe (gedragsgelijk); openai/openrouter zijn pure config. Geen netwerk:
`urllib.request.urlopen` wordt vervangen door een fake."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

import pytest

import nooch_village.llm as llm

_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
             "MISTRAL_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY")


class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(payload, capture=None):
    def _f(req, timeout=None):
        if capture is not None:
            capture["url"] = req.full_url
            capture["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(payload)
    return _f


def _ok(text="ANTWOORD"):
    return {"choices": [{"message": {"content": text}}]}


# ── registry ─────────────────────────────────────────────────────────────────
def test_registry_bevat_de_drie_vendors():
    assert set(llm._OPENAI_COMPAT) == {"mistral", "openai", "openrouter"}
    assert llm._OPENAI_COMPAT["mistral"] == ("https://api.mistral.ai/v1", "MISTRAL_API_KEY")
    assert llm._OPENAI_COMPAT["openai"] == ("https://api.openai.com/v1", "OPENAI_API_KEY")
    assert llm._OPENAI_COMPAT["openrouter"] == ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY")


# ── key/model-afhandeling ────────────────────────────────────────────────────
def test_geen_key_geeft_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm._try_openai_compatible("openai", "hi", model="gpt-x") is None


def test_pure_config_zonder_model_wordt_overgeslagen(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert llm._try_openai_compatible("openai", "hi") is None   # geen model → overslaan


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-env")
    cap = {}
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_ok(), cap))
    llm._try_openai_compatible("openai", "hi")                  # geen expliciet model → uit env
    assert cap["body"]["model"] == "gpt-env"


def test_mistral_default_model(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    cap = {}
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_ok(), cap))
    llm._try_openai_compatible("mistral", "hi")                 # geen model/env → vendor-default
    assert cap["body"]["model"] == llm._DEFAULT_MISTRAL_MODEL


# ── happy path: juiste URL + body per vendor ─────────────────────────────────
def test_juiste_url_en_body(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    cap = {}
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_ok("HOI"), cap))
    out = llm._try_openai_compatible("openrouter", "vraag", model="meta/llama", max_tokens=42)
    assert out == "HOI"
    assert cap["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert cap["body"]["model"] == "meta/llama" and cap["body"]["max_tokens"] == 42
    assert cap["body"]["messages"] == [{"role": "user", "content": "vraag"}]
    assert "response_format" not in cap["body"]                 # json_mode uit → geen response_format


def test_json_mode_zet_response_format(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    cap = {}
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_ok(), cap))
    llm._try_openai_compatible("openai", "hi", model="gpt", json_mode=True)
    assert cap["body"]["response_format"] == {"type": "json_object"}


# ── foutgedrag: 429 → _RateLimit ─────────────────────────────────────────────
def test_http_429_raise_ratelimit(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    def _boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    with pytest.raises(llm._RateLimit):
        llm._try_openai_compatible("openai", "hi", model="gpt")


def test_http_500_geeft_none(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    def _boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert llm._try_openai_compatible("openai", "hi", model="gpt") is None


# ── Mistral = dunne delegator (gedragsgelijk) ────────────────────────────────
def test_mistral_delegeert_naar_generic(monkeypatch):
    seen = {}

    def _fake(vendor, prompt, *, model=None, max_tokens=700, json_mode=False):
        seen.update(vendor=vendor, prompt=prompt, model=model, max_tokens=max_tokens, json_mode=json_mode)
        return "X"

    monkeypatch.setattr(llm, "_try_openai_compatible", _fake)
    assert llm._try_mistral("hoi", model="m", max_tokens=99, json_mode=True) == "X"
    assert seen == {"vendor": "mistral", "prompt": "hoi", "model": "m", "max_tokens": 99, "json_mode": True}


def test_mistral_en_openai_zelfde_parse(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_ok("ZELFDE")))
    a = llm._try_mistral("hi", model="mistral-small-latest")
    b = llm._try_openai_compatible("openai", "hi", model="gpt")
    assert a == b == "ZELFDE"


# ── routing in _call_tier ────────────────────────────────────────────────────
def test_call_tier_routeert_openrouter_naar_generic(monkeypatch):
    seen = {}
    monkeypatch.setattr(llm, "_try_openai_compatible",
                        lambda v, p, **kw: (seen.update(vendor=v, model=kw.get("model")), "R")[1])
    assert llm._call_tier("openrouter", "meta/x", "hi") == "R"
    assert seen == {"vendor": "openrouter", "model": "meta/x"}


def test_call_tier_mistral_via_named_seam(monkeypatch):
    # mistral houdt zijn named seam (getattr) zodat bestaande monkeypatches blijven werken
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: "VIA_NAAM")
    assert llm._call_tier("mistral", "m", "hi") == "VIA_NAAM"


def test_openai_en_openrouter_via_ladder(monkeypatch):
    # end-to-end door reason(): een ladder met alleen openrouter, key + fake HTTP → antwoord
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(_ok("LADDER")))
    llm.reset_cooldowns()
    assert llm.reason("hi", ladder="openrouter:meta/llama") == "LADDER"


# ── de samenvattende logregel splitst 3 uitkomsten: geen sleutel / lege respons / fout ───────────
def _msgs(caplog):
    return " || ".join(r.getMessage() for r in caplog.records)


def test_summary_variant_geen_sleutel(monkeypatch, caplog):
    for v in _KEY_VARS:
        monkeypatch.delenv(v, raising=False)
    llm.reset_cooldowns()
    with caplog.at_level(logging.INFO, logger="village.llm"):
        assert llm.reason("hi", ladder="openai:gpt-x") is None
    m = _msgs(caplog)
    assert "geen sleutel" in m                       # per-trede + samenvatting
    assert "lege respons" not in m and "fout (zie warning)" not in m


def test_summary_variant_lege_respons(monkeypatch, caplog):
    for v in _KEY_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")        # wél een sleutel...
    monkeypatch.setattr(llm, "_try_openai_compatible", lambda vendor, p, **kw: "")  # ...maar lege respons
    llm.reset_cooldowns()
    with caplog.at_level(logging.INFO, logger="village.llm"):
        assert llm.reason("hi", ladder="openai:gpt-x") is None
    m = _msgs(caplog)
    assert "lege respons" in m
    assert "geen sleutel" not in m and "fout (zie warning)" not in m


def test_summary_variant_fout(monkeypatch, caplog):
    for v in _KEY_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    def _boom(vendor, p, **kw):
        raise RuntimeError("kapot")

    monkeypatch.setattr(llm, "_try_openai_compatible", _boom)
    llm.reset_cooldowns()
    with caplog.at_level(logging.INFO, logger="village.llm"):
        assert llm.reason("hi", ladder="openai:gpt-x") is None
    m = _msgs(caplog)
    assert "fout (zie warning)" in m                  # samenvatting verwijst naar de warning
    assert any("onverwacht gefaald" in r.getMessage() and r.levelno >= logging.WARNING
               for r in caplog.records)               # en de warning zelf staat er
    assert "geen sleutel" not in m and "lege respons" not in m
