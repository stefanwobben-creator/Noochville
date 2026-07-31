"""Tests voor nooch_village/llm.py — timeout-instelling en exception-logging.

Geen importlib.reload nodig: llm.py importeert anthropic en google.genai lazy
(binnenin de functie), dus patch.dict op sys.modules vóór de reason()-aanroep
volstaat. os.getenv() werkt direct met monkeypatched env-vars.

Vijf invarianten:
  1. Anthropic-client wordt aangemaakt met een ruime timeout en streamt zijn antwoord.
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


def _fake_stream(msg=None, exc=None):
    """De context-manager die `client.messages.stream(...)` teruggeeft."""
    ctx = MagicMock()
    ctx.__enter__.return_value = MagicMock(get_final_message=MagicMock(return_value=msg))
    if exc is not None:
        ctx.__enter__.side_effect = exc
    return MagicMock(return_value=ctx)


# ── 1. Anthropic timeout ──────────────────────────────────────────────────────

def test_anthropic_timeout_is_set(monkeypatch):
    """Ruime timeout én streaming. Met de oude 30s haalde een einddocument-call (max_tokens=4000,
    gemeten ~56s op Sonnet) de streep nooit: retries, lege respons, ongewijzigd document."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    mock_client = MagicMock()
    mock_client.messages.stream = _fake_stream(msg=_fake_message("ok"))
    mock_anthropic_cls = MagicMock(return_value=mock_client)

    with patch.dict("sys.modules", {"anthropic": MagicMock(Anthropic=mock_anthropic_cls)}):
        reason("test prompt")

    mock_anthropic_cls.assert_called_once()
    _, kwargs = mock_anthropic_cls.call_args
    assert kwargs.get("timeout") == 180.0, f"Verwacht timeout=180.0, gekregen: {kwargs}"
    mock_client.messages.stream.assert_called_once()          # streamen, niet create()
    mock_client.messages.create.assert_not_called()


# ── 2. Anthropic failure is logged ───────────────────────────────────────────

def test_anthropic_failure_is_logged(monkeypatch, caplog):
    """Exception in Anthropic-call → warning gelogd met foutmelding erin."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    mock_client = MagicMock()
    mock_client.messages.stream = _fake_stream(exc=RuntimeError("verbinding verbroken"))
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


# ── 6. De premium-trede heeft tijd nodig ─────────────────────────────────────

def test_premium_trede_heeft_ruimte_voor_een_lang_antwoord():
    """De 30s van de goedkope tredes is te krap voor waar de premium-trede juist voor wordt gevraagd.

    Gemeten op prod: een einddocument-call op Sonnet (max_tokens=4000) deed er 56s over. Met de oude
    gedeelde timeout sneuvelde die stil — een lege respons is in de ladder geen fout maar 'volgende
    trede', dus je ziet alleen een document dat niet bijwerkt. Ruimte voor 2x de gemeten duur."""
    from nooch_village.llm import _ANTHROPIC_TIMEOUT_S, _HTTP_TIMEOUT_S

    GEMETEN_EINDDOCUMENT_S = 56
    assert _ANTHROPIC_TIMEOUT_S >= 2 * GEMETEN_EINDDOCUMENT_S
    assert _ANTHROPIC_TIMEOUT_S > _HTTP_TIMEOUT_S
