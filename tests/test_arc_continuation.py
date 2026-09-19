"""Tests voor overlap-kalibratie en gekoppelde voortzetting (ngram → OpenAlex)."""
from __future__ import annotations

from nooch_village.ngram_correlate import years_dict, calibrate, continue_arc


# ── years_dict ────────────────────────────────────────────────────────────────

def test_years_dict_mapt_index_op_jaar():
    assert years_dict([0.1, 0.2, None, 0.4], 2016) == {2016: 0.1, 2017: 0.2, 2019: 0.4}


# ── calibrate ─────────────────────────────────────────────────────────────────

def test_calibrate_sterke_correlatie():
    ng = {y: float(y) for y in range(2010, 2020)}          # 2010..2019 stijgend
    oa = {y: float(y) * 2 for y in range(2010, 2020)}      # zelfde vorm
    res = calibrate(ng, oa)
    assert res["r"] == 1.0
    assert res["n"] == 10
    assert res["overlap"] == (2010, 2019)


def test_calibrate_te_weinig_overlap():
    res = calibrate({2018: 1, 2019: 2}, {2019: 2, 2020: 3}, min_overlap=5)
    assert res["insufficient"] is True
    assert res["n"] == 1               # alleen 2019 overlapt


def test_calibrate_alleen_gedeelde_jaren():
    ng = {y: float(y) for y in range(2000, 2020)}
    oa = {y: float(y) for y in range(2015, 2026)}          # overlap 2015-2019
    res = calibrate(ng, oa)
    assert res["overlap"] == (2015, 2019)
    assert res["n"] == 5




def test_continue_arc_leeg_zonder_anker():
    # anker 2019 ontbreekt in openalex → kan niet normaliseren
    assert continue_arc({2019: 1.0}, {2020: 0.03}, anchor_year=2019) == {}


