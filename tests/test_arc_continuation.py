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


# ── continue_arc ──────────────────────────────────────────────────────────────

def test_continue_arc_ankert_op_100_en_zet_door():
    ngram    = {2017: 0.5, 2018: 0.75, 2019: 1.0}          # anker 2019 = 1.0
    openalex = {2019: 0.02, 2020: 0.03, 2021: 0.04}        # anker 2019 = 0.02
    arc = continue_arc(ngram, openalex, anchor_year=2019)
    assert arc[2019] == 100.0                              # anker = 100
    assert arc[2017] == 50.0                               # 100 * 0.5/1.0
    assert arc[2018] == 75.0
    assert arc[2020] == 150.0                              # 100 * 0.03/0.02
    assert arc[2021] == 200.0
    assert sorted(arc) == [2017, 2018, 2019, 2020, 2021]   # ngram t/m anker, daarna OpenAlex


def test_continue_arc_leeg_zonder_anker():
    # anker 2019 ontbreekt in openalex → kan niet normaliseren
    assert continue_arc({2019: 1.0}, {2020: 0.03}, anchor_year=2019) == {}


def test_continue_arc_negeert_ngram_na_anker():
    ngram    = {2018: 0.5, 2019: 1.0, 2020: 0.0}           # 2020 ngram-blind (0)
    openalex = {2019: 0.02, 2020: 0.04}
    arc = continue_arc(ngram, openalex, anchor_year=2019)
    assert arc[2020] == 200.0                              # OpenAlex, niet de ngram-0
