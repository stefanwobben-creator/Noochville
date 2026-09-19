"""Seed-opleving als spanning: enrich detecteert 'm, Harry duidt academisch, de scout zoekt de
nieuws-aanleiding (RSS), en de cockpit toont '▲ recent stijgend' + de mogelijke verklaring."""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.seed_surge_store import SeedSurges



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








