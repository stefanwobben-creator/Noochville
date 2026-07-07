"""Scope 2 (datalaag): GSC per Library-doelwit-keyword. Sleutel-naad met dimensie-suffix, gecureerde
selectie (approved+doelwit) + cap + drop-log, gedimensioneerde GSC-fetch (exact match, gaten blijven
gaten), en de collector die de ::slug-reeksen mét meta wegschrijft (idempotent)."""
from __future__ import annotations
import datetime
import logging
import types

from nooch_village.observations import ObservationStore, dim_slug
from nooch_village.source_status import SourceStatusStore
from nooch_village.skills import DataSourceSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill
from nooch_village.collector import collect_daily_observations, _dimension_keywords
from nooch_village.views.metrics import _obs_key_for_indicator


# ── (a) sleutel-naad ─────────────────────────────────────────────────────────
def test_obs_key_met_en_zonder_dimensie():
    assert _obs_key_for_indicator("gsc", "impressions") == ("gsc_impressions_day", "gsc")
    assert _obs_key_for_indicator("gsc", "impressions", "vegan_shoes") == ("gsc_impressions_day::vegan_shoes", "gsc")
    assert dim_slug("Vegan Shoes!") == "vegan_shoes" and dim_slug("footwear") == "footwear"


# ── (b) GSC gedimensioneerde fetch: contract + exacte match + gaten ──────────
def _gsc_ctx():
    return types.SimpleNamespace(settings={"GSC_SITE": "sc-domain:x.nl"})


def test_gsc_dimension_contract_match_en_gat():
    s = GscPerformanceSkill()
    cap = {}

    def fake_query(body):
        cap["body"] = body
        return {"rows": [
            {"keys": ["vegan shoes"], "impressions": 77, "clicks": 2, "ctr": 0.026, "position": 11.2},
            {"keys": ["random query"], "impressions": 500, "clicks": 0, "ctr": 0.0, "position": 40.0}]}
    out = s.daily_dimension_values(_gsc_ctx(), "2026-07-06",
                                   ["vegan shoes", "sustainable footwear"], _query=fake_query)
    assert cap["body"]["startDate"] == "2026-07-06" and cap["body"]["dimensions"] == ["query"]  # contract
    assert out[("impressions", "vegan shoes")] == 77 and out[("clicks", "vegan shoes")] == 2
    assert ("impressions", "sustainable footwear") not in out          # niet in respons → gat
    assert not any(k[1] == "random query" for k in out)                # niet-gecureerde query genegeerd


def test_gsc_dimension_fail_closed():
    s = GscPerformanceSkill()
    boom = lambda b: (_ for _ in ()).throw(RuntimeError("429"))
    assert s.daily_dimension_values(_gsc_ctx(), "2026-07-06", ["vegan shoes"], _query=boom) == {}
    assert s.daily_dimension_values(_gsc_ctx(), "2026-07-06", [], _query=boom) == {}   # geen keywords → geen call


# ── (c) selectie + cap + drop-log ────────────────────────────────────────────
class _FakeLib:
    def __init__(self, e): self._e = e
    def all(self): return self._e
    def function_of(self, w): return self._e.get(w, {}).get("function", "volg")


def test_selectie_alleen_approved_doelwit():
    lib = _FakeLib({"vegan shoes": {"status": "approved", "function": "doelwit"},
                    "shoes": {"status": "approved", "function": "volg"},                  # volg → uit
                    "sustainable footwear": {"status": "pending", "function": "doelwit"}})  # niet approved → uit
    ctx = types.SimpleNamespace(library=lib, settings={})
    assert _dimension_keywords(ctx) == ["vegan shoes"]


def test_cap_en_drop_log(caplog):
    e = {f"kw {i:02d}": {"status": "approved", "function": "doelwit"} for i in range(60)}
    ctx = types.SimpleNamespace(library=_FakeLib(e), settings={"gsc_dimension_max": 10})
    with caplog.at_level(logging.WARNING):
        got = _dimension_keywords(ctx)
    assert len(got) == 10 and "afgekapt op 10" in caplog.text and "50 keyword(s) gedropt" in caplog.text


# ── (d) collector schrijft de ::slug-reeksen + meta, idempotent ──────────────
class _FakeGsc(DataSourceSkill):
    name = "fake_gsc"
    SOURCE = "gsc"
    DIMENSION = "query"

    def available_metrics(self, context=None): return ["impressions", "clicks"]
    def is_configured(self, context): return True
    def daily_values(self, context, datum): return {"impressions": None, "clicks": None}   # totalen leeg
    def daily_dimension_values(self, context, datum, keywords):
        return {("impressions", "vegan shoes"): 77, ("clicks", "vegan shoes"): 2}
    def run(self, payload, context): return {}


class _Reg:
    def __init__(self, skills): self._s = skills
    def all(self): return self._s


def test_collector_schrijft_dimensie_met_meta_idempotent(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    sources = SourceStatusStore(str(tmp_path / "s.json")); sources.set_active("gsc", True)
    ctx = types.SimpleNamespace(
        library=_FakeLib({"vegan shoes": {"status": "approved", "function": "doelwit"}}), settings={})
    reg = _Reg([_FakeGsc()])
    collect_daily_observations(reg, sources, obs, ctx, today=datetime.date(2026, 7, 8))
    imp = [r for r in obs._read_all() if r["metric"] == "gsc_impressions_day::vegan_shoes"]
    assert imp and imp[0]["value"] == 77
    assert imp[0]["meta"] == {"dimension": "query", "keyword": "vegan shoes"}     # rauw keyword in de meta
    w2 = collect_daily_observations(reg, sources, obs, ctx, today=datetime.date(2026, 7, 8))
    assert w2 == [] and len([r for r in obs._read_all()
                             if r["metric"] == "gsc_impressions_day::vegan_shoes"]) == 1   # idempotent
