"""Drie externe observatie-bronnen (Stooq / Trends-categorie / GDELT-tone): contract, strikte
validatie/fail-closed, idempotentie en metadata. Externe calls zijn geïnjecteerd (`_fetch`) zodat de
suite offline + deterministisch draait; de échte sandbox-calls staan in de rapportage."""
from __future__ import annotations
import types

import pytest

from nooch_village.observations import ObservationStore
from nooch_village.skills_impl.stooq import StooqIndexSkill
from nooch_village.skills_impl.trends_categorie import TrendsCategorieSkill
from nooch_village.skills_impl.gdelt_tone import GdeltToneSkill

# de échte anti-bot/rate-limit-responses die de sandbox teruggaf (regressie-fixtures)
_STOOQ_CHALLENGE = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
                    '<noscript>This site requires JavaScript to verify your browser.</noscript></head></html>')
_STOOQ_CSV = ("Date,Open,High,Low,Close,Volume\n"
              "2026-07-02,5000,5050,4990,5010.5,0\n"
              "2026-07-03,5010,5080,5005,5075.25,0\n")


def _ctx(**settings):
    return types.SimpleNamespace(settings=settings)


# ── Stooq ─────────────────────────────────────────────────────────────────────────────────────
def test_stooq_config_en_meta():
    s = StooqIndexSkill()
    ctx = _ctx(stooq_symbols="spx:^spx, aex:^aex", stooq_source_version="2")
    assert s.SOURCE == "stooq" and s.kind == "flux"
    assert set(s.available_metrics(ctx)) == {"spx", "aex"} and s.is_configured(ctx)
    m = s.observation_meta(ctx, "2026-07-03", "aex")
    assert m["source_version"] == 2 and m["symbol"] == "^aex" and "s=%5Eaex" in m["endpoint"]


def test_stooq_happy_path_exacte_dag():
    s = StooqIndexSkill()
    # daily_values gebruikt _close_for; test die met geïnjecteerde CSV (exacte-dag-keying)
    assert s._close_for("^spx", "2026-07-03", _fetch=lambda sym: _STOOQ_CSV) == 5075.25
    assert s._close_for("^spx", "2026-07-02", _fetch=lambda sym: _STOOQ_CSV) == 5010.5


def test_stooq_fail_closed():
    s = StooqIndexSkill()
    f = lambda sym: _STOOQ_CHALLENGE
    assert s._close_for("^spx", "2026-07-03", _fetch=f) is None              # JS-challenge HTML → None
    assert s._close_for("^spx", "2026-07-09", _fetch=lambda x: _STOOQ_CSV) is None   # geen rij → gat
    assert s._close_for("^spx", "2026-07-03", _fetch=lambda x: "wrong,header\n1,2") is None  # verkeerde header
    bad = "Date,Open,High,Low,Close,Volume\n2026-07-03,a,b,c,nietnum,0\n"
    assert s._close_for("^spx", "2026-07-03", _fetch=lambda x: bad) is None   # niet-numerieke close
    assert s._close_for("^spx", "2026-07-03", _fetch=lambda x: (_ for _ in ()).throw(RuntimeError())) is None


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
    assert StooqIndexSkill()._symbols(ctx) == {"spx": "^spx", "aex": "^aex"}
    assert TrendsCategorieSkill()._terms(ctx) == ["footwear", "sustainable shoes", "vegan shoes"]
    assert GdeltToneSkill()._terms(ctx) == ["sustainable footwear", "vegan footwear"]
