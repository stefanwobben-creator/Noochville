"""Tests voor de provider-volgorde in llm.reason: Gemini default, Anthropic fallback.
Geen netwerk: de provider-pogingen worden vervangen."""
from __future__ import annotations

import nooch_village.llm as llm


def test_gemini_timeout_is_in_milliseconden():
    """Vangnet tegen de unit-bug: de SDK wil ms, dus een realistische TLS-handshake
    moet ruim passen. Een waarde < 1000 zou seconden-denken verraden."""
    assert llm._GEMINI_TIMEOUT_MS >= 5_000


def test_geen_keys_geeft_none(monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert llm.reason("hoi") is None


def test_gemini_is_default(monkeypatch):
    monkeypatch.setattr(llm, "_try_gemini", lambda p: "GEMINI")
    monkeypatch.setattr(llm, "_try_anthropic", lambda p: "ANTHROPIC")
    assert llm.reason("hoi") == "GEMINI"      # Gemini wint als default


def test_valt_terug_op_anthropic_als_gemini_niets_geeft(monkeypatch):
    monkeypatch.setattr(llm, "_try_gemini", lambda p: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p: "ANTHROPIC")
    assert llm.reason("hoi") == "ANTHROPIC"


def test_none_als_beide_falen(monkeypatch):
    monkeypatch.setattr(llm, "_try_gemini", lambda p: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p: None)
    assert llm.reason("hoi") is None
