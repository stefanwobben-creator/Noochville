"""Tests voor de lange-boog-correlatie-engine. Puur, geen netwerk."""
from __future__ import annotations

from nooch_village.ngram_correlate import pearson, correlate_terms, findings_from_rows


# ── pearson ───────────────────────────────────────────────────────────────────

def test_pearson_perfect_positief():
    assert pearson([1, 2, 3, 4], [2, 4, 6, 8]) == 1.0


def test_pearson_perfect_negatief():
    assert pearson([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_pearson_nul_variantie_geeft_none():
    assert pearson([5, 5, 5], [1, 2, 3]) is None       # x vlak → ongedefinieerd


def test_pearson_te_weinig_punten():
    assert pearson([1], [2]) is None


# ── correlate_terms ─────────────────────────────────────────────────────────

def _series():
    stijger   = [1, 2, 3, 4, 5, 6]
    mee       = [2, 3, 4, 5, 6, 7]      # beweegt mee met stijger → co-beweging
    daler     = [6, 5, 4, 3, 2, 1]      # tegengesteld aan stijger → substitutie
    ruis      = [3, 1, 4, 1, 5, 9]      # weinig samenhang → zwak
    return {"stijger": stijger, "mee": mee, "daler": daler, "ruis": ruis}


def test_co_beweging_herkend():
    res = correlate_terms(_series())
    paar = next(r for r in res if {r["a"], r["b"]} == {"stijger", "mee"})
    assert paar["label"] == "co-beweging"
    assert paar["r"] > 0.9


def test_substitutie_herkend():
    res = correlate_terms(_series())
    paar = next(r for r in res if {r["a"], r["b"]} == {"stijger", "daler"})
    assert paar["label"] == "substitutie"
    assert paar["r"] < -0.9


def test_gesorteerd_op_sterkste_verband_eerst():
    res = correlate_terms(_series())
    sterktes = [abs(r["r"]) for r in res]
    assert sterktes == sorted(sterktes, reverse=True)


def test_min_overlap_filtert_korte_reeksen():
    series = {"a": [1, 2, 3], "b": [3, 2, 1]}        # maar 3 punten
    assert correlate_terms(series, min_overlap=5) == []


def test_none_waarden_worden_uitgelijnd():
    series = {"a": [1, None, 3, 4, 5, 6], "b": [2, 9, 6, 8, 10, 12]}
    res = correlate_terms(series, min_overlap=3)
    assert len(res) == 1
    assert res[0]["n"] == 5          # het None-paar is weggelaten


# ── findings_from_rows (uit ngram-skill-rijen) ────────────────────────────────

def _rows():
    return [
        {"term": "stijger", "locale": "en", "timeseries": [1, 2, 3, 4, 5, 6]},
        {"term": "mee",     "locale": "en", "timeseries": [2, 3, 4, 5, 6, 7]},
        {"term": "daler",   "locale": "en", "timeseries": [6, 5, 4, 3, 2, 1]},
        {"term": "leeg",    "locale": "en", "no_data": True, "reason": "niet gevonden"},
        {"term": "nlterm",  "locale": "nl", "timeseries": [1, 1, 1, 1, 1, 1]},  # vlak, geen variantie
    ]


def test_findings_pakt_co_beweging_en_substitutie_per_locale():
    f = findings_from_rows(_rows())
    labels = {x["label"] for x in f}
    assert "co-beweging" in labels
    assert "substitutie" in labels
    assert all(x["locale"] == "en" for x in f)   # nl had geen bruikbaar paar


def test_findings_slaat_no_data_en_zonder_timeseries_over():
    f = findings_from_rows(_rows())
    betrokken = {x["a"] for x in f} | {x["b"] for x in f}
    assert "leeg" not in betrokken               # no_data-rij telt niet mee


def test_findings_leeg_bij_te_weinig_data():
    rows = [{"term": "x", "locale": "en", "timeseries": [1, 2, 3]}]
    assert findings_from_rows(rows) == []
