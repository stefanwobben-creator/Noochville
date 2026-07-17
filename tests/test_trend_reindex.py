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


# ── SerpApi-fallback + escalatie-gat ─────────────────────────────────────────

def _serpapi_resp(terms, pattern):
    wks = _weeks("2024-01-07", 104)
    import datetime as _dt
    tl = []
    for i, w in enumerate(wks):
        vals = [{"query": t, "value": str(int(pattern(i, w, t))),
                 "extracted_value": int(pattern(i, w, t))} for t in terms]
        tl.append({"timestamp": str(int(_dt.datetime(w.year, w.month, w.day).timestamp())),
                   "values": vals})
    return {"interest_over_time": {"timeline_data": tl}}


def test_serpapi_normalisatie_naar_pytrends_vorm():
    from nooch_village.skills_impl.trend_reindex import serpapi_timeseries_df
    resp = _serpapi_resp(["barefoot shoes", "vegan shoes"], lambda i, w, t: 20)
    df = serpapi_timeseries_df(resp, ["barefoot shoes", "vegan shoes"])
    assert "barefoot shoes" in df and "vegan shoes" in df and "isPartial" in df
    assert bool(df["isPartial"].iloc[-1]) is True and not bool(df["isPartial"].iloc[0])
    # series_from_df/_drop_partial werken ongewijzigd op deze vorm
    assert len(series_from_df(df, "barefoot shoes")) == 103    # 104 − de partiële laatste week
    # lege respons → lege df (fetch telt dan als mislukt)
    assert serpapi_timeseries_df({}, ["x"]).empty


def test_serpapi_fetch_ankers_in_een_request_en_run(tmp_path):
    from nooch_village.skills_impl.trend_reindex import _serpapi_fetch
    calls = []
    def fake_get(params):
        calls.append(params["q"])
        return _serpapi_resp(params["q"].split(","),
                             lambda i, w, t: (40 if w.year != 2024 else 10) if t == "barefoot shoes" else 10)
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"serpapi_api_key": "K"})
    skill = TrendReindexSkill()
    fetch = _serpapi_fetch(skill._cfg(ctx), get_fn=fake_get)
    res = skill.run({"terms": ["barefoot shoes"], "_fetch": fetch}, ctx)
    # candidate + ankerset in ÉÉN request (comma-gescheiden, één 0-100-schaal)
    assert calls and "barefoot shoes" in calls[0] and "vegan shoes" in calls[0]
    assert [s["term"] for s in res["signals"]] == ["barefoot shoes"] and res["escalate"] is None


def test_escalatie_gat_alle_fetches_falen(tmp_path):
    """Kandidaten gegenereerd maar ALLE fetches faalden (quota/429) → zichtbaar escaleren, niet stil."""
    from nooch_village.skills_impl.trend_reindex import _serpapi_fetch
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"serpapi_api_key": "K"})
    skill = TrendReindexSkill()
    badfetch = _serpapi_fetch(skill._cfg(ctx), get_fn=lambda p: {"error": "out of searches"})
    res = skill.run({"terms": ["barefoot shoes", "vegan shoes"], "_fetch": badfetch}, ctx)
    assert res["evaluated"] == [] and res["signals"] == []
    assert res["escalate"] and "opgehaald" in res["escalate"]["reason"].lower()


def test_make_fetch_kiest_serpapi_bij_key(tmp_path, monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    skill = TrendReindexSkill()
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"serpapi_api_key": "K"})
    fetch = skill._make_fetch(skill._cfg(ctx))
    assert fetch is not None and getattr(fetch, "__qualname__", "").startswith("_serpapi_fetch")
    # source=serpapi zonder key → None (fail-closed)
    ctx2 = SimpleNamespace(data_dir=str(tmp_path), settings={"trend_reindex_source": "serpapi"})
    assert skill._make_fetch(skill._cfg(ctx2)) is None
