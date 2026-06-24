"""Linkbuilding-radar: prioritering (concurrent-zonder-Nooch = hoog), parser, store,
cockpit-render en de gevalideerde pitch/negeer-actie. Geen netwerk (HTTP gemockt)."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.skills_impl.linkbuilding import (
    LinkbuildingTargetsSkill, _assess_priority, _parse_guides, _publication)
from nooch_village.link_targets import LinkTargets
from nooch_village.inbox_actions import decide_link_target
from nooch_village.cockpit import render_html


# ── prioritering ────────────────────────────────────────────────────────────────

def test_noemt_concurrent_zonder_nooch_is_hoog():
    prio, mentions = _assess_priority("Best vegan sneakers: Veja and Komrads", ["Veja", "Komrads"])
    assert prio == "hoog" and "Veja" in mentions


def test_noemt_nooch_is_laag():
    prio, _ = _assess_priority("Top sustainable brands incl Nooch", ["Veja"])
    assert prio == "laag"


def test_geen_tekst_is_onbekend():
    assert _assess_priority("", ["Veja"])[0] == "onbekend"


def test_publication_uit_titel():
    assert _publication("The Ultimate Guide - Good On You") == "Good On You"


# ── parser + skill ────────────────────────────────────────────────────────────

_FEED = """<?xml version="1.0"?><rss><channel>
<item><title>15 Best Vegan Sneaker Brands - Good On You</title><link>http://g</link>
 <description>&lt;p&gt;featuring Veja and Komrads&lt;/p&gt;</description></item>
</channel></rss>"""


def test_skill_geeft_doelwit_met_prioriteit():
    resp = SimpleNamespace(text=_FEED, raise_for_status=lambda: None)
    with patch("requests.get", return_value=resp):
        res = LinkbuildingTargetsSkill().run({"brands": ["Veja", "Komrads"]}, SimpleNamespace(settings={}))
    assert res["ok"] and len(res["targets"]) == 1
    t = res["targets"][0]
    assert t["priority"] == "hoog" and t["source"] == "Good On You"


def test_skill_fail_closed():
    with patch("requests.get", side_effect=RuntimeError("weg")):
        res = LinkbuildingTargetsSkill().run({"brands": []}, SimpleNamespace(settings={}))
    assert not res["ok"]


# ── store + beslissing ──────────────────────────────────────────────────────────

def test_store_dedup_en_pitch(tmp_path):
    s = LinkTargets(str(tmp_path / "l.json"))
    assert s.add_candidate("http://g", "Gids", "Good On You", "hoog") is True
    assert s.add_candidate("http://g") is False              # dedup op link
    assert decide_link_target(s, "http://g", "pursue")["link_status"] == "te pitchen"
    assert s.pursued()[0]["link"] == "http://g"
    assert not decide_link_target(s, "http://g", "huh")["ok"]


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
                               "source": "Good On You", "priority": "hoog", "mentions": ["Veja"]}]),
                       csrf_token="tok")
    assert "Linkbuilding" in html and "pitchen" in html and "link_decide" in html
    assert "hoog" in html and "Veja" in html


def test_render_read_only_zonder_knoppen():
    html = render_html(_snap([{"link": "http://g", "title": "X", "source": "", "priority": "midden",
                               "mentions": []}]))
    assert "link_decide" not in html
