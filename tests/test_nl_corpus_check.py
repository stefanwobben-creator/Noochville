"""Tests voor de dynamische NL-corpus-dekkingscheck (uncovered_nl_terms). Puur."""
from __future__ import annotations

from nooch_village.ngram_correlate import uncovered_nl_terms


def _rows():
    return [
        {"term": "consument", "locale": "nl", "no_data": True,
         "reason": "term niet gevonden in corpus"},
        {"term": "duurzaam", "locale": "nl", "timeseries": [0.1, 0.2, 0.3]},      # wel data
        {"term": "vegan shoes", "locale": "en", "no_data": True,
         "reason": "term niet gevonden in corpus"},                              # EN, telt niet
        {"term": "plasticvrij", "locale": "nl", "no_data": True,
         "reason": "max retries (netwerkfout)"},                                 # andere fout
        {"term": "soberheid", "locale": "nl", "no_data": True,
         "reason": "term niet gevonden in corpus"},
    ]


def test_pakt_alleen_nl_niet_gevonden_termen():
    assert uncovered_nl_terms(_rows()) == ["consument", "soberheid"]


def test_negeert_termen_met_data():
    rows = [{"term": "duurzaam", "locale": "nl", "timeseries": [0.1]}]
    assert uncovered_nl_terms(rows) == []


def test_negeert_netwerkfout():
    rows = [{"term": "x", "locale": "nl", "no_data": True, "reason": "netwerk stuk"}]
    assert uncovered_nl_terms(rows) == []


def test_negeert_engelse_termen():
    rows = [{"term": "y", "locale": "en", "no_data": True,
             "reason": "term niet gevonden in corpus"}]
    assert uncovered_nl_terms(rows) == []


def test_leeg_bij_geen_gaten():
    assert uncovered_nl_terms([]) == []
