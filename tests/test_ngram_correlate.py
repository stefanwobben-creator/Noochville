"""Tests voor de lange-boog-correlatie-engine. Puur, geen netwerk."""
from __future__ import annotations

from nooch_village.ngram_correlate import pearson, correlate_terms


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
