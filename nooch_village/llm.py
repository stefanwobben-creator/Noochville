"""Optionele LLM-redenering voor het dorp — een getrapte ladder, goedkoop eerst.

Alle LLM-werk loopt door één poortje: `reason(prompt)`. Dat poortje probeert een
**ladder** van modellen, trede voor trede, van goedkoop naar duur, tot er één een
antwoord geeft. Zo blijft het dorp betrouwbaar (valt een provider weg of is een gratis
dagcap op, dan rolt het werk door naar de volgende trede) én goedkoop (de dure treden
zijn alleen een laatste vangnet).

Default-ladder (instelbaar via env `LLM_LADDER`, formaat `vendor:model,vendor:model`):
  1. gemini:gemini-2.5-flash-lite   — ruime gratis tier, goedkoopste betaald
  2. mistral:mistral-small-latest   — onafhankelijke, goedkope provider (slaat over zonder key)
  3. gemini:gemini-2.5-flash        — pay-as-you-go, betere kwaliteit
  4. anthropic:claude-haiku-4-5-20251001 — betrouwbaar vangnet bij escalatie

Sonnet zit bewust NIET in de auto-ladder (te duur; het oude kostenlek). Wil je voor een
specifieke skill toch premium-kwaliteit, geef dan een eigen ladder mee via
`reason(prompt, ladder="anthropic:claude-sonnet-4-6")`.

Ontwerpregels:
- **Fail-closed.** Geen werkende trede → None; de caller valt terug op zijn heuristiek.
- **Geen sleutel = trede overslaan.** Zo kun je met alleen Gemini + Anthropic starten en
  de Mistral-trede later activeren door enkel een key te zetten.
- **Daily-cap-aware skip.** Geeft een trede een rate-limit/quota-fout, dan zetten we die
  trede in cooldown (`LLM_TIER_COOLDOWN_S`, default 30 min) en gaan direct door naar de
  volgende — we blijven niet wachten op een uitgeputte gratis dagcap.
- **Throttle.** De per-minuut-begrenzer (`LIMITER`) blijft staan zodat we niet binnen één
  minuut tegen de muur lopen.
"""
from __future__ import annotations
import logging
import os
import sys
import threading
import time

log = logging.getLogger("village.llm")

# Defaults: goedkoop-by-default, ook buiten de ladder (kill het Sonnet-lek aan de bron).
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
_DEFAULT_MISTRAL_MODEL = "mistral-small-latest"
_DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# De getrapte ladder: goedkoop → duur. Instelbaar via env LLM_LADDER.
_DEFAULT_LADDER = (
    "gemini:gemini-2.5-flash-lite",
    "mistral:mistral-small-latest",
    "gemini:gemini-2.5-flash",
    "anthropic:claude-haiku-4-5-20251001",
)

# LET OP: de google-genai SDK verwacht de timeout in MILLISECONDEN, niet seconden.
# 30 (ms) liet elke call direct timeouten op de TLS-handshake ("SSL timeout").
_GEMINI_TIMEOUT_MS = 30_000  # 30 seconden
_HTTP_TIMEOUT_S = 30.0       # Mistral/Anthropic in seconden

# Tempo: het dorp smeert zijn LLM-werk uit zodat het onder de gratis limiet blijft
# (geen 429-muur). Instelbaar via LLM_MAX_PER_MINUTE (0 = geen limiet).
_DEFAULT_MAX_PER_MINUTE = 5
_RATE_LIMIT_MARKERS = ("429", "resource_exhausted", "rate limit", "quota", "exhausted")

# Cooldown: hoelang een trede wordt overgeslagen na een rate-limit/quota-fout.
_DEFAULT_TIER_COOLDOWN_S = 1800.0  # 30 minuten


class _RateLimit(Exception):
    """Interne marker: deze trede zit aan zijn rate-limit/quota. Triggert cooldown + door."""


def _is_rate_limit(exc: Exception) -> bool:
    """Herken een rate-limit/quota-fout aan de boodschap. Conservatief: alleen bekende markers."""
    s = str(exc).lower()
    return any(m in s for m in _RATE_LIMIT_MARKERS)


# ── Throttle: glijdend-venster begrenzer ──────────────────────────────────────

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


# ── Cooldown: een uitgeputte trede tijdelijk overslaan ────────────────────────

_COOLDOWN: dict[str, float] = {}        # tier-string → monotone tijd tot wanneer overslaan
_COOLDOWN_LOCK = threading.Lock()


def _cooldown_seconds() -> float:
    try:
        return float(os.getenv("LLM_TIER_COOLDOWN_S", str(_DEFAULT_TIER_COOLDOWN_S)))
    except ValueError:
        return _DEFAULT_TIER_COOLDOWN_S


