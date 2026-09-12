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


def test_discover_geen_merknaam_leest_als_leeg_niet_als_vier():
    res = _discover("[]", text=_GIDS)
    assert res["no_data"] and res["candidates"] == [] and res["gescand"] == 1
    assert res["reason"] == "1 of 1 guides read, no brand names"
    assert _classify(res) == "leeg"                 # was: gelukt, archetype ('metric', 'guides')


def test_discover_zonder_model_is_een_fout():
    res = _discover(None, text=_GIDS)
    assert res["ok"] is False and "no model" in res["error"]
    assert _classify(res) == "fout"


def test_discover_zonder_gidsen_is_leeg():
    res = _discover("[]", text=_GIDS, guides=[])
    assert res["no_data"] and "no guide articles" in res["reason"]


def test_discover_records_dragen_het_zinnetje_uit_de_gids_en_de_text():
    res = _discover(json.dumps(["Vivobarefoot", "Wildling Shoes", "Xero Shoes"]), text=_GIDS)
    namen = [c["brand"] for c in res["candidates"]]
    assert namen == ["Vivobarefoot", "Wildling Shoes"]     # Xero staat niet in de tekst → grounding
    vivo = res["candidates"][0]
    assert vivo["citaat"].startswith("Our top pick is Vivobarefoot")
    assert res["text"].startswith("2 candidate brand(s) from 1 of 1 guides read")
    t = project_verslag.inhoud_tekst(res)
    assert t.splitlines()[0] == res["text"]
    assert "• Vivobarefoot (https://g.example/x) — Our top pick is Vivobarefoot" in t


def test_discover_prompt_is_engels_json_met_grounding_en_ladder():
    from nooch_village.skills_impl import competitor_discover as cd
    assert "Return ONLY a JSON array" in cd._PROMPT and "literally appear" in cd._PROMPT
    assert "Hieronder" not in cd._PROMPT
    skill = cd.CompetitorDiscoverSkill()
    gezien = {}

    def fake_reason(prompt, **kw):
        gezien.update(kw)
        return "[]"

    with patch.object(skill, "_serpapi_guides", return_value=[{"title": "g", "link": "https://g"}]), \
         patch.object(skill, "_fetch_text", return_value=_GIDS), \
         patch("nooch_village.llm.reason", fake_reason):
        skill.run({"topic": "barefoot", "ladder": "mistral:x"}, SimpleNamespace(settings={}))
    assert gezien["json_mode"] is True and gezien["max_tokens"] == cd._MAX_TOKENS
    assert gezien["ladder"] == "mistral:x" and gezien["call_site"] == "skill_competitor_discover"


def test_discover_parse_leest_json_en_kommalijst():
    from nooch_village.skills_impl.competitor_discover import _parse_brand_list
    assert _parse_brand_list('["Veja", "Cariuma", "Nooch"]', []) == ["Veja", "Cariuma"]
    assert _parse_brand_list("Veja, Cariuma", ["Veja"]) == ["Cariuma"]


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


def test_news_niets_gevonden_leest_als_leeg_niet_als_vier_merken(tmp_path):
    from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    with patch("requests.get", return_value=_resp(_RSS_LEEG)), patch("time.sleep"):
        res = CompetitorNewsSkill().run({"brands": ["Vivobarefoot", "Wildling", "Xero", "Vibram"]}, ctx)
    assert res["no_data"] and res["items"] == [] and res["total"] == 0
    assert res["reason"].startswith("no news about Vivobarefoot, Wildling, Xero, Vibram in the last 365 days")
    assert res["_brands"] == ["Vivobarefoot", "Wildling", "Xero", "Vibram"] and "brands" not in res
    assert _classify(res) == "leeg"                 # was: gelukt, ('list', 'brands') → "4 results"


