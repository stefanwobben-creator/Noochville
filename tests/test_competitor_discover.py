"""Concurrent-ontdekking: ruizige hint-extractie, mens-gated store, cockpit-bevestiging,
en de scout-discovery-stap. Geen netwerk (HTTP/skill gemockt)."""
from __future__ import annotations
import logging
import types
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.competitor_discover import (
    CompetitorDiscoverSkill, _parse_brand_list, _strip_html)
from nooch_village.competitor_brands import CompetitorBrands
from nooch_village.inbox_actions import decide_competitor_candidate
from nooch_village.roles import ConcurrentScout
from nooch_village.cockpit import render_html


# ── pure helpers ────────────────────────────────────────────────────────────────

def test_parse_brand_list_filtert_ruis_en_bekende():
    out = _parse_brand_list("Veja, Cariuma, Wills Vegan Store, Nooch, Best", ["Veja"])
    assert "Cariuma" in out and "Wills Vegan Store" in out
    assert "Veja" not in out and "Nooch" not in out and "Best" not in out


def test_parse_brand_list_none_geeft_leeg():
    assert _parse_brand_list("NONE", []) == []
    assert _parse_brand_list("", []) == []


def test_strip_html():
    assert "Veja" in _strip_html("<p>featuring <b>Veja</b></p>") and "<" not in _strip_html("<p>x</p>")


# ── skill run (gids lezen + LLM-extractie) ──────────────────────────────────────

def _run_with(llm_out, *, text="x" * 300 + " Veja and Cariuma"):
    skill = CompetitorDiscoverSkill()
    with patch.object(skill, "_fetch_guides",
                      return_value=[{"title": "15 Best Vegan Sneakers - Good On You", "link": "http://g"}]), \
         patch.object(skill, "_fetch_text", return_value=text), \
         patch("nooch_village.llm.reason", return_value=llm_out):
        return skill.run({"brands": ["Veja"]}, SimpleNamespace(settings={}))


def test_run_extraheert_echte_merken_uit_gids():
    res = _run_with("Veja, Cariuma, Wills Vegan Store")
    namen = [c["brand"] for c in res["candidates"]]
    assert res["ok"]
    assert "Cariuma" in namen and "Wills Vegan Store" in namen and "Veja" not in namen


def test_run_fail_closed_zonder_llm():
    res = _run_with(None)
    assert res["ok"] and res["candidates"] == []        # geen LLM → geen rommel


def test_run_slaat_lege_pagina_over():
    res = _run_with("Veja, Cariuma", text="te kort")     # <200 tekens → overslaan
    assert res["ok"] and res["candidates"] == []


def test_run_gidsen_ophalen_faalt():
    skill = CompetitorDiscoverSkill()
    with patch.object(skill, "_fetch_guides", side_effect=RuntimeError("netwerk weg")):
        res = skill.run({"brands": []}, SimpleNamespace(settings={}))
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

def test_scout_gebruikt_gedeelde_competitor_store(tmp_path):
    # 'aanbieden in de village': de scout leest de gedeelde context.competitors-store,
    # zodat confirmed concurrenten voor élke rol beschikbaar zijn.
    store = CompetitorBrands(str(tmp_path / "b.json"))
    store.add_candidate("Cariuma"); store.confirm("Cariuma")
    s = SimpleNamespace(context=SimpleNamespace(competitors=store, data_dir=str(tmp_path)))
    bound = types.MethodType(ConcurrentScout._brands_store, s)
    assert bound() is store and "Cariuma" in bound().confirmed()


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
