"""Optionele LLM-redenering voor het dorp.

Gemini is de **default** (goedkoop, ruime gratis tier, toereikend voor duiding/classificatie);
Anthropic is de fallback voor als Gemini niet beschikbaar is. Geen werkende provider → None,
dan vallen de callers terug op hun deterministische heuristiek.

Modelnamen zijn instelbaar via env (GEMINI_MODEL / ANTHROPIC_MODEL) zodat je een nieuwere
versie kunt kiezen zonder code te wijzigen.
"""
from __future__ import annotations
import logging
import os

log = logging.getLogger("village.llm")

_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"

# LET OP: de google-genai SDK verwacht de timeout in MILLISECONDEN, niet seconden.
# 30 (ms) liet elke call direct timeouten op de TLS-handshake ("SSL timeout").
_GEMINI_TIMEOUT_MS = 30_000  # 30 seconden


def _try_gemini(prompt: str) -> str | None:
    """Probeer Gemini (default). Eén retry op een transiente fout (bijv. SSL-timeout)."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL)
    for poging in range(2):
        try:
            from google import genai
            from google.genai import types as genai_types
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    http_options=genai_types.HttpOptions(timeout=_GEMINI_TIMEOUT_MS)
                ),
            )
            text = (resp.text or "").strip()
            if text:
                log.debug("LLM via Gemini (%s)", model)
                return text
            return None
        except Exception as exc:
            log.warning("LLM Gemini poging %d/2 faalde: %s", poging + 1, exc)
    return None


def _try_anthropic(prompt: str) -> str | None:
    """Fallback: Anthropic (duurder; alleen als Gemini niets gaf)."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.getenv("ANTHROPIC_MODEL", _DEFAULT_ANTHROPIC_MODEL)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=30.0)
        msg = client.messages.create(
            model=model, max_tokens=700,
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content
                       if getattr(b, "type", "") == "text").strip()
        if text:
            log.debug("LLM via Anthropic (%s)", model)
            return text
        return None
    except Exception as exc:
        log.warning("LLM Anthropic faalde: %s", exc)
        return None


def reason(prompt: str) -> str | None:
    """Optionele LLM-redenering. Gemini eerst (default), dan Anthropic als fallback.
    Geen werkende provider → None (caller valt terug op heuristiek)."""
    return _try_gemini(prompt) or _try_anthropic(prompt)
