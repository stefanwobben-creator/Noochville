"""SeedScheduler — spaced repetition: nieuw/productief vaak, uitgekauwd zelden. Pure logica."""
from __future__ import annotations

from nooch_village.keyword_scheduler import SeedScheduler


def test_nieuwe_zaadwoorden_eerst_en_budget(tmp_path):
    s = SeedScheduler(str(tmp_path / "s.json"), budget=2)
    s.tick()
    assert s.select(["a", "b", "c"]) == ["a", "b"]      # alle nieuw (due 0), budget 2


def test_saai_woord_zakt_naar_langer_interval(tmp_path):
    s = SeedScheduler(str(tmp_path / "s.json"), budget=5)
    s.tick()                                            # run 1
    s.select(["x"]); s.record("x", produced_new=False)  # saai → interval 2, due = 1+2 = 3
    s.tick()                                            # run 2: due 3 > 2 → niet aan de beurt
    assert "x" not in s.select(["x"])
    s.tick()                                            # run 3: due 3 <= 3 → wel
    assert "x" in s.select(["x"])


def test_productief_blijft_vaak_aan_de_beurt(tmp_path):
    s = SeedScheduler(str(tmp_path / "s.json"), budget=5)
    s.tick(); s.select(["x"]); s.record("x", produced_new=False)   # interval 2
    s.tick(); s.tick()                                  # naar run 3 (due)
    s.select(["x"]); s.record("x", produced_new=True)   # productief → interval terug naar 1
    s.tick()                                            # run 4: due = 3+1 = 4 → aan de beurt
    assert "x" in s.select(["x"])


def test_interval_heeft_een_plafond(tmp_path):
    s = SeedScheduler(str(tmp_path / "s.json"), budget=5, max_interval=4)
    for _ in range(8):
        s.tick()
        if "x" in s.select(["x"]):
            s.record("x", produced_new=False)
    assert s._state["seeds"]["x"]["interval"] <= 4


def test_produced_new_telt_alleen_schoen_domein():
    # de scheduler-opbrengst negeert off-domein ruis, zodat brede ruis-zaadwoorden wegzakken
    from nooch_village.skills_impl.serpapi_trends import SerpapiTrendsSkill
    f = SerpapiTrendsSkill._produced_new
    assert f([{"query": "regenerative medicine"}, {"query": "vegan food"}], [], None) is False
    assert f([{"query": "vegan sneakers"}], [], None) is True       # schoen-relevant → productief


def test_state_blijft_bewaard(tmp_path):
    p = str(tmp_path / "s.json")
    s = SeedScheduler(p)
    s.tick(); s.select(["x"]); s.record("x", produced_new=False); s.save()
    s2 = SeedScheduler(p)
    assert s2.counter == 1 and "x" in s2._state["seeds"]
