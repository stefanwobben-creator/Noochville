"""Externe observatie-bronnen (Trends-categorie / GDELT-tone / AlphaVantage): contract, strikte
validatie/fail-closed, idempotentie en metadata. Externe calls zijn geïnjecteerd (`_fetch`) zodat de
suite offline + deterministisch draait; de échte sandbox-calls staan in de rapportage.
(Stooq is verwijderd — vervangen door AlphaVantage.)"""
from __future__ import annotations
import types

import pytest

from nooch_village.observations import ObservationStore
from nooch_village.skills_impl.trends_categorie import TrendsCategorieSkill


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














# ── idempotentie + metadata via de store (geldt voor alle drie) ─────────────────────────────────
def test_idempotent_en_meta_via_store(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    meta = {"source_version": 1, "endpoint": "e", "symbol": "^spx"}
    assert obs.record_daily("stooq", "stooq_spx_day", 5075.25, bron="stooq", datum="2026-07-03", meta=meta) is True
    assert obs.record_daily("stooq", "stooq_spx_day", 5075.25, bron="stooq", datum="2026-07-03", meta=meta) is False  # geen duplicaat
    rows = obs._read_all()
    assert len(rows) == 1 and rows[0]["meta"] == meta and rows[0]["value"] == 5075.25






# ── Alpha Vantage (index-tracking-ETF's, vervangt Stooq) ────────────────────────────────────────
_AV_JSON = {"Meta Data": {"2. Symbol": "SPY"},
            "Time Series (Daily)": {
                "2026-07-02": {"1. open": "744", "2. high": "746", "3. low": "743",
                               "4. close": "744.78", "5. volume": "1"},
                "2026-07-01": {"4. close": "740.5"}}}














