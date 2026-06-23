"""Tests voor assess_continuation: alleen voortzetten bij een goede kalibratie."""
from __future__ import annotations

from nooch_village.ngram_correlate import assess_continuation


def _strong():
    # ngram en openalex bewegen identiek over 2010-2019 → sterke kalibratie
    ng = {y: float(y - 2009) for y in range(2010, 2020)}              # 1..10
    oa = {y: float(y - 2009) * 0.01 for y in range(2010, 2022)}      # zelfde vorm + 2020,2021
    return ng, oa


def test_sterke_kalibratie_wordt_vertrouwd_en_bouwt_boog():
    ng, oa = _strong()
    res = assess_continuation(ng, oa, anchor_year=2019)
    assert res["trusted"] is True
    assert res["calibration"]["r"] >= 0.9
    assert res["arc"][2019] == 100.0
    assert 2021 in res["arc"]                 # voorbij de cutoff voortgezet


def test_zwakke_kalibratie_niet_vertrouwd_geen_boog():
    ng = {y: float(y) for y in range(2010, 2020)}                    # stijgend
    oa = {2010: 5, 2011: 1, 2012: 9, 2013: 2, 2014: 8, 2015: 3,
          2016: 7, 2017: 1, 2018: 9, 2019: 2, 2020: 5}               # ruis
    res = assess_continuation(ng, oa, anchor_year=2019, min_r=0.5)
    assert res["trusted"] is False
    assert res["arc"] == {}                   # niet blind doorplakken
    assert "r" in res["calibration"]          # maar wel verantwoord met de gemeten r


def test_te_weinig_overlap_niet_vertrouwd():
    res = assess_continuation({2018: 1, 2019: 2}, {2019: 0.02, 2020: 0.03},
                              anchor_year=2019, min_r=0.5)
    assert res["trusted"] is False
    assert res["calibration"]["insufficient"] is True
    assert res["arc"] == {}
