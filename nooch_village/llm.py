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
import threading
import time

log = logging.getLogger("village.llm")

_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"

# LET OP: de google-genai SDK verwacht de timeout in MILLISECONDEN, niet seconden.
# 30 (ms) liet elke call direct timeouten op de TLS-handshake ("SSL timeout").
_GEMINI_TIMEOUT_MS = 30_000  # 30 seconden

# Tempo: het dorp smeert zijn LLM-werk uit zodat het onder de gratis Gemini-limiet
# blijft (geen 429-muur), in plaats van alles in één keer te proppen. Instelbaar via
# LLM_MAX_PER_MINUTE (0 = geen limiet). Backoff voor de retry bij een rate-limit.
_DEFAULT_MAX_PER_MINUTE = 5
_RATE_LIMIT_BACKOFF_S = 20.0
_RATE_LIMIT_MARKERS = ("429", "resource_exhausted", "rate limit", "quota", "exhausted")


def _is_rate_limit(exc: Exception) -> bool:
    """Herken een rate-limit/quota-fout aan de boodschap. Conservatief: alleen bekende markers."""
    s = str(exc).lower()
    return any(m in s for m in _RATE_LIMIT_MARKERS)


class RateLimiter:
    """Glijdend-venster begrenzer: hooguit `max_per_minute` aanroepen per `window` seconden.

    acquire() blokkeert (slaapt) tot er een plek vrij is, en blokkeert daarbij alleen
    het draadje van de aanroepende inwoner — de rest van het dorp loopt door. Thread-safe.
    Klok en sleep zijn injecteerbaar zodat tests deterministisch zijn zonder echt te wachten.
    max_per_minute <= 0 betekent: geen limiet.
    """

    def __init__(self, max_per_minute: int, *, clock=time.monotonic,
                 sleep=time.sleep, window: float = 60.0):
        self.max = max_per_minute
        self.window = window
        self._clock = clock
        self._sleep = sleep
        self._calls: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self.max <= 0:
            return
        while True:
            with self._lock:
                now = self._clock()
                cutoff = now - self.window
                self._calls = [t for t in self._calls if t > cutoff]
                if len(self._calls) < self.max:
                    self._calls.append(now)
                    return
                wait = self._calls[0] + self.window - now
            self._sleep(max(wait, 0.0))


def _build_limiter() -> RateLimiter:
    try:
        mpm = int(os.getenv("LLM_MAX_PER_MINUTE", str(_DEFAULT_MAX_PER_MINUTE)))
    except ValueError:
        mpm = _DEFAULT_MAX_PER_MINUTE
    return RateLimiter(mpm)


# Procesbreed, gedeeld over alle inwoner-draadjes: één rij voor het ene LLM-poortje.
LIMITER = _build_limiter()


def _try_gemini(prompt: str, *, sleep=time.sleep) -> str | None:
    """Probeer Gemini (default). Eén retry op een transiente fout (bijv. SSL-timeout).
    Bij een rate-limit (429) eerst even wachten vóór de retry, want direct opnieuw
    vragen blijft binnen dezelfde minuut en is zinloos."""
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
            # Alleen vóór een volgende poging wachten, en alleen bij een rate-limit.
            if poging == 0 and _is_rate_limit(exc):
                log.info("rate-limit gedetecteerd; %.0fs wachten voor de retry",
                         _RATE_LIMIT_BACKOFF_S)
                sleep(_RATE_LIMIT_BACKOFF_S)
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
    Geen werkende provider → None (caller valt terug op heuristiek).

    Alle LLM-aanroepen van het dorp lopen door dit ene poortje en worden hier in de
    tijd uitgesmeerd (LIMITER), zodat het dorp onder de gratis Gemini-limiet blijft."""
    LIMITER.acquire()
    return _try_gemini(prompt) or _try_anthropic(prompt)
