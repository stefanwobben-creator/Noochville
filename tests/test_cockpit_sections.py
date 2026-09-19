"""Cockpit-herinrichting: kwantitatief weekrapport en gesplitste woordenschat (ranks/seeds).

De concurrent-monitor stond hier ook; die is op 19 september 2026 weg met de radar-beoordelingslaag
(fase 4), samen met competitor_news_store."""
from __future__ import annotations
import json

from nooch_village.skills_impl.keywords_everywhere import trend_change_pct




def test_trend_change_pct():
    assert trend_change_pct([{"value": 100}, {"value": 150}]) == 50.0
    assert trend_change_pct([100, 50]) == -50.0
    assert trend_change_pct([]) is None
    assert trend_change_pct([{"value": 0}, {"value": 50}]) is None   # vanaf 0 niet te bepalen






