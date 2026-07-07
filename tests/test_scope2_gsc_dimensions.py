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
    assert len(got) == 10 and "afgekapt op 10" in caplog.text and "50 waarde(n) gedropt" in caplog.text


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
    assert imp[0]["meta"] == {"dimension": "query", "value": "vegan shoes"}       # generieke meta.value
    w2 = collect_daily_observations(reg, sources, obs, ctx, today=datetime.date(2026, 7, 8))
    assert w2 == [] and len([r for r in obs._read_all()
                             if r["metric"] == "gsc_impressions_day::vegan_shoes"]) == 1   # idempotent


# ── 2b: tegel-weergave (store-groepering, breakdown-fetch, keyword-dim aanbod) ────────────────────
from nooch_village import cockpit2
from nooch_village.metrics import MetricStore
from nooch_village.views import metrics as vm

C = "mother_earth__nooch"


def test_dimensioned_series_groepeert_op_keyword(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    for d, v in [("2026-07-06", 77), ("2026-07-07", 80)]:
        obs.record_daily("gsc", "gsc_impressions_day::vegan_shoes", v, bron="gsc", datum=d,
                         meta={"dimension": "query", "keyword": "vegan shoes"})
    obs.record_daily("gsc", "gsc_impressions_day::earth_shoes", 12, bron="gsc", datum="2026-07-07",
                     meta={"dimension": "query", "keyword": "earth shoes"})
    groups = obs.dimensioned_series("gsc_impressions_day", bron="gsc")
    assert set(groups) == {"vegan shoes", "earth shoes"}                     # rauwe keywords uit de meta
    assert [r["value"] for r in groups["vegan shoes"]] == [77, 80]           # oplopend op meetdag


def test_fetch_dim_keyword_geeft_breakdown(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    obs.record_daily("gsc", "gsc_impressions_day::vegan_shoes", 80, bron="gsc", datum="2026-07-07",
                     meta={"dimension": "query", "keyword": "vegan shoes"})
    obs.record_daily("gsc", "gsc_impressions_day::earth_shoes", 12, bron="gsc", datum="2026-07-07",
                     meta={"dimension": "query", "keyword": "earth shoes"})
    m = MetricStore(str(tmp_path / "m.json"))
    it = m.add_kpi("n1", "Vertoningen (GSC)", "n", origin="gsc", veld="impressions",
                   categorie="Zoekprestaties", aard="reeks", meetwijze="systeem", auto=True)
    st = types.SimpleNamespace(observations=obs, metrics=m, dd=str(tmp_path))
    res = vm._fetch(st, f"kpi:{it['id']}", "value", "keyword", None)
    assert res["kind"] == "breakdown"
    assert res["rows"] == [("vegan shoes", 80), ("earth shoes", 12)]         # gesorteerd op waarde desc


def test_keyword_dim_alleen_bij_dimensie_bron(tmp_path):
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    gsc = st.metrics.add_kpi(C, "Vertoningen (GSC)", "n", origin="gsc", veld="impressions",
                             categorie="Zoekprestaties", aard="reeks", meetwijze="systeem", auto=True)
    pla = st.metrics.add_kpi(C, "Bezoekers (Plausible)", "n", origin="plausible", veld="visitors",
                             categorie="Website", aard="reeks", meetwijze="systeem", auto=True)
    st2 = cockpit2._Stores(dd)
    srcs = {s["id"]: s for s in vm._sources_for(st2, st2.records.get(C))}
    gsc_dims = [d[0] for d in srcs[f"kpi:{gsc['id']}"]["dims"]]
    pla_dims = [d[0] for d in srcs[f"kpi:{pla['id']}"]["dims"]]
    assert "keyword" in gsc_dims and "keyword" not in pla_dims               # GSC heeft DIMENSION, Plausible niet
