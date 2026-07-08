"""Externe observatie-bronnen (Trends-categorie / GDELT-tone / AlphaVantage): contract, strikte
validatie/fail-closed, idempotentie en metadata. Externe calls zijn geïnjecteerd (`_fetch`) zodat de
suite offline + deterministisch draait; de échte sandbox-calls staan in de rapportage.
(Stooq is verwijderd — vervangen door AlphaVantage.)"""
from __future__ import annotations
import types

import pytest

from nooch_village.observations import ObservationStore
from nooch_village.skills_impl.alphavantage import AlphaVantageIndexSkill
from nooch_village.skills_impl.trends_categorie import TrendsCategorieSkill
from nooch_village.skills_impl.gdelt_tone import GdeltToneSkill


def _ctx(**settings):
    return types.SimpleNamespace(settings=settings)


# ── Trends-categorie ──────────────────────────────────────────────────────────────────────────
def _trends_df():
    import pandas as pd
    idx = pd.to_datetime([f"2026-07-05 {h:02d}:00:00" for h in range(24)]
                         + [f"2026-07-06 {h:02d}:00:00" for h in range(3)])
    return pd.DataFrame({"vegan shoes": [10] * 24 + [20] * 3,
                         "isPartial": [False] * 24 + [True] * 3}, index=idx)


def test_trends_config_meta_en_source_los_van_bestaande():
    s = TrendsCategorieSkill()
    assert s.SOURCE == "trends_categorie"                    # botst niet met de anker-ratio-'trends'
    ctx = _ctx(trends_cat_terms="vegan shoes, sustainable footwear", trends_cat_source_version="3")
    assert s.available_metrics(ctx) == ["vegan_shoes", "sustainable_footwear"] and s.is_configured(ctx)
    m = s.observation_meta(ctx, "2026-07-05", "vegan_shoes")
    assert m["timeframe"] == "now 7-d" and m["source_version"] == 3
    assert m["termenset"] == ["vegan shoes", "sustainable footwear"]


def test_trends_happy_path_dag_gemiddelde():
    s = TrendsCategorieSkill()
    ctx = _ctx(trends_cat_terms="vegan shoes")
    out = s.daily_values(ctx, "2026-07-05", _fetch=lambda terms, tf, geo: _trends_df())
    assert out == {"vegan_shoes": 10.0}                      # gemiddelde over de 24 volledige uren


def test_trends_fail_closed_en_partiële_dag():
    s = TrendsCategorieSkill()
    ctx = _ctx(trends_cat_terms="vegan shoes")
    # 429/fout → alles None (fail-closed, geen retry-storm door de geïnjecteerde raise)
    boom = lambda terms, tf, geo: (_ for _ in ()).throw(RuntimeError("429"))
    assert s.daily_values(ctx, "2026-07-05", _fetch=boom) == {"vegan_shoes": None}
    # partiële (nog niet volledige) dag → geen waarde
    assert s.daily_values(ctx, "2026-07-06", _fetch=lambda t, tf, g: _trends_df()) == {"vegan_shoes": None}


# ── GDELT-tone ────────────────────────────────────────────────────────────────────────────────
def _gdelt_json():
    return {"timeline": [{"series": "Average Tone",
                          "data": [{"date": "20260705T000000Z", "value": -1.5},
                                   {"date": "20260705T120000Z", "value": -2.5},
                                   {"date": "20260706T000000Z", "value": 0.0}]}]}


def test_gdelt_config_en_meta():
    s = GdeltToneSkill()
    ctx = _ctx(gdelt_terms="vegan footwear", gdelt_source_version="1")
    assert s.available_metrics(ctx) == ["vegan_footwear"] and s.is_configured(ctx)
    m = s.observation_meta(ctx, "2026-07-05", "vegan_footwear")
    assert m["term"] == "vegan footwear" and m["timespan"] == "2d" and "timelinetone" in m["endpoint"]


def test_gdelt_happy_path_dag_gemiddelde():
    s = GdeltToneSkill()
    assert s._tone_for("vegan footwear", "2026-07-05", _fetch=lambda t: _gdelt_json()) == -2.0   # (-1.5 + -2.5)/2


def test_gdelt_fail_closed():
    s = GdeltToneSkill()
    assert s._tone_for("x", "2026-07-05", _fetch=lambda t: (_ for _ in ()).throw(RuntimeError("429"))) is None
    assert s._tone_for("x", "2026-07-05", _fetch=lambda t: "niet json") is None                  # geen dict
    assert s._tone_for("x", "2026-07-05", _fetch=lambda t: {"foo": 1}) is None                    # geen timeline
    assert s._tone_for("x", "2026-07-09", _fetch=lambda t: _gdelt_json()) is None                 # geen dag → gat
    broken = {"timeline": [{"data": [{"date": "20260705T000000Z"}]}]}                             # punt zonder value
    assert s._tone_for("x", "2026-07-05", _fetch=lambda t: broken) is None