def test_news_record_draagt_snippet_en_uitgever(tmp_path):
    from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill
    d = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    with patch("requests.get", return_value=_resp(_RSS_GN.format(d=d))):
        res = CompetitorNewsSkill().run({"brands": "Vivobarefoot"}, ctx)      # string → lijst
    it = res["items"][0]
    assert it["source"] == "Footwear News" and it["snippet"] == "Footwear News"   # description zonder de kop
    assert res["text"].startswith("1 news item(s) about 1 brand(s): Vivobarefoot 1 (30d)")
    assert "• Vivobarefoot opens repair hub - Footwear News (http://a) — Footwear News" in project_verslag.inhoud_tekst(res)


def test_news_zonder_merken_is_fout_en_de_puls_slaat_eerlijk_over(tmp_path):
    from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill
    from nooch_village.roles import ConcurrentScout
    res = CompetitorNewsSkill().run({}, SimpleNamespace(data_dir=str(tmp_path), settings={}))
    assert _classify(res) == "fout" and "competitor_brands" in res["error"]
    s = SimpleNamespace(id="concurrent_scout", log=logging.getLogger("t"), _events=[])
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s.use_skill = lambda cap, payload: (_ for _ in ()).throw(AssertionError("mag niet draaien"))
    types.MethodType(ConcurrentScout._run_news, s)([])
    done = [e for e in s._events if e.name == "competitor_pulse_completed"]
    assert done and done[0].data["ok"] is False and "geen merken" in done[0].data["error"]


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


def test_listening_stil_leest_als_leeg_met_de_samenvatting(tmp_path):
    from nooch_village.skills_impl import buzz_fetchers
    from nooch_village.skills_impl.community_listening import CommunityListeningSkill
    with patch.dict(buzz_fetchers.FETCHERS, {"youtube": _spy(), "bluesky": _spy()}):
        res = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, _listen_ctx(tmp_path))
    assert res["ok"] and res["no_data"] and res["reason"] == "youtube: 0 nieuw / bluesky: 0 nieuw / reddit: inactief"
    assert _classify(res) == "leeg"                 # was: gelukt, ('dictlist', 'counts')


def test_listening_alle_platforms_geweigerd_is_fout(tmp_path):
    from nooch_village.skills_impl import buzz_fetchers
    from nooch_village.skills_impl.community_listening import CommunityListeningSkill
    with patch.dict(buzz_fetchers.FETCHERS, {"youtube": _spy(refuse="BUZZ_NO_KEY"),
                                             "bluesky": _spy(refuse="BUZZ_RATE_LIMITED")}):
        res = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, _listen_ctx(tmp_path))
    assert res["ok"] is False and res["refuse"] == "BUZZ_NO_KEY" and "BUZZ_RATE_LIMITED" in res["error"]
    assert _classify(res) == "fout"


def test_listening_discovery_krijgt_ook_de_al_bekende_rijen(tmp_path):
    from nooch_village.skills_impl import buzz_fetchers
    from nooch_village.skills_impl.community_listening import CommunityListeningSkill
    ctx = _listen_ctx(tmp_path)
    rijen = [_rij(1), _rij(2)]
    with patch.dict(buzz_fetchers.FETCHERS, {"youtube": _spy(rijen), "bluesky": _spy()}):
        puls = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, ctx)     # de monitor-puls
        proj = CommunityListeningSkill().run({"queries": ["barefoot shoes"]}, ctx)              # het project daarna
        puls2 = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, ctx)    # de reeks blijft nieuw=nieuw
    assert puls["new"] == 2 and len(puls["observaties"]) == 2
    assert proj["new"] == 0 and proj["bekend"] == 2 and len(proj["observaties"]) == 2   # was: 0 observaties
    assert proj["text"].startswith("2 observation(s) about 'barefoot shoes'") and "2 al bekend" in proj["summary"]
    assert _classify(proj) == "gelukt"
    assert puls2["no_data"] and "bekend" not in puls2
    obs = proj["observaties"][0]
    assert obs["title"] == "Best barefoot shoes review" and "context" not in obs
    assert "• Best barefoot shoes review (https://youtube.com/watch?v=V1&lc=C1) — comment 1" in project_verslag.inhoud_tekst(proj)


