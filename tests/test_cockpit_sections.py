"""Cockpit-herinrichting: kwantitatief weekrapport, gesplitste woordenschat (ranks/seeds),
en de volledige concurrent-monitor met laatste nieuwsfeit per merk."""
from __future__ import annotations
import json

from nooch_village import cockpit
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


def _setup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "human_inbox.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    (data / "library.json").write_text(json.dumps({
        "vegan sneakers dames": {"status": "approved", "date": "2026-06-24", "function": "doelwit",
                                 "evidence": {"volume": 210, "opportunity": 210,
                                              "gsc_seen": False}},
        "vegan": {"status": "approved", "date": "2026-06-24", "function": "volg",
                  "evidence": {"volume": 1220000, "trend_pct": 12.5}},
    }), encoding="utf-8")
    (data / "competitor_brands.json").write_text(json.dumps(
        {"candidates": {}, "confirmed": ["Veja", "LØCI"], "rejected": []}), encoding="utf-8")
    (data / "competitor_news.json").write_text(json.dumps(
        {"Veja": {"title": "VEJA lanceert nieuwe sneaker", "link": "http://x", "date": "2026-01-21"}}),
        encoding="utf-8")
    (data / "noochie_daily.json").write_text(json.dumps(
        {"verdict": "niet_ok", "oordeel": "Field Note adviseert ads", "date": "2026-06-25"}),
        encoding="utf-8")
    # competitor_brands settings (config) lukt niet via gather (leest settings.ini); we testen
    # de monitor-render via de confirmed + news direct.
    return cockpit.gather(str(data))


def test_woordenschat_split_en_concurrent_monitor(tmp_path):
    snap = _setup(tmp_path)
    page = cockpit.render_html(snap, csrf_token="t")

    # Woordenschat: doelwit met kans, seed met trend%
    assert "Doelwit-woorden" in page and "Volg-woorden" in page
    assert "vegan sneakers dames" in page and "210" in page
    assert "12.5%" in page                                    # seed-trend
    # Concurrent-monitor toont álle gemonitorde merken + laatste nieuwsfeit (of 'geen')
    assert "Gemonitord — alle concurrenten" in page
    assert "Veja" in page and "VEJA lanceert nieuwe sneaker" in page
    assert "LØCI" in page and "geen recent nieuws opgehaald" in page


def test_weekrapport_kwantitatief_met_noochie(tmp_path):
    snap = _setup(tmp_path)
    page = cockpit.render_html(snap, csrf_token="t")
    assert "Weekrapport" in page
    assert "Noochie vandaag" in page and "Field Note adviseert ads" in page
