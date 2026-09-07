"""Cockpit-herinrichting: kwantitatief weekrapport, gesplitste woordenschat (ranks/seeds),
en de volledige concurrent-monitor met laatste nieuwsfeit per merk."""
from __future__ import annotations
import json

from nooch_village.competitor_news_store import CompetitorNews
from nooch_village.skills_impl.keywords_everywhere import trend_change_pct


def test_competitor_news_houdt_nieuwste_per_merk(tmp_path):
    store = CompetitorNews(str(tmp_path / "news.json"))
    store.update([
        {"brand": "Veja", "title": "oud", "link": "a", "date": "2025-01-01"},
        {"brand": "Veja", "title": "nieuw", "link": "b", "date": "2026-06-01"},
        {"brand": "Komrads", "title": "k", "link": "c", "date": "2026-05-01"},
    ])
    assert store.latest("Veja")["title"] == "nieuw"          # nieuwste op datum wint
    assert store.latest("Komrads")["title"] == "k"
    # herladen vanaf schijf
    assert CompetitorNews(str(tmp_path / "news.json")).latest("Veja")["title"] == "nieuw"


def test_trend_change_pct():
    assert trend_change_pct([{"value": 100}, {"value": 150}]) == 50.0
    assert trend_change_pct([100, 50]) == -50.0
    assert trend_change_pct([]) is None
    assert trend_change_pct([{"value": 0}, {"value": 50}]) is None   # vanaf 0 niet te bepalen






