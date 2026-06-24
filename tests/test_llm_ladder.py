"""De getrapte LLM-ladder: goedkoop eerst, cooldown bij rate-limit, fail-closed.

Geen netwerk: de trede-functies en de cooldown-klok worden geïnjecteerd."""
from __future__ import annotations

import nooch_village.llm as llm


# ── Parsen ────────────────────────────────────────────────────────────────────

def test_parse_ladder_vendor_en_model():
    out = llm._parse_ladder("gemini:gemini-2.5-flash-lite, mistral:mistral-small-latest ,anthropic")
    assert out == [
        ("gemini", "gemini-2.5-flash-lite"),
        ("mistral", "mistral-small-latest"),
        ("anthropic", None),     # alleen vendor → default-model
    ]


def test_default_ladder_begint_goedkoop():
    steps = llm._ladder()
    assert steps[0] == ("gemini", "gemini-2.5-flash-lite")      # goedkoopste eerst
    assert steps[-1][0] == "anthropic"                          # vangnet als laatste
    assert "mistral" in [v for v, _ in steps]


# ── Volgorde: goedkoop eerst, dan door ────────────────────────────────────────

def test_ladder_pakt_eerste_werkende_trede(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None: (calls.append("g"), None)[1])
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None: (calls.append("m"), "MISTRAL")[1])
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None: (calls.append("a"), "A")[1])
    out = llm.reason("hoi", ladder="gemini:g1,mistral:m1,anthropic:a1")
    assert out == "MISTRAL"
    assert calls == ["g", "m"]          # gestopt zodra Mistral antwoordde; Anthropic niet bereikt


# ── Rate-limit → cooldown + door naar de volgende trede ───────────────────────

def test_rate_limit_zet_trede_in_cooldown_en_gaat_door(monkeypatch):
    def boom(p, model=None):
        raise llm._RateLimit("429 RESOURCE_EXHAUSTED")
    monkeypatch.setattr(llm, "_try_gemini", boom)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None: "MISTRAL")
    out = llm.reason("hoi", ladder="gemini:g1,mistral:m1")
    assert out == "MISTRAL"
    assert llm._in_cooldown("gemini:g1")        # uitgeputte trede staat in cooldown


def test_trede_in_cooldown_wordt_overgeslagen(monkeypatch):
    geraakt = {"gemini": False}

    def gem(p, model=None):
        geraakt["gemini"] = True
        return "GEMINI"
    monkeypatch.setattr(llm, "_try_gemini", gem)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None: "MISTRAL")
    llm._set_cooldown("gemini:g1")              # alsof Gemini's dagcap op is
    out = llm.reason("hoi", ladder="gemini:g1,mistral:m1")
    assert out == "MISTRAL"
    assert geraakt["gemini"] is False           # cooldown-trede niet aangeroepen


def test_cooldown_verloopt_na_de_tijd(monkeypatch):
    monkeypatch.setenv("LLM_TIER_COOLDOWN_S", "100")        # deterministisch, los van .env
    llm.reset_cooldowns()
    llm._set_cooldown("gemini:g1", now=0.0)
    assert llm._in_cooldown("gemini:g1", now=10.0)          # binnen het venster (< 100)
    assert not llm._in_cooldown("gemini:g1", now=10_000.0)  # ruim erna verlopen (> 100)


# ── Fail-closed + geen sleutel = trede overslaan ──────────────────────────────

def test_alle_treden_falen_geeft_none(monkeypatch):
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None: None)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None: None)
    assert llm.reason("hoi") is None


def test_mistral_zonder_key_geeft_none(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert llm._try_mistral("hoi") is None      # geen key → trede overslaan, geen call


def test_custom_ladder_voor_premium_skill(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None: (calls.append("g"), "G")[1])
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None: (calls.append("a"), "SONNET")[1])
    out = llm.reason("hoi", ladder="anthropic:claude-sonnet-4-6")
    assert out == "SONNET"
    assert calls == ["a"]                       # alleen de premium-trede, Gemini niet geraakt
