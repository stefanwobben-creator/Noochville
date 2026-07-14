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

Vendors met een OpenAI-compatibele /chat/completions-API (mistral, openai, openrouter) lopen
allemaal door één generieke trede (`_try_openai_compatible`, registry `_OPENAI_COMPAT`). openai en
openrouter zijn pure config: activeer ze door een key te zetten en ze in `LLM_LADDER` op te nemen met
een expliciet model, bv. `LLM_LADDER=...,openrouter:meta-llama/llama-3.1-70b-instruct,...`.

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

# Vendors met een OpenAI-compatibele /chat/completions-API worden allemaal door één generieke trede
# (`_try_openai_compatible`) bediend: (base_url, env-var voor de key). De model-env-var wordt afgeleid
# als <env_key zonder _API_KEY>_MODEL (bv. MISTRAL_MODEL). Nieuwe zo'n vendor toevoegen = één regel hier.
_OPENAI_COMPAT = {
    "mistral":    ("https://api.mistral.ai/v1",    "MISTRAL_API_KEY"),
    "openai":     ("https://api.openai.com/v1",    "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
}
# Default-model per OpenAI-compatibele vendor, alleen waar een zinnige default bestaat. openai/openrouter
# zijn "pure config": zonder expliciet model (in de ladder of via <VENDOR>_MODEL) wordt de trede overgeslagen.
_DEFAULT_MODELS = {"mistral": _DEFAULT_MISTRAL_MODEL}

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

def _try_gemini(prompt: str, *, model: str | None = None, sleep=time.sleep, max_tokens: int = 700,
                json_mode: bool = False) -> str | None:
    """Probeer Gemini. Eén retry bij een transiente fout (bijv. SSL-timeout).
    Bij een rate-limit/quota → `_RateLimit` (de ladder zet de trede in cooldown en gaat door).
    json_mode=True forceert JSON-output (response_mime_type)."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    model = model or os.getenv("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL)
    for poging in range(2):
        try:
            from google import genai
            from google.genai import types as genai_types
            client = genai.Client(api_key=key)
            _cfg = dict(max_output_tokens=max_tokens,
                        http_options=genai_types.HttpOptions(timeout=_GEMINI_TIMEOUT_MS))
            if json_mode:
                _cfg["response_mime_type"] = "application/json"
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(**_cfg),
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


def _try_openai_compatible(vendor: str, prompt: str, *, model: str | None = None,
                           max_tokens: int = 700, json_mode: bool = False) -> str | None:
    """Generieke trede voor elke vendor met een OpenAI-compatibele /chat/completions-API (dependency-vrij,
    enkel urllib). De vendor komt uit de registry `_OPENAI_COMPAT` (base_url + env-key).

    - Geen key → trede overslaan (`None`); de ladder gaat door naar de volgende trede.
    - Model-resolutie: expliciet `model` → env `<VENDOR>_MODEL` → `_DEFAULT_MODELS[vendor]`. Geen model
      (pure-config vendor zonder opgave) → trede overslaan.
    - Rate-limit/quota (HTTP 429 of bekende markers) → `_RateLimit` (cooldown + door, beheerd in `reason`).
    - `json_mode=True` forceert JSON-output (`response_format`; OpenAI-compatibel)."""
    base_url, env_key = _OPENAI_COMPAT[vendor]
    key = os.getenv(env_key)
    if not key:
        return None
    model = model or os.getenv(env_key.replace("_API_KEY", "_MODEL")) or _DEFAULT_MODELS.get(vendor)
    if not model:
        log.warning("LLM %s: geen model opgegeven (pure config) — trede overgeslagen", vendor)
        return None
    import json
    import urllib.error
    import urllib.request
    _payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if json_mode:
        _payload["response_format"] = {"type": "json_object"}
    body = json.dumps(_payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data["choices"][0]["message"]["content"] or "").strip()
        if text:
            log.debug("LLM via %s (%s)", vendor, model)
            return text
        return None
    except urllib.error.HTTPError as exc:
        log.warning("LLM %s (%s) faalde: HTTP %s", vendor, model, exc.code)
        if exc.code == 429:
            raise _RateLimit(f"HTTP 429 {exc}") from exc
        return None
    except Exception as exc:
        log.warning("LLM %s (%s) faalde: %s", vendor, model, exc)
        if _is_rate_limit(exc):
            raise _RateLimit(str(exc)) from exc
        return None


def _try_mistral(prompt: str, *, model: str | None = None, max_tokens: int = 700,
                 json_mode: bool = False) -> str | None:
    """Mistral-trede — dunne delegator naar de generieke OpenAI-compatibele adapter. Behoudt de
    named seam (monkeypatch-punt voor de tests); het HTTP-pad is identiek aan de andere compat-vendors."""
    return _try_openai_compatible("mistral", prompt, model=model, max_tokens=max_tokens, json_mode=json_mode)


def _try_anthropic(prompt: str, *, model: str | None = None, max_tokens: int = 700,
                   json_mode: bool = False) -> str | None:
    """Probeer Anthropic (duur; alleen als vangnet in de ladder). Rate-limit/quota → `_RateLimit`.
    (json_mode wordt geaccepteerd maar Anthropic kent geen strikte json-modus — de robuuste parse +
    strakke prompt-instructie vangen dit af.)"""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = model or os.getenv("ANTHROPIC_MODEL", _DEFAULT_ANTHROPIC_MODEL)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=_HTTP_TIMEOUT_S)
        msg = client.messages.create(
            model=model, max_tokens=max_tokens,
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


def _call_tier(vendor: str, model: str | None, prompt: str, max_tokens: int = 700,
               json_mode: bool = False) -> str | None:
    module = sys.modules[__name__]
    # Native adapters (gemini/anthropic) + de mistral-delegator: via getattr op naam, zodat een test die
    # de trede-functie monkeypatcht ook echt door de ladder wordt opgepikt.
    name = _VENDOR_FNS.get(vendor)
    if name is not None:
        fn = getattr(module, name, None)
        return fn(prompt, model=model, max_tokens=max_tokens, json_mode=json_mode) if fn else None
    # Overige OpenAI-compatibele vendors (openai/openrouter): pure config → de generieke trede.
    if vendor in _OPENAI_COMPAT:
        fn = getattr(module, "_try_openai_compatible", None)
        return fn(vendor, prompt, model=model, max_tokens=max_tokens, json_mode=json_mode) if fn else None
    log.warning("onbekende LLM-vendor in ladder: %r (trede overgeslagen)", vendor)
    return None


def _vendor_has_key(vendor: str) -> bool:
    """Heeft deze vendor een API-sleutel geconfigureerd? Pure env-check (geen call), zodat `reason()`
    een None-uitkomst kan splitsen in 'geen sleutel' (trede overgeslagen) vs 'lege respons' (wél
    aangeroepen, maar leeg). Geen adapter-wijziging: de treden blijven ongewijzigd None teruggeven."""
    if vendor == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    if vendor == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    reg = _OPENAI_COMPAT.get(vendor)
    return bool(os.getenv(reg[1])) if reg else False


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


def reason(prompt: str, *, ladder: str | None = None, max_tokens: int = 700,
           json_mode: bool = False, return_tier: bool = False, call_site: str = "onbekend"):
    """Optionele LLM-redenering via de getrapte ladder (goedkoop → duur).

    Loopt de treden af tot er één een antwoord geeft. Een trede zonder sleutel of in
    cooldown wordt overgeslagen; een rate-limit zet de trede in cooldown en gaat door.
    Geen werkende trede → None (de caller valt terug op zijn heuristiek).

    `ladder`: optioneel een eigen ladder-string voor een specifieke (premium) skill.
    `json_mode`: forceer JSON-output waar de provider het ondersteunt (Gemini/Mistral).
    `return_tier`: geef `(tekst, trede)` terug i.p.v. alleen `tekst` (bij falen `(None, None)`),
      zodat de caller kan loggen wélke trede het antwoord leverde.
    `call_site`: kort, stabiel label van de aanroeplocatie (bv. "plan_checklist", "field_note_narrative").
      Eén centrale INFO-regel per aanroep logt dit label + de promptlengte + de trede die antwoordde,
      zodat prompt-omvang en herkomst per call-site zichtbaar zijn. Default "onbekend" maakt niet-gelabelde
      call-sites vanzelf zichtbaar in de logs.

    Alle LLM-aanroepen van het dorp lopen door dit ene poortje en worden hier in de tijd
    uitgesmeerd (LIMITER), zodat het dorp onder de gratis limiet blijft."""
    LIMITER.acquire()
    steps = _parse_ladder(ladder) if ladder else _ladder()
    outcomes: list[str] = []                       # per trede de uitkomst — voor de samenvatting bij falen
    for vendor, model in steps:
        tier = f"{vendor}:{model or 'default'}"
        if _in_cooldown(tier):                     # observeerbaar op INFO (was DEBUG → onzichtbaar)
            log.info("LLM-trede %s: in cooldown — overgeslagen", tier)
            outcomes.append(f"{tier}=cooldown")
            continue
        try:
            out = _call_tier(vendor, model, prompt, max_tokens=max_tokens, json_mode=json_mode)
        except _RateLimit:
            log.info("LLM-trede %s: rate-limit (429) — cooldown + door naar volgende", tier)
            _set_cooldown(tier)
            outcomes.append(f"{tier}=429")
            continue
        except Exception as exc:   # defensief: een trede mag de ladder nooit laten crashen
            log.warning("LLM-trede %s: onverwacht gefaald (%s) — door naar volgende", tier, exc)
            outcomes.append(f"{tier}=fout (zie warning)")
            continue
        if out:
            log.info("LLM-trede %s: geslaagd", tier)
            log.info("LLM-call [%s] prompt=%d tekens → %s", call_site, len(prompt), tier)
            try:                                   # CO2-KPI-boekhouding: usage vastleggen, fail-soft
                from nooch_village import llm_usage
                it, ot = llm_usage.estimate_split(prompt, out)
                llm_usage.record(call_site, tier, it, ot, estimated=True)
            except Exception:                      # boekhouding mag de LLM-call nooit breken
                pass
            return (out, tier) if return_tier else out
        # None-uitkomst gesplitst: geen sleutel (trede overgeslagen) vs lege respons (wél aangeroepen).
        if not _vendor_has_key(vendor):
            log.info("LLM-trede %s: geen sleutel — overgeslagen", tier)
            outcomes.append(f"{tier}=geen sleutel")
        else:
            log.info("LLM-trede %s: lege respons — door naar volgende", tier)
            outcomes.append(f"{tier}=lege respons")
    # Alle tredes op: log expliciet waaróm (voorheen zag de caller alleen "LLM-plan mislukt").
    log.warning("LLM: alle %d trede(s) uitgeput — geen antwoord. Per trede: %s",
                len(outcomes), "; ".join(outcomes) or "(geen tredes geconfigureerd)")
    log.info("LLM-call [%s] prompt=%d tekens → geen antwoord", call_site, len(prompt))
    return (None, None) if return_tier else None
