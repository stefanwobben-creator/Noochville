"""Tests voor de provider-volgorde in llm.reason: de getrapte ladder begint goedkoop
(Gemini), valt terug op Anthropic. Geen netwerk: de trede-functies worden vervangen.
De ladder dispatcht met een `model`-kwarg, dus de stubs accepteren `model=None`."""
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
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: "GEMINI")
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None, **kw: "ANTHROPIC")
    assert llm.reason("hoi") == "GEMINI"      # goedkoopste trede (Gemini) wint


def test_valt_terug_op_anthropic_als_de_rest_niets_geeft(monkeypatch):
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None, **kw: "ANTHROPIC")
    assert llm.reason("hoi") == "ANTHROPIC"


def test_none_als_alle_treden_falen(monkeypatch):
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None, **kw: None)
    assert llm.reason("hoi") is None