def test_listening_cache_sleutel_per_set(tmp_path):
    """Dezelfde query in twee sets → twee fetches: de discovery-set van een project deelt zijn 6u-cache
    niet meer met de monitor-set (anders kreeg het project 0 rijen als de puls al draaide)."""
    from nooch_village.buzz_observations import BuzzCache
    from nooch_village.skills_impl.buzz_fetchers.bluesky import BlueskyFetcher
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path))
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append(params["q"])
        return SimpleNamespace(status_code=200, json=lambda: {"posts": []}, raise_for_status=lambda: None)

    with patch("requests.get", get), patch("time.sleep"):
        BlueskyFetcher().fetch("barefoot_ervaringen", {"active": True, "queries": ["barefoot"]}, ctx, cache, {"now": 1e9})
        BlueskyFetcher().fetch("discover:x", {"active": True, "queries": ["barefoot"]}, ctx, cache, {"now": 1e9})
        BlueskyFetcher().fetch("discover:x", {"active": True, "queries": ["barefoot"]}, ctx, cache, {"now": 1e9})
    assert calls == ["barefoot", "barefoot"]         # per set één keer; de derde zit in de cache


def test_listening_validate_noemt_de_bestaande_sets_en_laat_discovery_door(tmp_path):
    from nooch_village.skills_impl.community_listening import CommunityListeningSkill
    ctx = _listen_ctx(tmp_path)
    reden = CommunityListeningSkill().validate_payload({"query_set_id": "verzonnen"}, ctx)
    assert reden and "bestaande sets: barefoot_ervaringen" in reden[0] and "`queries`" in reden[0]
    assert CommunityListeningSkill().validate_payload({"query_set_id": "verzonnen", "queries": ["x"]}, ctx) == []
    # run() volgt dezelfde regel: onbekend id mét queries = discovery
    from nooch_village.skills_impl import buzz_fetchers
    with patch.dict(buzz_fetchers.FETCHERS, {"youtube": _spy(), "bluesky": _spy()}):
        res = CommunityListeningSkill().run({"query_set_id": "verzonnen", "queries": ["barefoot slijtage"]}, ctx)
    assert res["query_set_id"] == "discover:barefoot-slijtage"
    with patch.dict(buzz_fetchers.FETCHERS, {"youtube": _spy(), "bluesky": _spy()}):
        res = CommunityListeningSkill().run({"query_set_id": "verzonnen"}, ctx)
    assert res["refuse"] == "BUZZ_NO_SET" and "barefoot_ervaringen" in res["error"]


def test_youtube_commentthreads_fout_lekt_geen_sleutel(tmp_path, caplog, monkeypatch):
    """Het tweede HTTP-pad (commentThreads) bouwde zijn melding nog met raise_for_status (URL mét key=)."""
    from nooch_village.buzz_observations import BuzzCache
    from nooch_village.skills_impl.buzz_fetchers.youtube import YouTubeFetcher
    monkeypatch.setenv("YOUTUBE_API_KEY", _GEHEIM)
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path))

    def get(url, params=None, headers=None, timeout=None):
        if "/search" in url:
            return SimpleNamespace(status_code=200, text="", json=lambda: {"items": [{"id": {"videoId": "V"}, "snippet": {"title": "t"}}]})
        return SimpleNamespace(status_code=500, reason="Server Error", text=f"boom key={_GEHEIM}",
                               raise_for_status=lambda: (_ for _ in ()).throw(RuntimeError(f"500 for url ?key={_GEHEIM}")))

    with patch("requests.get", get), caplog.at_level(logging.WARNING):
        res = YouTubeFetcher().fetch("s", {"active": True, "queries": ["x"]}, ctx, BuzzCache(str(tmp_path / "c.json")), {"now": 1e9})
    assert res["rows"] == []
    assert any("BUZZ_FETCH_FAILED" in r.getMessage() for r in caplog.records)
    assert _GEHEIM not in caplog.text


# ── 4. linkbuilding_targets ──────────────────────────────────────────────────

