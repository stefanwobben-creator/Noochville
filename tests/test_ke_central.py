"""Gecentraliseerde KeywordsEverywhere-verrijking bij de Librarian: élke kandidaat
(GSC, SerpAPI-Trends, ngram) krijgt vóór de beoordeling echt zoekvolume aan zijn demand.
Faalt closed; respecteert een door de bron al geleverd volume."""
from __future__ import annotations
import logging
import types
from types import SimpleNamespace

from nooch_village.roles import Librarian

_BOUND = ("_enrich_volume", "_ke_country")


def _stub(use_skill_return, *, settings=None, has_ke=True):
    s = SimpleNamespace()
    s.dna = SimpleNamespace(skills=(["keywords_everywhere"] if has_ke else []))
    s.context = SimpleNamespace(settings=settings or {})
    s.log = logging.getLogger("test.lib")
    s._captured = {}
    def _use(cap, payload):
        s._captured["cap"] = cap
        s._captured["payload"] = payload
        return use_skill_return
    s.use_skill = _use
    for name in _BOUND:
        setattr(s, name, types.MethodType(getattr(Librarian, name), s))
    return s


def test_enrich_voegt_echt_volume_toe():
    s = _stub({"keywords": [{"keyword": "vegan sneakers", "vol": 1300}]})
    out = s._enrich_volume("vegan sneakers", {"signal": "positive"})
    assert out["volume"] == 1300
    assert s._captured["payload"]["kw"] == ["vegan sneakers"]   # één woord per kandidaat


def test_enrich_respecteert_bron_volume():
    s = _stub({"keywords": [{"keyword": "x", "vol": 999}]})
    out = s._enrich_volume("x", {"volume": 50})
    assert out["volume"] == 50           # bron leverde al volume
    assert s._captured == {}             # geen meting, geen credit


def test_enrich_fail_closed_zonder_key():
    s = _stub({"error": "KEYWORDS_EVERYWHERE_API_KEY ontbreekt"})
    out = s._enrich_volume("x", {"signal": "positive"})
    assert "volume" not in out           # geen volume, geen crash → beoordeelt zoals voorheen


def test_enrich_overslaan_zonder_dna_grant():
    s = _stub({"keywords": [{"keyword": "x", "vol": 9}]}, has_ke=False)
    out = s._enrich_volume("x", {})
    assert "volume" not in out
    assert s._captured == {}             # use_skill niet aangeroepen


def test_enrich_country_instelbaar():
    s = _stub({"keywords": [{"keyword": "x", "vol": 1}]}, settings={"ke_country": "be"})
    s._enrich_volume("x", {})
    assert s._captured["payload"]["country"] == "be"
