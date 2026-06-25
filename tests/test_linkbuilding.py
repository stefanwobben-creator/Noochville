"""Linkbuilding-radar: diepe prioritering op de gids-tekst (concurrent-zonder-Nooch = hoog),
store, gevalideerde pitch/negeer-actie en cockpit-render. Geen netwerk (web_read gemockt)."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill, _assess_priority
from nooch_village.link_targets import LinkTargets
from nooch_village.inbox_actions import decide_link_target
from nooch_village.cockpit import render_html


# ── prioritering op de gids-tekst ───────────────────────────────────────────────

def test_noemt_concurrent_zonder_nooch_is_hoog():
    prio, mentions = _assess_priority("...featuring Veja and Komrads, both vegan...",
                                      ["Veja", "Komrads"])
    assert prio == "hoog" and "Veja" in mentions


def test_noemt_nooch_is_laag():
    prio, _ = _assess_priority("top brands include Nooch and Veja", ["Veja"])
    assert prio == "laag"


def test_geen_tekst_is_onbekend():
    assert _assess_priority("", ["Veja"])[0] == "onbekend"


def test_geen_concurrenten_geen_nooch_is_midden():
    assert _assess_priority("a long guide about shoes in general", ["Veja"])[0] == "midden"


# ── skill run (SerpAPI echte URL → body lezen → prioriteit) ─────────────────────

def _run(brands, *, guides, body, settings=None):
    skill = LinkbuildingTargetsSkill()
    ctx = SimpleNamespace(settings=settings if settings is not None else {"SERPAPI_API_KEY": "k"})
    with patch("nooch_village.web_read.serpapi_search", return_value=guides), \
         patch("nooch_village.web_read.fetch_text", return_value=body):
        return skill.run({"brands": brands}, ctx)


def test_skill_prioriteert_op_body_en_bron():
    res = _run(["Veja", "Komrads"],
               guides=[{"title": "15 Best Vegan Sneakers", "link": "https://www.goodonyou.eco/x"}],
               body="...we love Veja and Komrads, both vegan and sustainable...")
    assert res["ok"] and len(res["targets"]) == 1
    t = res["targets"][0]
    assert t["priority"] == "hoog" and t["source"] == "goodonyou.eco" and "Veja" in t["mentions"]


def test_skill_fail_closed_zonder_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    res = _run([], guides=[], body="", settings={})
    assert not res["ok"]


def test_skill_fail_closed_bij_serpapi_fout():
    skill = LinkbuildingTargetsSkill()
    ctx = SimpleNamespace(settings={"SERPAPI_API_KEY": "k"})
    with patch("nooch_village.web_read.serpapi_search", side_effect=RuntimeError("weg")):
        res = skill.run({"brands": []}, ctx)
    assert not res["ok"]


# ── store + beslissing ──────────────────────────────────────────────────────────

def test_store_dedup_en_pitch(tmp_path):
    s = LinkTargets(str(tmp_path / "l.json"))
    assert s.add_candidate("http://g", "Gids", "goodonyou.eco", "hoog") is True
    assert s.add_candidate("http://g") is False
    assert decide_link_target(s, "http://g", "pursue")["link_status"] == "te pitchen"
    assert s.pursued()[0]["link"] == "http://g"


def test_candidates_sorteren_hoog_eerst(tmp_path):
    s = LinkTargets(str(tmp_path / "l.json"))
    s.add_candidate("http://a", "A", "", "laag")
    s.add_candidate("http://b", "B", "", "hoog")
    assert s.candidates()[0]["priority"] == "hoog"


# ── cockpit-render ──────────────────────────────────────────────────────────────

def _snap(targets):
    return {"roster": [], "inbox": [], "projects": [], "insights": [], "library": [],
            "competitor_candidates": [], "competitor_confirmed": [],
            "link_candidates": targets, "link_pursued": [], "generated_at": 0}


def test_render_toont_doelwitten_met_knoppen():
    html = render_html(_snap([{"link": "http://g", "title": "15 Best Vegan Sneakers",
                               "source": "goodonyou.eco", "priority": "hoog", "mentions": ["Veja"]}]),
                       csrf_token="tok")
    assert "Linkbuilding" in html and "pitchen" in html and "link_decide" in html
    assert "hoog" in html and "Veja" in html


def test_render_read_only_zonder_knoppen():
    html = render_html(_snap([{"link": "http://g", "title": "X", "source": "", "priority": "midden",
                               "mentions": []}]))
    assert "link_decide" not in html