# ── idempotentie + metadata via de store (geldt voor alle drie) ─────────────────────────────────
def test_idempotent_en_meta_via_store(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    meta = {"source_version": 1, "endpoint": "e", "symbol": "^spx"}
    assert obs.record_daily("stooq", "stooq_spx_day", 5075.25, bron="stooq", datum="2026-07-03", meta=meta) is True
    assert obs.record_daily("stooq", "stooq_spx_day", 5075.25, bron="stooq", datum="2026-07-03", meta=meta) is False  # geen duplicaat
    rows = obs._read_all()
    assert len(rows) == 1 and rows[0]["meta"] == meta and rows[0]["value"] == 5075.25


def test_gdelt_daily_values_spatieert_per_term(monkeypatch):
    s = GdeltToneSkill()
    ctx = _ctx(gdelt_terms="a, b")
    monkeypatch.setattr(s, "_tone_for", lambda term, datum: {"a": -1.0, "b": 2.0}[term])
    slept = []
    out = s.daily_values(ctx, "2026-07-05", _sleep=lambda x: slept.append(x))
    assert out == {"a": -1.0, "b": 2.0} and slept == [6.0]      # één spacing tussen twee termen


def test_bevroren_config_wordt_door_de_skills_gelezen():
    """De bevroren snapshot in settings.ini komt via load_context in de skills terecht."""
    from nooch_village.config import load_context
    from nooch_village.village import BASE_DIR
    ctx = load_context(BASE_DIR)
    assert AlphaVantageIndexSkill()._symbols(ctx) == {"spx": "SPY", "aex": "IAEX.AMS"}   # ETF-proxies (vervangt Stooq)
    assert TrendsCategorieSkill()._terms(ctx) == ["footwear", "sustainable shoes", "vegan shoes"]
    assert GdeltToneSkill()._terms(ctx) == ["sustainable footwear", "vegan footwear"]


# ── Alpha Vantage (index-tracking-ETF's, vervangt Stooq) ────────────────────────────────────────
_AV_JSON = {"Meta Data": {"2. Symbol": "SPY"},
            "Time Series (Daily)": {
                "2026-07-02": {"1. open": "744", "2. high": "746", "3. low": "743",
                               "4. close": "744.78", "5. volume": "1"},
                "2026-07-01": {"4. close": "740.5"}}}


def test_alphavantage_config_meta_zonder_key_lek():
    s = AlphaVantageIndexSkill()
    ctx = _ctx(alphavantage_symbols="spx:SPY, aex:IAEX.AMS", ALPHAVANTAGE_API_KEY="SECRET",
               alphavantage_source_version="2")
    assert set(s.available_metrics(ctx)) == {"spx", "aex"} and s.is_configured(ctx)
    m = s.observation_meta(ctx, "2026-07-02", "spx")
    assert m["symbol"] == "SPY" and m["instrument"] == "index-tracking-ETF" and m["source_version"] == 2
    assert "SECRET" not in m["endpoint"] and "apikey" not in m["endpoint"]     # key lekt NIET in de meta


def test_alphavantage_happy_path_exacte_dag():
    s = AlphaVantageIndexSkill()
    assert s._close_for("SPY", "2026-07-02", "K", _fetch=lambda sym: _AV_JSON) == 744.78
    assert s._close_for("SPY", "2026-07-01", "K", _fetch=lambda sym: _AV_JSON) == 740.5


def test_alphavantage_fail_closed():
    s = AlphaVantageIndexSkill()
    for err in ({"Note": "rate limit"}, {"Information": "premium endpoint"}, {"Error Message": "invalid"}):
        assert s._close_for("SPY", "2026-07-02", "K", _fetch=lambda x, e=err: e) is None   # AV-fout/limiet
    assert s._close_for("SPY", "2026-07-09", "K", _fetch=lambda x: _AV_JSON) is None        # geen dag → gat
    assert s._close_for("SPY", "2026-07-02", "K", _fetch=lambda x: "niet json") is None      # geen dict
    bad = {"Time Series (Daily)": {"2026-07-02": {"4. close": "nietnum"}}}
    assert s._close_for("SPY", "2026-07-02", "K", _fetch=lambda x: bad) is None              # niet-numeriek
    assert s._close_for("SPY", "2026-07-02", "K", _fetch=lambda x: (_ for _ in ()).throw(RuntimeError())) is None


def test_alphavantage_geen_key_geen_data():
    s = AlphaVantageIndexSkill()
    ctx = _ctx(alphavantage_symbols="spx:SPY")                                # geen key
    assert not s.is_configured(ctx)
    assert s.daily_values(ctx, "2026-07-02", _sleep=lambda x: None) == {"spx": None}


def test_alphavantage_spatieert_per_symbool(monkeypatch):
    s = AlphaVantageIndexSkill()
    ctx = _ctx(alphavantage_symbols="spx:SPY, aex:IAEX.AMS", ALPHAVANTAGE_API_KEY="K")
    monkeypatch.setattr(s, "_close_for", lambda sym, datum, key, **kw: {"SPY": 744.78, "IAEX.AMS": 100.0}[sym])
    slept = []
    out = s.daily_values(ctx, "2026-07-02", _sleep=lambda x: slept.append(x))
    assert out == {"spx": 744.78, "aex": 100.0} and slept == [13.0]           # één spacing tussen twee symbolen