def test_linkbuilding_onderwerp_uit_het_project_en_snippet_in_het_record():
    from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
    gezien = {}

    def search(query, key, num=10, **kw):
        gezien["query"] = query
        return [{"title": "Best barefoot shoe brands", "link": "https://goodonyou.eco/barefoot",
                 "snippet": "We tested 12 barefoot brands, from Vivobarefoot to Wildling."}]

    with patch("nooch_village.web_read.serpapi_search", search), \
         patch("nooch_village.web_read.fetch_text", return_value="… Vivobarefoot and Wildling …"):
        res = LinkbuildingTargetsSkill().run({"brands": ["Vivobarefoot", "Wildling"], "topic": "best barefoot shoe brands"},
                                             SimpleNamespace(settings={"SERPAPI_API_KEY": "k",
                                                                       "linkbuilding_query": "vegan sneakers guide"}))
    assert gezien["query"] == "best barefoot shoe brands"         # payload wint van de config
    t = res["targets"][0]
    assert t["priority"] == "hoog" and t["snippet"].startswith("We tested 12 barefoot brands")
    assert res["gescand"] == 1 and "scanned" not in res
    assert res["text"] == "1 guide page(s) for 'best barefoot shoe brands': 1 hoog; strongest pitch: goodonyou.eco"
    assert "• Best barefoot shoe brands (https://goodonyou.eco/barefoot) — We tested 12 barefoot brands" in project_verslag.inhoud_tekst(res)


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


def test_ke_rij_heeft_term_en_tekst_en_de_text_de_top_drie():
    from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill
    data = [{"keyword": "barefoot shoes", "vol": 12100, "cpc": {"value": "0.42"}, "competition": 0.31,
             "trend": [{"value": 9900}, {"value": 12100}]},
            {"keyword": "minimalist shoes", "vol": 2400, "cpc": {"value": "0"}, "competition": 0,
             "trend": []},
            {"keyword": "zero drop shoes", "vol": 5400, "cpc": {"value": "0.2"}, "competition": 0.1, "trend": []},
            {"keyword": "wide toe box", "vol": 800, "cpc": {"value": "0"}, "competition": 0, "trend": []}]
    with patch("nooch_village.skills_impl.keywords_everywhere.requests.post", return_value=_ke_response(data)):
        res = KeywordsEverywhereSkill().run({"kw": ["barefoot shoes", "minimalist shoes", "zero drop shoes", "wide toe box"]},
                                            SimpleNamespace(settings={"KEYWORDS_EVERYWHERE_API_KEY": "k"}))
    r0 = res["keywords"][0]
    assert r0["term"] == "barefoot shoes"
    assert r0["tekst"] == "12100/mo, cpc 0.42, competition 0.31, trend +22% over 12 months"
    assert res["keywords"][1]["tekst"] == "2400/mo"
    assert res["text"] == ("4 keyword(s) with search volume (global); top: barefoot shoes 12100/mo; "
                           "zero drop shoes 5400/mo; minimalist shoes 2400/mo")
    t = project_verslag.inhoud_tekst(res)
    assert "• barefoot shoes — 12100/mo, cpc 0.42, competition 0.31, trend +22% over 12 months" in t
    assert "{" not in t                                                # geen ruwe JSON meer


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


def test_trends_term_wordt_opgezocht_niet_het_lexicon_venster():
    import pandas as pd
    gezien = []

    def fetch(pytrends, kw, geo, timeframe="today 12-m"):
        gezien.append((kw, geo, timeframe))
        return pd.DataFrame({kw: [40, 62]}), {}

    res = _trends_run({"term": "barefoot shoes", "timeframe": "today 5-y"}, fetch)
    assert gezien == [("barefoot shoes", "NL", "today 5-y")]
    row = res["rows"][0]
    assert row["tekst"] == "interest 62 (stijgend)" and row["interest_latest"] == 62
    assert res["text"] == "1 of 1 term(s) with Google Trends data (today 5-y): barefoot shoes 62 (stijgend)"
    assert _classify(res) == "gelukt"
    assert "• barefoot shoes — interest 62 (stijgend)" in project_verslag.inhoud_tekst(res)


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


