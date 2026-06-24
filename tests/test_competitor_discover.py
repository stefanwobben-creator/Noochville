"""Concurrent-ontdekking: ruizige hint-extractie, mens-gated store, cockpit-bevestiging,
en de scout-discovery-stap. Geen netwerk (HTTP/skill gemockt)."""
from __future__ import annotations
import logging
import types
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.competitor_discover import CompetitorDiscoverSkill, _extract
from nooch_village.competitor_brands import CompetitorBrands
from nooch_village.inbox_actions import decide_competitor_candidate
from nooch_village.roles import ConcurrentScout
from nooch_village.cockpit import render_html


# ── pure extractie ─────────────────────────────────────────────────────────────

def test_extract_filtert_stopwoorden_en_bekende_merken():
    titles = [("10 Best Sustainable Sneaker Brands Like Veja: Cariuma and Saye", "http://x")]
    out = _extract(titles, ["Veja", "Moea"])
    namen = [c["brand"] for c in out]
    assert "Cariuma" in namen and "Saye" in namen
    assert "Best" not in namen and "Veja" not in namen and "Sneaker" not in namen


def test_extract_dedupliceert_en_limiteert():
    titles = [("Allbirds vs Allbirds and Cariuma", "http://x")]
    out = _extract(titles, [], limit=2)
    namen = [c["brand"] for c in out]
    assert namen.count("Allbirds") == 1 and len(out) <= 2


# ── skill run ──────────────────────────────────────────────────────────────────

_FEED = """<?xml version="1.0"?><rss><channel>
<item><title>Best vegan sneaker brands like Veja: Cariuma rises</title><link>http://a</link></item>
</channel></rss>"""


def test_run_geeft_kandidaten(monkeypatch):
    resp = SimpleNamespace(text=_FEED, raise_for_status=lambda: None)
    with patch("requests.get", return_value=resp):
        res = CompetitorDiscoverSkill().run({"brands": ["Veja"]}, SimpleNamespace(settings={}))
    assert res["ok"]
    assert any(c["brand"] == "Cariuma" for c in res["candidates"])


def test_run_fail_closed(monkeypatch):
    with patch("requests.get", side_effect=RuntimeError("netwerk weg")):
        res = CompetitorDiscoverSkill().run({"brands": ["Veja"]}, SimpleNamespace(settings={}))
    assert not res["ok"]


# ── store: mens-gated, hoofdletter-ongevoelige dedup ────────────────────────────

def test_store_add_confirm_reject(tmp_path):
    s = CompetitorBrands(str(tmp_path / "b.json"))
    assert s.add_candidate("Cariuma", "art", "http://x") is True
    assert s.add_candidate("cariuma") is False          # dedup hoofdletter-ongevoelig
    assert s.status("Cariuma") == "candidate"
    assert s.confirm("Cariuma") is True
    assert s.status("cariuma") == "confirmed" and "Cariuma" in s.confirmed()
    # opnieuw voorstellen kan niet meer (al bekend)
    assert s.add_candidate("Cariuma") is False

    assert s.add_candidate("Sneaker") is True
    assert s.reject("Sneaker") is True
    assert s.status("sneaker") == "rejected"
    assert s.add_candidate("Sneaker") is False          # ruis komt niet terug


def test_decide_competitor_candidate(tmp_path):
    s = CompetitorBrands(str(tmp_path / "b.json"))
    s.add_candidate("Saye", "art", "http://x")
    assert decide_competitor_candidate(s, "Saye", "confirm")["brand_status"] == "gemonitord"
    assert "Saye" in s.confirmed()
    assert not decide_competitor_candidate(s, "Saye", "huh")["ok"]


# ── cockpit-render ──────────────────────────────────────────────────────────────

def _snap(cands):
    return {"roster": [], "inbox": [], "projects": [], "insights": [], "library": [],
            "competitor_candidates": cands, "competitor_confirmed": ["Cariuma"],
            "generated_at": 0}


def test_render_toont_kandidaten_met_knoppen():
    html = render_html(_snap([{"brand": "Saye", "article": "vegan alternatives", "link": "http://x"}]),
                       csrf_token="tok")
    assert "Nieuw gespot" in html and "Saye" in html
    assert "brand_decide" in html and "monitor" in html
    assert "Cariuma" in html                              # bevestigde set zichtbaar


def test_render_read_only_zonder_knoppen():
    html = render_html(_snap([{"brand": "Saye", "article": "x", "link": "http://x"}]))
    assert "Saye" in html and "brand_decide" not in html


# ── scout-discovery-stap ────────────────────────────────────────────────────────

def test_scout_discovery_zet_kandidaten_klaar(tmp_path):
    s = SimpleNamespace()
    s.id = "concurrent_scout"
    s.dna = SimpleNamespace(skills=["competitor_news", "competitor_discover"])
    s.log = logging.getLogger("test.scout")
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s.use_skill = lambda cap, payload: {"ok": True, "candidates": [
        {"brand": "Cariuma", "article": "art", "link": "http://a"}]}
    s._run_discovery = types.MethodType(ConcurrentScout._run_discovery, s)
    store = CompetitorBrands(str(tmp_path / "b.json"))
    s._run_discovery(["Veja"], store)
    assert store.status("Cariuma") == "candidate"
    assert any(e.name == "competitor_candidate" for e in s._events)
