"""Seed-opleving als spanning: enrich detecteert 'm, Harry duidt academisch, de scout zoekt de
nieuws-aanleiding (RSS), en de cockpit toont '▲ recent stijgend' + de mogelijke verklaring."""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.seed_surge_store import SeedSurges
from nooch_village import cockpit


def test_store_add_pending_investigate_explain(tmp_path):
    s = SeedSurges(str(tmp_path / "surges.json"))
    assert s.add("microplastics", locale="nl", pct=42.0) is True
    assert s.add("microplastics") is False                 # dedup op term
    assert [x["term"] for x in s.pending()] == ["microplastics"]
    s.set_explanation("microplastics", {"title": "EU verbiedt microplastics", "link": "x"})
    s.mark_investigated("microplastics")
    assert s.pending() == []                                # niet meer 'new'
    assert s.all()["microplastics"]["explanation"]["title"] == "EU verbiedt microplastics"


def test_enrich_signaleert_opleving(monkeypatch, tmp_path):
    from nooch_village import library_enrich

    data = {"microplastics": {"status": "approved", "function": "volg", "evidence": {}}}

    class FakeKE:
        def run(self, p, c):
            return {"keywords": [{"vol": 135000, "competition": 0.05}]}

    class FakeGSC:
        def run(self, p, c):
            return {"rows": []}

    class FakeTrends:
        def series(self, term, context, timeframe="today 5-y"):
            return [50] * 24 + [80, 85, 90]                # aanhoudende recente stijging

    monkeypatch.setattr(
        "nooch_village.skills_impl.keywords_everywhere.KeywordsEverywhereSkill", FakeKE)
    monkeypatch.setattr("nooch_village.skills_impl.gsc.GscPerformanceSkill", FakeGSC)
    monkeypatch.setattr("nooch_village.skills_impl.serpapi_trends.SerpapiTrendsSkill", FakeTrends)

    class Lib:
        def __init__(self, d):
            self._d = d
        def all(self):
            return self._d
        def status(self, w):
            return self._d.get(w)
        def set_evidence(self, w, u):
            self._d[w]["evidence"] = {**self._d[w]["evidence"], **u}
            return self._d[w]

    ctx = SimpleNamespace(settings={"ke_country": ""}, data_dir=str(tmp_path))
    library_enrich.enrich_library(Lib(data), ctx, sleep=0)

    assert data["microplastics"]["evidence"]["recent_surge"] is True
    surges = json.load(open(tmp_path / "seed_surges.json"))
    assert "microplastics" in surges and surges["microplastics"]["status"] == "new"


def test_enrich_herberekent_uit_opgeslagen_reeks_zonder_api(monkeypatch, tmp_path):
    """Bij een al opgeslagen reeks: geen nieuwe Trends-call, maar de richting wordt wél
    (her)berekend — hier een daling → recent_move 'dalend' + surge-store met richting."""
    from nooch_village import library_enrich

    series = [80] * 24 + [40, 35, 30, 32]                  # duidelijke daling
    data = {"vegan": {"status": "approved", "function": "volg",
                      "evidence": {"volume": 100, "trend_series": series}}}

    class FakeKE:
        def run(self, p, c):
            return {"keywords": [{"vol": 100, "competition": 0.1}]}

    class FakeGSC:
        def run(self, p, c):
            return {"rows": []}

    class FakeTrendsNoCall:
        def series(self, *a, **k):
            raise AssertionError("geen API-call verwacht als de reeks al bestaat")

    monkeypatch.setattr(
        "nooch_village.skills_impl.keywords_everywhere.KeywordsEverywhereSkill", FakeKE)
    monkeypatch.setattr("nooch_village.skills_impl.gsc.GscPerformanceSkill", FakeGSC)
    monkeypatch.setattr(
        "nooch_village.skills_impl.serpapi_trends.SerpapiTrendsSkill", FakeTrendsNoCall)

    class Lib:
        def __init__(self, d):
            self._d = d
        def all(self):
            return self._d
        def status(self, w):
            return self._d.get(w)
        def set_evidence(self, w, u):
            self._d[w]["evidence"] = {**self._d[w]["evidence"], **u}
            return self._d[w]

    ctx = SimpleNamespace(settings={"ke_country": ""}, data_dir=str(tmp_path))
    library_enrich.enrich_library(Lib(data), ctx, sleep=0)

    assert data["vegan"]["evidence"]["recent_move"] == "dalend"
    assert data["vegan"]["evidence"]["recent_surge"] is False
    surges = json.load(open(tmp_path / "seed_surges.json"))
    assert surges["vegan"]["direction"] == "dalend"