def test_trends_ladder_valt_door_naar_serpapi_zonder_dna_grant(tmp_path):
    """De échte trede: google_trends (429) → serpapi_trends met dezelfde payload, ook al staat
    serpapi_trends in geen rugzak en niet in het DNA — wie de kop mag voeren, mag de trede voeren."""
    from nooch_village.evidence_ledger import SKILL_LADDERS, EvidenceLedger
    assert SKILL_LADDERS["google_trends"] == ["google_trends", "serpapi_trends"]
    gezien = {}
    kop = _Stub("google_trends", {"ok": False, "error": "all 1 lookup(s) failed: 429", "rows": [{"term": "x", "error": "429"}]})
    trede = _Stub("serpapi_trends", fn=lambda p: gezien.setdefault("payload", p) and
                  {"rows": [{"term": "barefoot", "interest_latest": 55, "tekst": "interest 55 (vlak)"}],
                   "text": "1 of 1 term(s)", "source": "serpapi"})
    inw = _inw(kop, trede, tmp_path=tmp_path, dna=["google_trends"])
    assert "serpapi_trends" not in inw.effective_skills()
    res, bron = inw._use_skill_with_ladder("google_trends", {"term": "barefoot", "timeframe": "today 5-y"})
    assert bron == "serpapi_trends" and res["rows"][0]["interest_latest"] == 55
    assert gezien["payload"] == {"term": "barefoot", "timeframe": "today 5-y"}
    recs = EvidenceLedger(os.path.join(str(tmp_path), "evidence_ledger.jsonl")).all_records()
    assert [(r["source"], r["status"]) for r in recs] == [("google_trends", "fout"), ("serpapi_trends", "bevestigd")]
    assert not os.path.exists(os.path.join(str(tmp_path), "human_inbox.json"))   # geen valse escalatie


def test_trede_respecteert_de_domeinpoort(tmp_path):
    inw = _inw(_Stub("google_trends", {"ok": True}), _Stub("serpapi_trends", {"ok": True}), tmp_path=tmp_path,
               dna=["google_trends"])
    with patch("nooch_village.skill_meta.schrijft_in_domein", return_value="bibliotheek"):
        res = inw._run_rung("serpapi_trends", {})
    assert "domein" in res["error"]


def test_rugzakken_noemen_de_trede_waar():
    from nooch_village.evidence_ledger import SKILL_LADDERS
    treden = {t for rungs in SKILL_LADDERS.values() for t in rungs[1:]}
    assert {"google_patents", "semscholar_tldr", "serpapi_trends"} <= treden
    with open("config/rugzakken.json", encoding="utf-8") as f:
        rz = json.load(f)
    assert not any("serpapi_trends" in blok.get("skills", []) for k, blok in rz.items() if not k.startswith("_"))


# ── 8. trend_reindex ─────────────────────────────────────────────────────────

def test_reindex_escalatie_zonder_evaluatie_is_fout_en_de_puls_meldt_de_founder(tmp_path):
    from nooch_village.skills_impl.trend_reindex import TrendReindexSkill, _serpapi_fetch
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={"serpapi_api_key": "K"})
    skill = TrendReindexSkill()
    bad = _serpapi_fetch(skill._cfg(ctx), get_fn=lambda p: {"error": "out of searches"})
    res = skill.run({"terms": ["barefoot shoes"], "_fetch": bad}, ctx)
    assert res["ok"] is False and res["error"] == res["escalate"]["reason"] and "opgehaald" in res["error"]
    assert _classify(res) == "fout"                        # was: gelukt, ('list', 'watchlist')

    # de dagpuls van HarryHemp maakt er nog steeds de founder-heads-up van
    from nooch_village.roles import HarryHemp
    from nooch_village.notifications import NotifStore
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    reg = SkillRegistry()
    reg.register(_Stub("trend_reindex", res))
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["trend_reindex"]), source="seed")
    rec.persona = "Sid"
    harry = HarryHemp(rec, EventBus(name="t"),  reg,
                      SimpleNamespace(settings={"tijdgeest_interval_seconds": "0", "reflect_interval_seconds": "0"},
                                      data_dir=str(tmp_path), records=None, library=SimpleNamespace(status=lambda w: None)))
    harry._trend_reindex_pulse(None)
    fnd = NotifStore(str(tmp_path / "notifications.json")).for_targets([("role", FOUNDER_ROLE_ID)])
    assert len(fnd) == 1 and "trend-re-index" in fnd[0]["snippet"]


