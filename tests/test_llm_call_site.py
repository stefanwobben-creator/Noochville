"""De call_site-parameter op reason(): één centrale INFO-regel per aanroep met label + promptlengte
+ (indien geslaagd) de trede. Default 'onbekend' maakt niet-gelabelde call-sites zichtbaar."""
from __future__ import annotations

import logging

import nooch_village.llm as llm


def _msgs(caplog):
    return " || ".join(r.getMessage() for r in caplog.records)


def test_call_site_in_logregel(monkeypatch, caplog):
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: "OK")
    llm.reset_cooldowns()
    with caplog.at_level(logging.INFO, logger="village.llm"):
        assert llm.reason("hallo wereld", ladder="gemini:x", call_site="mijn_site") == "OK"
    m = _msgs(caplog)
    assert "LLM-call [mijn_site]" in m          # het label
    assert "prompt=12 tekens" in m              # len("hallo wereld") == 12
    assert "gemini:x" in m                      # de trede die antwoordde


def test_call_site_default_onbekend(monkeypatch, caplog):
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: "OK")
    llm.reset_cooldowns()
    with caplog.at_level(logging.INFO, logger="village.llm"):
        assert llm.reason("x", ladder="gemini:x") == "OK"   # géén call_site meegegeven
    assert "LLM-call [onbekend]" in _msgs(caplog)


def test_call_site_bij_geen_antwoord(monkeypatch, caplog):
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: None)   # geen antwoord
    llm.reset_cooldowns()
    with caplog.at_level(logging.INFO, logger="village.llm"):
        assert llm.reason("hoi", ladder="gemini:x", call_site="faalsite") is None
    m = _msgs(caplog)
    assert "LLM-call [faalsite]" in m and "geen antwoord" in m