def test_scout_explain_surge_zet_verklaring(tmp_path):
    from nooch_village.roles import ConcurrentScout
    import types
    from nooch_village.event_bus import Event

    SeedSurges(str(tmp_path / "seed_surges.json")).add("microplastics")

    s = SimpleNamespace(id="concurrent_scout", log=__import__("logging").getLogger("t"))
    s.context = SimpleNamespace(data_dir=str(tmp_path))
    s.dna = SimpleNamespace(skills=["competitor_news"])
    s._events = []
    s.bus = SimpleNamespace(publish=lambda e: s._events.append(e))
    s.use_skill = lambda name, payload: {"items": [
        {"title": "EU scherpt microplastics-regels aan", "link": "http://x", "date": "2026-06-20"},
        {"title": "ouder bericht", "link": "http://y", "date": "2026-01-01"}]}
    s._explain_surge = types.MethodType(ConcurrentScout._explain_surge, s)

    s._explain_surge(Event("seed_surge_sensed", {"term": "microplastics"}, "harry"))

    surges = json.load(open(tmp_path / "seed_surges.json"))
    assert surges["microplastics"]["explanation"]["title"] == "EU scherpt microplastics-regels aan"
    assert any(e.name == "seed_surge_explanation" for e in s._events)


def test_cockpit_toont_surge_badge_en_verklaring(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "human_inbox.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    (data / "library.json").write_text(json.dumps({
        "microplastics": {"status": "approved", "function": "volg", "date": "2026-06-24",
                          "evidence": {"volume": 135000, "trend_state": "stabiel",
                                       "trend_series": [50] * 24 + [80, 85, 90],
                                       "recent_surge": True}},
    }), encoding="utf-8")
    (data / "seed_surges.json").write_text(json.dumps({
        "microplastics": {"term": "microplastics", "status": "investigated",
                          "explanation": {"title": "EU verbiedt microplastics in cosmetica",
                                          "link": "http://x", "date": "2026-06-20"}}}),
        encoding="utf-8")
    page = cockpit.render_html(cockpit.gather(str(data)), csrf_token="t")
    assert "recent stijgend" in page
    assert "EU verbiedt microplastics in cosmetica" in page


def test_seed_linkt_naar_harry_duiding(tmp_path):
    from nooch_village.notes_store import NotesStore
    from nooch_village.insight import Insight, GroundingStatus
    data = tmp_path / "data"
    data.mkdir()
    for f in ("governance_records.json", "human_inbox.json", "projects.json"):
        (data / f).write_text("{}", encoding="utf-8")
    (data / "library.json").write_text(json.dumps({
        "microplastics": {"status": "approved", "function": "volg", "date": "2026-06-24",
                          "evidence": {"volume": 135000, "trend_state": "stabiel",
                                       "recent_move": "stijgend"}},
    }), encoding="utf-8")
    ns = NotesStore(str(data / "notes.json"))
    ns.add(Insight(id="card1", claim="Microplastics zijn sterk relevant: bronnen tonen milieu-impact.",
                   source="harry", word="microplastics", status=GroundingStatus.SUPPORTED,
                   grounds="OpenAlex", grounding_count=2))
    page = cockpit.render_html(cockpit.gather(str(data)), csrf_token="t")
    assert "🔬" in page and "/card?id=card1" in page          # link naar Harry's duiding
