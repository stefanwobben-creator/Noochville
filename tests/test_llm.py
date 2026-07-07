"""Tests voor nooch_village/llm.py — timeout-instelling en exception-logging.

Geen importlib.reload nodig: llm.py importeert anthropic en google.genai lazy
(binnenin de functie), dus patch.dict op sys.modules vóór de reason()-aanroep
volstaat. os.getenv() werkt direct met monkeypatched env-vars.

Vijf invarianten:
  1. Anthropic-client wordt aangemaakt met timeout=30.0.
  2. Exception in Anthropic-aanroep → warning gelogd (geen bare swallow).
  3. Gemini-aanroep gebruikt HttpOptions(timeout=30000) — milliseconden, niet seconden.
  4. Exception in Gemini-aanroep → warning gelogd.
  5. Geen key → reason() geeft None terug.
"""
from __future__ import annotations
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nooch_village.llm import reason


def _fake_message(text: str):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


# ── 1. Anthropic timeout ──────────────────────────────────────────────────────

def test_anthropic_timeout_is_set(monkeypatch):
    """Anthropic client wordt aangemaakt met timeout=30.0."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _fake_message("ok")
    mock_anthropic_cls = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=mock_anthropic_cls)}):
        reason("test prompt")

    mock_anthropic_cls.assert_called_once()
    _, kwargs = mock_anthropic_cls.call_args
    assert kwargs.get("timeout") == 30.0, f"Verwacht timeout=30.0, gekregen: {kwargs}"


# ── 2. Anthropic failure is logged ───────────────────────────────────────────

def test_anthropic_failure_is_logged(monkeypatch, caplog):
    """Exception in Anthropic-call → warning gelogd met foutmelding erin."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("verbinding verbroken")
    mock_anthropic_cls = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=mock_anthropic_cls)}):
        with caplog.at_level(logging.WARNING):
            result = reason("test prompt")

    assert result is None
    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("Anthropic" in m and "verbinding verbroken" in m for m in messages), (
        f"Verwacht warning met 'Anthropic' en 'verbinding verbroken'; gelogd: {messages}"
    )


# ── 3. Gemini timeout ─────────────────────────────────────────────────────────

def test_gemini_timeout_is_set(monkeypatch):
    """Gemini-aanroep gebruikt HttpOptions(timeout=30000) — MS, niet seconden (unit-bug-vangnet)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    fake_http_options = MagicMock()
    fake_config = MagicMock()
    fake_types = MagicMock()
    fake_types.HttpOptions.return_value = fake_http_options
    fake_types.GenerateContentConfig.return_value = fake_config

    captured = {}

    def fake_generate(model, contents, config=None):
        captured["config"] = config
        return SimpleNamespace(text="gemini-antwoord")

    mock_models = MagicMock()
    mock_models.generate_content.side_effect = fake_generate
    mock_genai_client = MagicMock()
    mock_genai_client.models = mock_models
    fake_genai = MagicMock()
    fake_genai.Client.return_value = mock_genai_client
    fake_genai.types = fake_types  # `from google.genai import types` pakt .types-attribuut

    with patch.dict("sys.modules", {
        "google": MagicMock(genai=fake_genai),
        "google.genai": fake_genai,
        "google.genai.types": fake_types,
    }):
        reason("test prompt")

    fake_types.HttpOptions.assert_called_once_with(timeout=30000)   # ms, niet seconden
    fake_types.GenerateContentConfig.assert_called_once_with(
        max_output_tokens=700, http_options=fake_http_options)   # default token-cap
    assert captured.get("config") is fake_config


# ── 4. Gemini failure is logged ───────────────────────────────────────────────

def test_gemini_failure_is_logged(monkeypatch, caplog):
    """Exception in Gemini-call → warning gelogd met foutmelding erin."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    mock_models = MagicMock()
    mock_models.generate_content.side_effect = RuntimeError("quota overschreden")
    mock_genai_client = MagicMock()
    mock_genai_client.models = mock_models
    fake_genai = MagicMock()
    fake_genai.Client.return_value = mock_genai_client

    with patch.dict("sys.modules", {
        "google": MagicMock(genai=fake_genai),
        "google.genai": fake_genai,
        "google.genai.types": MagicMock(),
    }):
        with caplog.at_level(logging.WARNING):
            result = reason("test prompt")

    assert result is None
    messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("Gemini" in m and "quota overschreden" in m for m in messages), (
        f"Verwacht warning met 'Gemini' en 'quota overschreden'; gelogd: {messages}"
    )


# ── 5. Geen key → None ────────────────────────────────────────────────────────

def test_reason_returns_none_when_no_key(monkeypatch):
    """Geen API-key → reason() geeft None terug zonder exception."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    assert reason("test prompt") is None
