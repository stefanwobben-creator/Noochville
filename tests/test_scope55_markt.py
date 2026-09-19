"""Scope 55 — markt en luisteren leveren records en zeggen eerlijk 'niets' (batch B van de
skill-review van 12 september 2026).

Gemeten aanleiding: alle elf markt-/luister-skills lazen bij "niets gevonden" of "bron kapot" als
`gelukt` — een echo van de invoer (`brands`, `windows`), een teller onder een ongecatalogiseerde
naam (`guides`, `scanned`) of een configwaarde (`currency`, `counts`) droeg de "inhoud". En de
records die er wél waren hadden geen strekking: het verslag toonde "• barefoot shoes" of ruwe JSON.

Dit bestand toetst wat de mens merkt: de classificatie (`Inhabitant._classify_result`), de
wall-note (`_deliverable_note`), het verslag (`project_verslag.inhoud_tekst`), de planner-poort
(`validate_payload`/`required_payload`) en de Trends-ladder (google_trends → serpapi_trends).
"""
from __future__ import annotations

import json
import logging
import os
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village import project_verslag
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition
from nooch_village.skills import Skill, SkillRegistry


# ── gereedschap ──────────────────────────────────────────────────────────────

class _Stub(Skill):
    cost = "free"

    def __init__(self, naam, result=None, fn=None):
        self.name = naam
        self.description = "stub"
        self._result, self._fn = result, fn

    def run(self, payload, context):
        return self._fn(payload) if self._fn else self._result


def _inw(*skills, tmp_path=None, dna=None):
    reg = SkillRegistry()
    for s in skills:
        reg.register(s)
    rec = Record(id="rol_a", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="test", skills=list(dna) if dna else [s.name for s in skills]),
                 source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0",
                                    "deliverable_conclusie_enabled": "0"},
                          rugzakken={}, data_dir=str(tmp_path) if tmp_path else "")
    return Inhabitant(rec, EventBus(name="t"), reg, ctx)


def _classify(result):
    return Inhabitant._classify_result(result)[0]


_GEHEIM = "SECRETKEY1234567890abc"


# ── 1. competitor_discover ───────────────────────────────────────────────────

def _discover(llm_out, *, text, guides=None):
    from nooch_village.skills_impl.competitor_discover import CompetitorDiscoverSkill
    skill = CompetitorDiscoverSkill()
    guides = guides if guides is not None else [{"title": "Best barefoot shoe brands 2026", "link": "https://g.example/x"}]
    with patch.object(skill, "_serpapi_guides", return_value=guides), \
         patch.object(skill, "_fetch_text", return_value=text), \
         patch("nooch_village.llm.reason", return_value=llm_out):
        return skill.run({"topic": "best barefoot shoe brands"}, SimpleNamespace(settings={}))


_GIDS = ("x" * 250 + " Our top pick is Vivobarefoot, a British brand with wide toe boxes. "
         "Wildling Shoes makes minimalist shoes in Germany. Nike is only mentioned as the mainstream contrast.")














# ── 2. competitor_news ───────────────────────────────────────────────────────

def _resp(text):
    return SimpleNamespace(text=text, raise_for_status=lambda: None)


_RSS_LEEG = '<?xml version="1.0"?><rss><channel></channel></rss>'
_RSS_GN = ('<?xml version="1.0"?><rss><channel><item>'
           '<title>Vivobarefoot opens repair hub - Footwear News</title><link>http://a</link>'
           '<pubDate>{d}</pubDate>'
           '<description>&lt;a href="http://a"&gt;Vivobarefoot opens repair hub&lt;/a&gt;&amp;nbsp;'
           '&lt;font color="#6f6f6f"&gt;Footwear News&lt;/font&gt;</description>'
           '<source url="https://footwearnews.com">Footwear News</source>'
           '</item></channel></rss>')








# ── 3. community_listening ───────────────────────────────────────────────────

def _listen_ctx(tmp_path, key=True):
    from nooch_village.buzz_observations import BuzzObservationStore
    from nooch_village.buzz_query_sets import BuzzQuerySets, seed_buzz_query_sets
    ctx = SimpleNamespace(settings=({"YOUTUBE_API_KEY": "k"} if key else {}), data_dir=str(tmp_path))
    ctx.buzz_query_sets = BuzzQuerySets(str(tmp_path / "sets.json"))
    seed_buzz_query_sets(ctx.buzz_query_sets)
    ctx.buzz_observations = BuzzObservationStore(str(tmp_path / "obs.jsonl"))
    return ctx


