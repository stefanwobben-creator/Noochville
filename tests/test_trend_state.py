"""Seed-trend-toestand: een 5-jaars interesse-reeks → opkomend/stabiel/piek-voorbij/dalend.
Pure classifier (geen netwerk) + de serpapi-reeksparser + de cockpit-weergave."""
from __future__ import annotations

from nooch_village.trend_analysis import trend_state, trend_state_label
from nooch_village.skills_impl.serpapi_trends import _series_from_timeseries


def test_opkomend():
    rising = list(range(10, 70))                      # 60 mnd gestaag omhoog
    assert trend_state(rising) == "opkomend"


def test_dalend():
    falling = list(range(70, 10, -1))
    assert trend_state(falling) == "dalend"


def test_stabiel():
    flat = [50] * 60
    assert trend_state(flat) == "stabiel"


def test_piek_voorbij():
    # stijgt naar een piek halverwege, zakt daarna terug (maar netto niet sterk dalend)
    up = list(range(20, 100, 4))      # 20 punten omhoog naar ~96
    down = list(range(96, 30, -3))    # ~22 punten omlaag naar ~33
    assert trend_state(up + down) == "piek-voorbij"


def test_te_weinig_data():
    assert trend_state([1, 2, 3]) is None
    assert trend_state([]) is None


def test_label():
    assert "opkomend" in trend_state_label("opkomend")
    assert trend_state_label(None) == "—"


def test_series_parser():
    resp = {"interest_over_time": {"timeline_data": [
        {"values": [{"extracted_value": 10}]},
        {"values": [{"extracted_value": 20}]},
        {"values": [{"extracted_value": 30}]},
    ]}}
    assert _series_from_timeseries(resp) == [10, 20, 30]
    assert _series_from_timeseries({}) == []


def test_enrich_seed_krijgt_trend_state(monkeypatch):
    """Seed-woord wordt verrijkt met de 5-jaars trend-toestand; doelwit krijgt 'm niet."""
    from types import SimpleNamespace
    from nooch_village import library_enrich

    data = {
        "vegan":              {"status": "approved", "function": "volg", "evidence": {}},
        "vegan sneakers dames": {"status": "approved", "function": "doelwit", "evidence": {}},
    }

    class FakeKE:
        def run(self, p, c):
            return {"keywords": [{"vol": 500, "competition": 0.1}]}

    class FakeGSC:
        def run(self, p, c):
            return {"rows": []}

    class FakeTrends:
        def series(self, term, context, timeframe="today 5-y"):
            return list(range(10, 70))                    # gestage stijging → opkomend

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

    library_enrich.enrich_library(Lib(data), SimpleNamespace(settings={"ke_country": ""}), sleep=0)
    assert data["vegan"]["evidence"]["trend_state"] == "opkomend"
    assert "trend_state" not in data["vegan sneakers dames"]["evidence"]   # doelwit: geen seed-trend
