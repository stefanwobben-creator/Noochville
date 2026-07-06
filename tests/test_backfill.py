"""Backfill-mechanisme (fase 1: Plausible). Loopt per periode de historische waarde op en schrijft
idempotent via record_daily — zelfde sleutel als de collector, dus geen duplicaten/botsingen. De
contract-test bewijst dat de skill de meegegeven datum écht meestuurt (geen 'herhaal gisteren')."""
from __future__ import annotations
import datetime
import types

import pytest

from nooch_village import backfill as bf
from nooch_village.backfill import backfill, BackfillError, _periods
from nooch_village.observations import ObservationStore
from nooch_village.skills import DataSourceSkill


class FakeFlux(DataSourceSkill):
    SOURCE = "fake"
    kind = "flux"
    required_env = ()

    def __init__(self, per_datum, freq="daily", lag=0):
        self._per = per_datum          # {datum: {field: value|None}}
        self._freq = freq
        self.lag_days = lag
        self.seen = []                 # welke datums zijn opgevraagd
        self._cfg = True

    def run(self, p, c): return {}
    def available_metrics(self, context=None): return ["a", "b"]
    def frequency(self, field): return self._freq
    def is_configured(self, c): return self._cfg

    def daily_values(self, context, datum):
        self.seen.append(datum)
        return dict(self._per.get(datum, {"a": None, "b": None}))


def _obs(tmp_path): return ObservationStore(str(tmp_path / "obs.jsonl"))
def _ctx(): return types.SimpleNamespace(settings={})
def _install(monkeypatch, fake): monkeypatch.setitem(bf.BACKFILL_SOURCES, "fake", lambda: fake)
def _d(s): return datetime.date.fromisoformat(s)


def test_periods_daily_inclusief_en_grenzen():
    assert list(_periods("daily", _d("2026-01-01"), _d("2026-01-03"))) == \
        ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert list(_periods("daily", _d("2026-01-05"), _d("2026-01-05"))) == ["2026-01-05"]  # één dag
    assert list(_periods("daily", _d("2026-01-05"), _d("2026-01-04"))) == []              # start>end → leeg
    with pytest.raises(BackfillError):
        list(_periods("weekly", _d("2026-01-01"), _d("2026-01-31")))                      # nog niet gebouwd


def test_datum_wordt_doorgegeven_niet_constant(tmp_path, monkeypatch):
    fake = FakeFlux({"2026-01-01": {"a": 10, "b": 1}, "2026-01-02": {"a": 20, "b": 2}})
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    res = backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-03"), sleep=0)  # end = 2026-01-02
    assert fake.seen == ["2026-01-01", "2026-01-02"]
    assert {(r["datum"], r["metric"], r["value"]) for r in obs._read_all()} == {
        ("2026-01-01", "fake_a_day", 10), ("2026-01-01", "fake_b_day", 1),
        ("2026-01-02", "fake_a_day", 20), ("2026-01-02", "fake_b_day", 2)}
    assert (res["written"], res["skipped"], res["lege_dagen"], res["dagen"]) == (4, 0, 0, 2)
    assert res["start"] == "2026-01-01" and res["end"] == "2026-01-02" and res["clamped"] is False


def test_idempotent_herdraaien(tmp_path, monkeypatch):
    fake = FakeFlux({"2026-01-01": {"a": 10, "b": 1}})
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-02"), sleep=0)
    n1 = len(obs._read_all())
    res2 = backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-02"), sleep=0)
    assert res2["written"] == 0 and res2["skipped"] == 2
    assert len(obs._read_all()) == n1                                # geen extra rijen


def test_botst_niet_met_collector_punt(tmp_path, monkeypatch):
    fake = FakeFlux({"2026-01-01": {"a": 10, "b": 1}, "2026-01-02": {"a": 20, "b": 2}})
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    obs.record_daily("fake", "fake_a_day", 20, bron="fake", datum="2026-01-02")    # collector schreef 'm al
    res = backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-03"), sleep=0)
    a02 = [r for r in obs._read_all() if r["metric"] == "fake_a_day" and r["datum"] == "2026-01-02"]
    assert len(a02) == 1                                             # geen duplicaat
    assert res["skipped"] == 1 and res["written"] == 3


def test_none_en_lege_dag(tmp_path, monkeypatch):
    fake = FakeFlux({
        "2026-01-01": {"a": 0, "b": None},        # a=0 is echte data; losse b-None is normaal
        "2026-01-02": {"a": None, "b": None},     # alles None → lege dag (verdacht)
    })
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    res = backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-03"), sleep=0)
    assert {(r["datum"], r["metric"]): r["value"] for r in obs._read_all()} == {
        ("2026-01-01", "fake_a_day"): 0}          # v==0 geschreven, b niet
    assert res["written"] == 1 and res["lege_dagen"] == 1 and res["dagen"] == 2