def _spy(rows=(), refuse=None):
    return SimpleNamespace(platform="x", fetch=lambda set_id, cfg, context, cache, opts:
                           {"rows": [dict(r, query_set_id=set_id) for r in rows], "refuse": refuse,
                            "requests": 0, "note": ""})


def _rij(n, title="Best barefoot shoes review"):
    return {"platform": "youtube", "permalink": f"https://youtube.com/watch?v=V{n}&lc=C{n}", "title": "",
            "fragment": f"comment {n}: been wearing these for a year", "score": n,
            "context_id": f"V{n}", "context_title": title, "query": "barefoot shoes"}
















def test_linkbuilding_zonder_onderwerp_blokkeert_bij_het_plannen_en_bij_het_draaien():
    from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
    s = LinkbuildingTargetsSkill()
    assert "linkbuilding_query" in s.validate_payload({"brands": ["x"]}, SimpleNamespace(settings={}))[0]
    assert s.validate_payload({"brands": ["x"]}, SimpleNamespace(settings={"linkbuilding_query": "q"})) == []
    assert s.validate_payload({"brands": ["x"], "query": "barefoot"}, SimpleNamespace(settings={})) == []
    res = s.run({"brands": ["x"]}, SimpleNamespace(settings={"SERPAPI_API_KEY": "k"}))
    assert _classify(res) == "fout" and "linkbuilding_query" in res["error"]
    assert "topic" in s.input_schema and "_GUIDE_QUERY" not in open(
        os.path.join(os.path.dirname(project_verslag.__file__), "skills_impl", "linkbuilding.py")).read()


def test_linkbuilding_geen_gidsen_is_leeg():
    from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
    with patch("nooch_village.web_read.serpapi_search", return_value=[]):
        res = LinkbuildingTargetsSkill().run({"brands": ["x"], "topic": "niche"},
                                             SimpleNamespace(settings={"SERPAPI_API_KEY": "k"}))
    assert res["no_data"] and _classify(res) == "leeg"     # was: gelukt, ('metric', 'scanned')


# ── 5. keywords_everywhere ───────────────────────────────────────────────────

def _ke_response(data, credits=100):
    r = SimpleNamespace(status_code=200, raise_for_status=lambda: None)
    r.json = lambda: {"data": data, "credits": credits, "credits_consumed": len(data)}
    return r


def test_ke_string_wordt_niet_teken_voor_teken_verstuurd():
    from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill
    gezien = {}

    def post(url, headers=None, data=None, timeout=None):
        gezien["kw"] = [v for k, v in data if k == "kw[]"]
        return _ke_response([])

    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post", post):
        res = KeywordsEverywhereSkill().run({"kw": "barefoot shoes, minimalist shoes;barefoot shoes"},
                                            SimpleNamespace(settings={"KEYWORDS_EVERYWHERE_API_KEY": "k"}))
    assert gezien["kw"] == ["barefoot shoes", "minimalist shoes"]     # was: 14 losse letters
    assert res["no_data"] and res["reason"] == "no search volume for barefoot shoes, minimalist shoes"
    assert _classify(res) == "leeg"                                    # was: gelukt, ('text', 'currency')




# ── 6. google_trends ─────────────────────────────────────────────────────────

class _TrendReq:
    def __init__(self, *a, **kw):
        pass


def _trends_run(payload, fetch, settings=None, tmp_path=None):
    from nooch_village.skills_impl.trends import TrendsSkill
    skill = TrendsSkill()
    ctx = SimpleNamespace(settings=settings or {"trends_geo": "NL"}, data_dir=str(tmp_path) if tmp_path else "",
                          lexicon=None, library=None)
    with patch("pytrends.request.TrendReq", _TrendReq), patch.object(skill, "_fetch", side_effect=fetch), \
         patch("time.sleep"):
        return skill.run(payload, ctx)




