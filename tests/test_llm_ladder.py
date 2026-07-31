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
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: (calls.append("g"), None)[1])
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: (calls.append("m"), "MISTRAL")[1])
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None, **kw: (calls.append("a"), "A")[1])
    out = llm.reason("hoi", ladder="gemini:g1,mistral:m1,anthropic:a1")
    assert out == "MISTRAL"
    assert calls == ["g", "m"]          # gestopt zodra Mistral antwoordde; Anthropic niet bereikt


# ── Rate-limit → cooldown + door naar de volgende trede ───────────────────────

def test_rate_limit_zet_trede_in_cooldown_en_gaat_door(monkeypatch):
    def boom(p, model=None, **kw):
        raise llm._RateLimit("429 RESOURCE_EXHAUSTED")
    monkeypatch.setattr(llm, "_try_gemini", boom)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: "MISTRAL")
    out = llm.reason("hoi", ladder="gemini:g1,mistral:m1")
    assert out == "MISTRAL"
    assert llm._in_cooldown("gemini:g1")        # uitgeputte trede staat in cooldown


def test_trede_in_cooldown_wordt_overgeslagen(monkeypatch):
    geraakt = {"gemini": False}

    def gem(p, model=None, **kw):
        geraakt["gemini"] = True
        return "GEMINI"
    monkeypatch.setattr(llm, "_try_gemini", gem)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: "MISTRAL")
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
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_mistral", lambda p, model=None, **kw: None)
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None, **kw: None)
    assert llm.reason("hoi") is None


def test_mistral_zonder_key_geeft_none(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert llm._try_mistral("hoi") is None      # geen key → trede overslaan, geen call


def test_custom_ladder_voor_premium_skill(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_try_gemini", lambda p, model=None, **kw: (calls.append("g"), "G")[1])
    monkeypatch.setattr(llm, "_try_anthropic", lambda p, model=None, **kw: (calls.append("a"), "SONNET")[1])
    out = llm.reason("hoi", ladder="anthropic:claude-sonnet-4-6")
    assert out == "SONNET"
    assert calls == ["a"]                       # alleen de premium-trede, Gemini niet geraakt


# ── de zachte staart: een eigen ladder AANVULLEN, niet vervangen ────────────

def test_dorpsstaart_komt_achter_de_eigen_tredes(monkeypatch):
    """De kop blijft de kop; de goedkope staart komt er ACHTER, niet ervoor."""
    monkeypatch.setenv("LLM_LADDER", "gemini:g1,mistral:m1")
    assert llm.met_dorpsstaart("anthropic:sonnet") == "anthropic:sonnet,gemini:g1,mistral:m1"


def test_dorpsstaart_noemt_een_trede_nooit_twee_keer(monkeypatch):
    """Staat een dorpstrede al in de eigen ladder, dan blijft hij op zijn EIGEN plek staan —
    anders zou dezelfde trede twee keer geprobeerd worden (dubbele wachttijd bij een storing)."""
    monkeypatch.setenv("LLM_LADDER", "gemini:g1,mistral:m1")
    assert llm.met_dorpsstaart("mistral:m1,anthropic:sonnet") == "mistral:m1,anthropic:sonnet,gemini:g1"


def test_dorpsstaart_zonder_eigen_ladder_is_de_dorpsladder(monkeypatch):
    monkeypatch.setenv("LLM_LADDER", "gemini:g1")
    assert llm.met_dorpsstaart("") == "gemini:g1"


def test_tier_namen_normaliseert_een_kale_vendor():
    """'anthropic' en 'anthropic:default' zijn dezelfde trede; zonder normalisatie zou een
    gerapporteerde trede nooit matchen met wat er in de ladder stond."""
    assert llm.tier_namen("anthropic,gemini:g1") == ["anthropic:default", "gemini:g1"]


def test_staart_bewaart_de_originele_spec_niet_het_label(monkeypatch):
    """De samengestelde ladder moet uitvoerbaar blijven: 'anthropic' mag geen 'anthropic:default'
    worden, want dan reist 'default' als MODELNAAM mee naar de leverancier."""
    monkeypatch.setenv("LLM_LADDER", "anthropic")
    assert llm._parse_ladder(llm.met_dorpsstaart("gemini:g1")) == [("gemini", "g1"), ("anthropic", None)]
