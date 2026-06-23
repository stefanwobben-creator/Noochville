"""Tests voor de cadans-helper is_due. Puur, geen tijd-afhankelijkheid."""
from __future__ import annotations

from nooch_village.util import is_due

WEEK = 7 * 24 * 3600


def test_net_gedraaid_is_niet_aan_de_beurt():
    assert is_due(last_ts=1000.0, now=1000.0 + 3600, interval_s=WEEK) is False


def test_na_een_week_wel_aan_de_beurt():
    assert is_due(last_ts=1000.0, now=1000.0 + WEEK, interval_s=WEEK) is True
    assert is_due(last_ts=1000.0, now=1000.0 + WEEK + 1, interval_s=WEEK) is True


def test_nooit_gedraaid_is_aan_de_beurt():
    assert is_due(last_ts=0.0, now=1_000_000.0, interval_s=WEEK) is True


def test_interval_nul_altijd_aan_de_beurt():
    assert is_due(last_ts=999.0, now=1000.0, interval_s=0) is True