def test_trends_alle_rijen_fout_is_fout_alle_rijen_leeg_is_leeg():
    import pandas as pd

    def kapot(pytrends, kw, geo, timeframe="today 12-m"):
        raise RuntimeError(f"max retries voor '{kw}' (geo={geo}) — 429")

    res = _trends_run({"keywords": ["a", "b"]}, kapot)
    assert res["ok"] is False and res["error"].startswith("all 2 lookup(s) failed: max retries")
    assert all(r.get("error") and not r.get("no_data") for r in res["rows"])
    assert _classify(res) == "fout"                        # was: gelukt, ('list', 'rows')

    def leeg(pytrends, kw, geo, timeframe="today 12-m"):
        return pd.DataFrame(), {}

    res = _trends_run({"keywords": "a, b"}, leeg)
    assert res["no_data"] and res["reason"] == "no interest data for a, b (geo NL, today 12-m)"
    assert _classify(res) == "leeg"


def test_trends_declareert_zijn_payload_voor_de_planner():
    from nooch_village.skills import ontbrekende_velden
    from nooch_village.skills_impl.trends import TrendsSkill, payload_terms
    assert ontbrekende_velden(TrendsSkill.required_payload, {}) == ["keywords|term"]
    assert ontbrekende_velden(TrendsSkill.required_payload, {"term": "x"}) == []
    assert "keywords" in TrendsSkill.input_schema and "term" in TrendsSkill.input_schema
    assert payload_terms({"keywords": "a, b;c", "term": "d"}) == ["a", "b", "c"]
    assert payload_terms({"term": " d "}) == ["d"] and payload_terms({}) == []


# ── 7. serpapi_trends als trede ──────────────────────────────────────────────

def test_serpapi_trends_leest_beide_sleutelnamen_en_de_term_payload(tmp_path):
    from nooch_village.skills_impl.serpapi_trends import SerpapiTrendsSkill, _key
    assert _key(SimpleNamespace(settings={"serpapi_api_key": "klein"})) == "klein"
    assert _key(SimpleNamespace(settings={"SERPAPI_API_KEY": "groot"})) == "groot"
    assert SerpapiTrendsSkill.required_payload == (("keywords", "term"),)

    class _Fake(SerpapiTrendsSkill):
        def __init__(self):
            self.calls = []

        def _get(self, params):
            self.calls.append(params["q"])
            if params["data_type"] == "TIMESERIES":
                return {"interest_over_time": {"timeline_data": [{"values": [{"extracted_value": 30}]},
                                                                 {"values": [{"extracted_value": 60}]}]}}
            return {"related_queries": {"top": [{"query": "barefoot shoes women", "extracted_value": 80}], "rising": []}}

    s = _Fake()
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"serpapi_api_key": "k", "trends_geo": "GB"},
                          lexicon=None, library=None)
    res = s.run({"term": "barefoot shoes"}, ctx)
    assert s.calls == ["barefoot shoes", "barefoot shoes"]
    assert res["rows"][0]["tekst"] == "interest 60 (stijgend); top: barefoot shoes women"
    assert res["source"] == "serpapi" and res["text"].startswith("1 of 1 term(s) with Google Trends data")

    class _Boom(SerpapiTrendsSkill):
        def _get(self, params):
            raise RuntimeError(f"SerpApi gaf HTTP 429 api_key={_GEHEIM}")

    res = _Boom().run({"keywords": ["a"]}, ctx)
    assert res["ok"] is False and _GEHEIM not in json.dumps(res) and _classify(res) == "fout"






def test_rugzakken_noemen_de_trede_waar():
    from nooch_village.evidence_ledger import SKILL_LADDERS
    treden = {t for rungs in SKILL_LADDERS.values() for t in rungs[1:]}
    assert {"google_patents", "semscholar_tldr", "serpapi_trends"} <= treden
    with open("config/rugzakken.json", encoding="utf-8") as f:
        rz = json.load(f)
    assert not any("serpapi_trends" in blok.get("skills", []) for k, blok in rz.items() if not k.startswith("_"))




# ── 9. het tweewekelijkse rapport verwacht alleen wat de catalogus actief noemt ─

def test_verwachte_bronnen_komen_uit_de_meetcatalogus():
    from nooch_village import biweekly_report, meetcatalog
    actief = meetcatalog.actieve_bronnen()
    assert "gdelt_tone" not in actief and "trends_categorie" not in actief and "werkoverleg" not in actief
    assert {"plausible", "gsc", "trends", "alphavantage", "keywordseverywhere"} <= set(actief)
    assert biweekly_report._verwacht() == actief
    assert not hasattr(biweekly_report, "_VERWACHT")


