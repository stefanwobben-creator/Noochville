"""Tests voor per-taal-batches met eigen geo (de geo-fix). Thread-vrij, geen netwerk."""
from __future__ import annotations

import pytest

from nooch_village.keyword_batch import propose_locale_batch
from nooch_village.keyword_matrix import (
    core_candidates_for_locale, longtail_candidates_for_locale, LOCALE_GEO,
)


def test_en_batch_meet_in_gb_geo():
    b = propose_locale_batch("en", "core")
    assert b["locale"] == "en"
    assert b["country"] == "gb"          # Engels gemeten in Groot-Brittannië, niet nl
    assert b["market"] == "gb"


def test_nl_batch_meet_in_nl_geo():
    b = propose_locale_batch("nl", "core")
    assert b["locale"] == "nl"
    assert b["country"] == "nl"


def test_en_batch_bevat_alleen_engelse_termen():
    b = propose_locale_batch("en", "core")
    assert "vegan shoes" in b["candidates"]
    assert "vegan schoenen" not in b["candidates"]     # geen NL-term in EN-batch
    assert b["candidates"] == core_candidates_for_locale("en")


def test_nl_batch_bevat_alleen_nederlandse_termen():
    b = propose_locale_batch("nl", "core")
    assert "vegan schoenen" in b["candidates"]
    assert "vegan shoes" not in b["candidates"]


def test_longtail_tier():
    b = propose_locale_batch("en", "longtail")
    assert b["candidates"] == longtail_candidates_for_locale("en")
    assert all(len(c.split()) >= 3 for c in b["candidates"])


def test_estimated_credits_telt_kandidaten():
    b = propose_locale_batch("nl", "core")
    assert b["estimated_credits"] == len(b["candidates"])


def test_onbekende_taal_faalt():
    with pytest.raises(ValueError):
        propose_locale_batch("xx", "core")


def test_onbekende_tier_faalt():
    with pytest.raises(ValueError):
        propose_locale_batch("en", "midtail")


def test_elke_locale_heeft_een_geo():
    from nooch_village.keyword_matrix import QUALIFIERS
    for locale in QUALIFIERS:
        assert locale in LOCALE_GEO, f"taal {locale} mist een geo in LOCALE_GEO"
