"""Scope 4: Plausible als tweede dimensie-bron (country). Contract (visit:country-breakdown, property+datum),
config-selectie + cap + drop-log, collector-idempotentie, backfill-idempotentie (gaten blijven gaten), en de
tegel die 'per land' aanbiedt náást GSC 'per keyword'."""
from __future__ import annotations
import datetime
import logging
import types

from nooch_village.observations import ObservationStore
from nooch_village.source_status import SourceStatusStore
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.collector import collect_daily_observations, _dimension_values
import nooch_village.backfill as bf


def _ctx(**settings):
    base = {"PLAUSIBLE_API_KEY": "k", "PLAUSIBLE_SITE_ID": "s"}
    base.update(settings)
    return types.SimpleNamespace(settings=base, library=None)


# ── (1) contract + exacte match + gat ────────────────────────────────────────
def test_plausible_country_contract_match_en_gat():
    s = PlausibleSkill()
    assert s.DIMENSION == "country"
    cap = {}

    def fake_get(params):
        cap["p"] = params
        return [{"country": "NL", "visitors": 31, "pageviews": 60, "visit_duration": 100, "bounce_rate": 55},
                {"country": "XX", "visitors": 5, "pageviews": 5}]
    out = s.daily_dimension_values(_ctx(), "2026-07-06", ["NL", "ES"], _get=fake_get)
    assert cap["p"]["property"] == "visit:country" and cap["p"]["date"] == "2026-07-06"    # contract
    assert out[("visitors", "NL")] == 31 and out[("bounce_rate", "NL")] == 55
    assert not any(k[1] == "ES" for k in out)          # ES niet in respons → gat
    assert not any(k[1] == "XX" for k in out)          # XX niet gecureerd → genegeerd


def test_plausible_country_fail_closed():
    s = PlausibleSkill()
    boom = lambda p: (_ for _ in ()).throw(RuntimeError("500"))
    assert s.daily_dimension_values(_ctx(), "2026-07-06", ["NL"], _get=boom) == {}
    assert s.daily_dimension_values(_ctx(), "2026-07-06", [], _get=boom) == {}     # geen landen → geen call


# ── (2) config-selectie + cap + drop-log ──────────────────────────────────────
def test_country_selectie_genormaliseerd_uit_config():
    assert _dimension_values(_ctx(plausible_dimension_countries="nl, be , de"), "country") == ["NL", "BE", "DE"]


def test_country_default_lijst():
    assert _dimension_values(_ctx(), "country") == ["NL", "BE", "DE", "FR", "ES", "GB", "US"]


def test_country_cap_en_drop_log(caplog):
    ctx = _ctx(plausible_dimension_countries=",".join(f"C{i:02d}" for i in range(20)),
               plausible_dimension_max="5")
    with caplog.at_level(logging.WARNING):
        got = _dimension_values(ctx, "country")
    assert len(got) == 5 and "dimensie 'country' afgekapt op 5" in caplog.text and "15 waarde(n) gedropt" in caplog.text


# ── (4) collector + backfill idempotent ──────────────────────────────────────
class _FakePlausible(PlausibleSkill):
    lag_days = 0

    def is_configured(self, context): return True
    def daily_values(self, context, datum):
        return {"visitors": None, "pageviews": None, "visit_duration": None, "bounce_rate": None}
    def daily_dimension_values(self, context, datum, countries, *, _get=None):
        return {("visitors", "NL"): int(datum[-2:]), ("pageviews", "NL"): 60}   # per-dag verschillend


class _Reg:
    def __init__(self, s): self._s = s
    def all(self): return self._s


def test_collector_plausible_country_met_meta_idempotent(tmp_path):
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    sources = SourceStatusStore(str(tmp_path / "s.json")); sources.set_active("plausible", True)
    ctx = _ctx(plausible_dimension_countries="NL")
    reg = _Reg([_FakePlausible()])
    collect_daily_observations(reg, sources, obs, ctx, today=datetime.date(2026, 7, 8))
    nl = [r for r in obs._read_all() if r["metric"] == "plausible_visitors_day::nl"]
    assert nl and nl[0]["meta"] == {"dimension": "country", "value": "NL"}       # generieke meta.value
    assert collect_daily_observations(reg, sources, obs, ctx, today=datetime.date(2026, 7, 8)) == []  # idempotent


def test_backfill_dimensions_idempotent_en_per_dag(tmp_path, monkeypatch):
    monkeypatch.setitem(bf.BACKFILL_SOURCES, "plausible", _FakePlausible)
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    ctx = _ctx(plausible_dimension_countries="NL")
    r1 = bf.backfill_dimensions("plausible", "2026-07-01", obs, ctx, today=datetime.date(2026, 7, 5), sleep=0)
    assert r1["written"] > 0 and r1["dimension"] == "country"
    nl = obs.dimensioned_series("plausible_visitors_day", bron="plausible")["NL"]
    assert [x["value"] for x in nl] == [1, 2, 3, 4]                              # per-dag (01..04 = today-1)
    r2 = bf.backfill_dimensions("plausible", "2026-07-01", obs, ctx, today=datetime.date(2026, 7, 5), sleep=0)
    assert r2["written"] == 0 and r2["skipped"] > 0                              # idempotent, geen duplicaten


# ── (5) tegel: twee gedimensioneerde bronnen (GSC per keyword + Plausible per land) ──────────────
def test_tegel_biedt_keyword_en_land_en_breakdown(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views import metrics as vm
    C = "mother_earth__nooch"
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
    assert "keyword" in gsc_dims and "keyword" not in pla_dims                   # elk zijn eigen dim
    assert "country" in pla_dims and "country" not in gsc_dims
    # de breakdown-fetch werkt voor de land-dimensie
    st2.observations.record_daily("plausible", "plausible_visitors_day::nl", 31, bron="plausible",
                                  datum="2026-07-06", meta={"dimension": "country", "value": "NL"})
    res = vm._fetch(cockpit2._Stores(dd), f"kpi:{pla['id']}", "value", "country", None)
    assert res["kind"] == "breakdown" and ("NL", 31) in res["rows"]