def test_reindex_rij_draagt_oordeel_en_zin(tmp_path):
    from nooch_village.skills_impl.trend_reindex import TrendReindexSkill, signal_tekst
    import datetime as dt
    import pandas as pd
    weeks = [dt.date(2024, 1, 7) + dt.timedelta(days=7 * i) for i in range(104)]

    def fetch(terms):
        vals = {t: [10.0] * 104 for t in terms}
        vals[terms[0]] = [10.0] * 52 + [40.0] * 52                     # 4x de baseline, aanhoudend
        df = pd.DataFrame(vals, index=pd.DatetimeIndex([pd.Timestamp(w) for w in weeks]))
        df["isPartial"] = [False] * 103 + [True]
        return df

    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    res = TrendReindexSkill().run({"terms": ["barefoot shoes"], "_fetch": fetch}, ctx)
    row = res["evaluated"][0]
    assert list(row)[:3] == ["term", "signal_type", "tekst"] and row["signal_type"] == "trend"
    assert row["tekst"].startswith("trend: ~4.0x its 2024 baseline, holds across")
    assert res["text"].startswith("1 term(s) re-indexed (override): 1 trend; signals: barefoot shoes")
    assert "• barefoot shoes — trend: ~4.0x its 2024 baseline" in project_verslag.inhoud_tekst(res)
    note = Inhabitant._format_record(row)
    assert note.startswith("term: barefoot shoes | signal_type: trend | tekst: trend: ~4.0x")
    assert "no signal" in signal_tekst("x", {"signal_type": "flat", "index_latest": 1.0, "base_year": 2024,
                                            "baseline": 10, "peak": 12})


# ── 9. het tweewekelijkse rapport verwacht alleen wat de catalogus actief noemt ─

def test_verwachte_bronnen_komen_uit_de_meetcatalogus():
    from nooch_village import biweekly_report, meetcatalog
    actief = meetcatalog.actieve_bronnen()
    assert "gdelt_tone" not in actief and "trends_categorie" not in actief and "werkoverleg" not in actief
    assert {"plausible", "gsc", "trends", "alphavantage", "keywordseverywhere"} <= set(actief)
    assert biweekly_report._verwacht() == actief
    assert not hasattr(biweekly_report, "_VERWACHT")


# ── 10. de wall-note toont leeswijzer én strekking ───────────────────────────

def test_wall_note_toont_de_text_en_het_citaat(tmp_path):
    inw = _inw(_Stub("competitor_discover", {}), tmp_path=tmp_path)
    res = {"ok": True, "gescand": 1, "gelezen": 1, "query": "q",
           "candidates": [{"brand": "Vivobarefoot", "article": "Best barefoot", "link": "https://g",
                           "citaat": "Our top pick is Vivobarefoot."}],
           "text": "1 candidate brand(s) from 1 of 1 guides read for 'q': Vivobarefoot"}
    status, arch = Inhabitant._classify_result(res)
    assert (status, arch) == ("gelukt", ("list", "candidates"))
    note = inw._deliverable_note({"text": "find brands", "skill": "competitor_discover"}, res, arch)
    regels = note.splitlines()
    assert regels[1] == res["text"]                                   # de leeswijzer direct onder de kop
    assert regels[2] == "• brand: Vivobarefoot | article: Best barefoot | link: https://g | citaat: Our top pick is Vivobarefoot."
