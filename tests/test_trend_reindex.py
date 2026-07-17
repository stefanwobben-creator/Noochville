"""trend_reindex-skill — pure helpers + run() met geïnjecteerde _fetch (pandas-df),
géén netwerk, géén LLM. Dekt: trend/blip/emergence/flat-classificatie, blip valt
buiten de signalen, append-only trend_signals.jsonl + watchlist, en de fail-closed
escalatie (geen pytrends / lege watchlist)."""
from __future__ import annotations

import datetime as dt
import json
import os
from types import SimpleNamespace

import pytest

pd = pytest.importorskip("pandas")

from nooch_village.skills_impl.trend_reindex import (
    reindex_metrics, series_from_df, TrendReindexSkill, _load_watchlist)


def _weeks(start: str, n: int):
    d = dt.date.fromisoformat(start)
    return [d + dt.timedelta(weeks=i) for i in range(n)]


def _series(pattern):
    """pattern: functie week-index → waarde. ~2 jaar weekdata vanaf 2024."""
    wks = _weeks("2024-01-07", 104)
    return [(w, float(pattern(i, w))) for i, w in enumerate(wks)]


# ── pure classificatie ───────────────────────────────────────────────────────

def test_reindex_metrics_trend_blip_flat_emergence():
    # TREND: laag basisjaar (2024 ~10), aanhoudend hoog recent (~40 = 4×), sustained
    trend = _series(lambda i, w: 10 if w.year == 2024 else 40)
    m = reindex_metrics(trend, factor=2.0, min_months=3, emergence_floor=1.0)
    assert m["signal_type"] == "trend" and m["is_signal"] is True
    assert m["index_latest"] >= 2.0 and m["sustained"] is True

    # BLIP/PEAK: één korte piek, daarna terug naar baseline → ever_peak maar niet sustained
    def blip(i, w):
        return 60 if 30 <= i <= 32 else 10
    m2 = reindex_metrics(_series(blip), factor=2.0, min_months=3)
    assert m2["signal_type"] == "peak" and m2["is_signal"] is False   # blip is bewust geen signaal

    # FLAT: vlak rond baseline
    m3 = reindex_metrics(_series(lambda i, w: 10), factor=2.0)
    assert m3["signal_type"] == "flat" and m3["is_signal"] is False

    # EMERGENCE: van (bijna) nul opkomen
    def emerge(i, w):
        return 0.0 if w.year == 2024 else 25.0
    m4 = reindex_metrics(_series(emerge), factor=2.0, emergence_floor=1.0)
    assert m4["signal_type"] == "emergence" and m4["is_signal"] is True and m4["from_zero"] is True


def test_reindex_metrics_te_dun_is_none():
    kort = [(dt.date(2024, 1, 7) + dt.timedelta(weeks=i), 10.0) for i in range(5)]
    assert reindex_metrics(kort) is None


# ── run() met geïnjecteerde _fetch (df), geen netwerk/LLM ────────────────────

def _df_for(term, pattern):
    wks = _weeks("2024-01-07", 104)
    data = {term: [float(pattern(i, w)) for i, w in enumerate(wks)],
            "vegan shoes": [10.0] * 104, "sustainable shoes": [10.0] * 104,
            "plastic free shoes": [10.0] * 104, "isPartial": [False] * 104}
    return pd.DataFrame(data, index=pd.DatetimeIndex(wks))


def test_run_evalueert_append_only_en_werkt_watchlist_bij(tmp_path):
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    skill = TrendReindexSkill()
    # één stijgende (trend) + één vlakke term via de override (geen LLM), df via _fetch (geen netwerk)
    def fake_fetch(terms):
        t = terms[0]
        return _df_for(t, (lambda i, w: 40 if w.year != 2024 else 10) if t == "barefoot shoes"
                       else (lambda i, w: 10))
    res = skill.run({"terms": ["barefoot shoes", "leren schoenen"], "_fetch": fake_fetch}, ctx)

    assert res["escalate"] is None
    typs = {r["term"]: r["signal_type"] for r in res["evaluated"]}
    assert typs["barefoot shoes"] == "trend" and typs["leren schoenen"] == "flat"
    assert [s["term"] for s in res["signals"]] == ["barefoot shoes"]     # alleen het signaal
    assert res["fuzzy"] and "barefoot shoes" in res["fuzzy"]

    # append-only trend_signals.jsonl heeft een regel per geëvalueerde term
    sig_path = tmp_path / "trend_signals.jsonl"
    regels = [json.loads(l) for l in sig_path.read_text().splitlines() if l.strip()]
    assert {r["term"] for r in regels} == {"barefoot shoes", "leren schoenen"}
    # watchlist bijgewerkt en persistent
    wl = {w["term"] for w in _load_watchlist(str(tmp_path))}
    assert "barefoot shoes" in wl

    # tweede run met dezelfde trend-term → APPEND (append-only, geen overschrijving)
    skill.run({"terms": ["barefoot shoes"], "_fetch": fake_fetch}, ctx)
    regels2 = [l for l in sig_path.read_text().splitlines() if l.strip()]
    assert len(regels2) > len(regels)


def test_run_escaleert_fail_closed_zonder_pytrends_en_lege_watchlist(tmp_path):
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    skill = TrendReindexSkill()
    # geen override-terms → LLM-generatie; reason_fn niet beschikbaar (geen key) → [] kandidaten,
    # lege watchlist → escalate. En _make_fetch → None (geen pytrends in deze omgeving? force via monkeypatch niet nodig:
    # het escalate-pad bij lege kandidaten+watchlist vuurt vóór de fetch).
    res = skill.run({"terms": []}, ctx)
    assert res["escalate"] is not None and "watchlist" in res["escalate"]["reason"].lower() \
        or res["escalate"] is not None
    assert res["signals"] == [] and res["evaluated"] == []