def _in_cooldown(tier: str, *, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _COOLDOWN_LOCK:
        until = _COOLDOWN.get(tier)
        if until is None:
            return False
        if now >= until:
            _COOLDOWN.pop(tier, None)
            return False
        return True


def _set_cooldown(tier: str, *, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _COOLDOWN_LOCK:
        _COOLDOWN[tier] = now + _cooldown_seconds()


def reset_cooldowns() -> None:
    """Wis alle cooldowns (voor tests en voor een handmatige herstart van de ladder)."""
    with _COOLDOWN_LOCK:
        _COOLDOWN.clear()


# ── De vendor-treden ──────────────────────────────────────────────────────────

def _try_gemini(prompt: str, *, model: str | None = None, sleep=time.sleep) -> str | None:
    """Probeer Gemini. Eén retry bij een transiente fout (bijv. SSL-timeout).
    Bij een rate-limit/quota → `_RateLimit` (de ladder zet de trede in cooldown en gaat door)."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    model = model or os.getenv("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL)
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
            log.warning("LLM Gemini (%s) poging %d/2 faalde: %s", model, poging + 1, exc)
            if _is_rate_limit(exc):
                raise _RateLimit(str(exc)) from exc
            # transiente fout: nog één keer proberen, zonder lang wachten
    return None


def _try_mistral(prompt: str, *, model: str | None = None) -> str | None:
    """Probeer Mistral via de OpenAI-compatibele chat-completions-API (dependency-vrij,
    enkel urllib). Geen key → trede overslaan. Rate-limit/quota → `_RateLimit`."""
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        return None
    model = model or os.getenv("MISTRAL_MODEL", _DEFAULT_MISTRAL_MODEL)
    import json
    import urllib.error
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if text:
            log.debug("LLM via Mistral (%s)", model)
            return text
        return None
    except urllib.error.HTTPError as exc:
        log.warning("LLM Mistral (%s) faalde: HTTP %s", model, exc.code)
        if exc.code == 429:
            raise _RateLimit(f"HTTP 429 {exc}") from exc
        return None
    except Exception as exc:
        log.warning("LLM Mistral (%s) faalde: %s", model, exc)
        if _is_rate_limit(exc):
            raise _RateLimit(str(exc)) from exc
        return None


def _try_anthropic(prompt: str, *, model: str | None = None) -> str | None:
    """Probeer Anthropic (duur; alleen als vangnet in de ladder).
    Rate-limit/quota → `_RateLimit`."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = model or os.getenv("ANTHROPIC_MODEL", _DEFAULT_ANTHROPIC_MODEL)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=_HTTP_TIMEOUT_S)
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
        log.warning("LLM Anthropic (%s) faalde: %s", model, exc)
        if _is_rate_limit(exc):
            raise _RateLimit(str(exc)) from exc
        return None


# Vendor-naam → naam van de trede-functie. We dispatchen via getattr(module, naam) zodat
# een test die `_try_gemini` monkeypatcht ook echt door de ladder wordt opgepikt.
_VENDOR_FNS = {
    "gemini": "_try_gemini",
    "mistral": "_try_mistral",
    "anthropic": "_try_anthropic",
}


def _call_tier(vendor: str, model: str | None, prompt: str) -> str | None:
    name = _VENDOR_FNS.get(vendor)
    if name is None:
        log.warning("onbekende LLM-vendor in ladder: %r (trede overgeslagen)", vendor)
        return None
    fn = getattr(sys.modules[__name__], name, None)
    if fn is None:
        return None
    return fn(prompt, model=model)


def _parse_ladder(raw: str) -> list[tuple[str, str | None]]:
    """Parse een ladder-string `vendor:model,vendor:model` → [(vendor, model|None)]."""
    out: list[tuple[str, str | None]] = []
    for spec in raw.split(","):
        spec = spec.strip()
        if not spec:
            continue
        if ":" in spec:
            vendor, model = spec.split(":", 1)
            out.append((vendor.strip().lower(), model.strip() or None))
        else:
            out.append((spec.strip().lower(), None))   # alleen vendor → vendor-default-model
    return out


def _ladder() -> list[tuple[str, str | None]]:
    raw = os.getenv("LLM_LADDER", "").strip()
    return _parse_ladder(raw) if raw else _parse_ladder(",".join(_DEFAULT_LADDER))


def reason(prompt: str, *, ladder: str | None = None) -> str | None:
    """Optionele LLM-redenering via de getrapte ladder (goedkoop → duur).

    Loopt de treden af tot er één een antwoord geeft. Een trede zonder sleutel of in
    cooldown wordt overgeslagen; een rate-limit zet de trede in cooldown en gaat door.
    Geen werkende trede → None (de caller valt terug op zijn heuristiek).

    `ladder`: optioneel een eigen ladder-string voor een specifieke (premium) skill,
    bijv. "anthropic:claude-sonnet-4-6". Default = env LLM_LADDER of de standaardladder.

    Alle LLM-aanroepen van het dorp lopen door dit ene poortje en worden hier in de tijd
    uitgesmeerd (LIMITER), zodat het dorp onder de gratis limiet blijft."""
    LIMITER.acquire()
    steps = _parse_ladder(ladder) if ladder else _ladder()
    for vendor, model in steps:
        tier = f"{vendor}:{model or 'default'}"
        if _in_cooldown(tier):
            log.debug("LLM-trede %s in cooldown — overgeslagen", tier)
            continue
        try:
            out = _call_tier(vendor, model, prompt)
        except _RateLimit as exc:
            log.info("LLM-trede %s tegen rate-limit (%s) — cooldown + door naar volgende",
                     tier, exc)
            _set_cooldown(tier)
            continue
        except Exception as exc:   # defensief: een trede mag de ladder nooit laten crashen
            log.warning("LLM-trede %s onverwacht gefaald: %s — door naar volgende", tier, exc)
            continue
        if out:
            return out
    return None