def test_end_grens_met_lag(tmp_path, monkeypatch):
    fake = FakeFlux({d: {"a": 1, "b": 1} for d in
                     ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]}, lag=3)
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-08"), sleep=0)   # end = 08-1-3 = 01-04
    assert fake.seen[-1] == "2026-01-04"
    assert "2026-01-05" not in fake.seen                            # today-lag nooit opgevraagd


def test_whitelist_poort_weigert_snapshot_en_onbekend(tmp_path):
    obs = _obs(tmp_path)
    with pytest.raises(BackfillError):
        backfill("openalex", "2026-01-01", obs, _ctx(), today=_d("2026-01-03"), sleep=0)   # snapshot
    with pytest.raises(BackfillError):
        backfill("onbekend", "2026-01-01", obs, _ctx(), today=_d("2026-01-03"), sleep=0)


def test_fase1_guard_weigert_weekly(tmp_path, monkeypatch):
    fake = FakeFlux({}, freq="weekly")
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    with pytest.raises(BackfillError):
        backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-08"), sleep=0)


def test_start_na_end_en_ongeldige_datum(tmp_path, monkeypatch):
    fake = FakeFlux({})
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    with pytest.raises(BackfillError):        # start ná de laatste volledige dag
        backfill("fake", "2026-01-09", obs, _ctx(), today=_d("2026-01-08"), sleep=0)
    with pytest.raises(BackfillError):        # ongeldige datum-opmaak
        backfill("fake", "09-01-2026", obs, _ctx(), today=_d("2026-01-08"), sleep=0)


def test_onconfigureerd_geen_crash(tmp_path, monkeypatch):
    fake = FakeFlux({"2026-01-01": {"a": None, "b": None}})
    fake._cfg = False
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    res = backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-01-02"), sleep=0)
    assert res["written"] == 0 and res["lege_dagen"] == res["dagen"] == 1


def test_horizon_klemt_start_af(tmp_path, monkeypatch):
    """Een bron met beperkte historie (GSC ~16 mnd) klemt de startdatum af naar zijn horizon, zodat je
    geen dagen bevraagt die de bron sowieso niet heeft."""
    fake = FakeFlux({d: {"a": 1, "b": 1} for d in
                     ["2026-07-03", "2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07"]})
    fake.backfill_history_days = 5                                  # bron bewaart 5 dagen
    _install(monkeypatch, fake)
    obs = _obs(tmp_path)
    # today=2026-07-08, lag0 → end=2026-07-07; horizon 5 → earliest=2026-07-03
    res = backfill("fake", "2026-01-01", obs, _ctx(), today=_d("2026-07-08"), sleep=0)
    assert res["clamped"] is True and res["start"] == "2026-07-03" and res["end"] == "2026-07-07"
    assert fake.seen[0] == "2026-07-03"                            # niet 2026-01-01


def test_contract_gsc_daily_values_stuurt_datum_mee():
    """Hard vereist voor whitelist-lidmaatschap van GSC: daily_values stuurt de meegegeven datum als
    startDate én endDate mee (dimensie=date) → 'herhaal een andere dag onder elke sleutel' onmogelijk."""
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    captured = {}

    def fake_query(body):
        captured.update(body)
        return {"rows": [{"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 3.2}]}

    ctx = types.SimpleNamespace(settings={"GSC_SITE": "sc-domain:nooch.earth"})
    vals = GscPerformanceSkill().daily_values(ctx, "2026-01-02", _query=fake_query)
    assert captured.get("startDate") == "2026-01-02" and captured.get("endDate") == "2026-01-02"
    assert captured.get("dimensions") == ["date"]
    assert vals == {"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 3.2}


def test_contract_plausible_daily_values_stuurt_datum_mee(monkeypatch):
    """Hard vereist voor whitelist-lidmaatschap: daily_values stuurt de meegegeven datum écht mee
    (period=day&date=<datum>), zodat 'herhaal gisteren onder elke sleutel' onmogelijk stil doorglipt."""
    from nooch_village.skills_impl import plausible as pl
    captured = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"results": {"visitors": {"value": 5}}}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured.update(params or {})
        return _Resp()

    monkeypatch.setattr(pl.requests, "get", fake_get)
    ctx = types.SimpleNamespace(settings={"PLAUSIBLE_API_KEY": "k", "PLAUSIBLE_SITE_ID": "s"})
    pl.PlausibleSkill().daily_values(ctx, "2026-01-02")
    assert captured.get("date") == "2026-01-02" and captured.get("period") == "day"
