"""Fase 1 van het generieke schrijf-mechanisme: DataSourceSkill-contract, de generieke collector
(actief/inactief, due-check per verwachte periode, fail-closed), en de migratie (legacy visitors_day
→ plausible_visitors_day + Plausible actief). Testdata in de tmp-map."""
from __future__ import annotations
import datetime
import types

from nooch_village import cockpit2
from nooch_village.skills import DataSourceSkill, SkillRegistry
from nooch_village.collector import collect_daily_observations, migrate_data_sources, _expected_period


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


class _FakeSource(DataSourceSkill):
    name = "fake_src"
    SOURCE = "gsc"                       # bestaande data-source-id, maar zonder eigen creds nodig
    required_env = ()
    def __init__(self, vals): self._vals = vals
    def run(self, payload, context): return {}
    def available_metrics(self): return ["clicks", "impressions"]
    def is_configured(self, context): return True
    def daily_values(self, context, datum): return dict(self._vals)


def _ctx(): return types.SimpleNamespace(settings={})


def test_migratie_hernoemt_en_activeert_plausible(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    assert st.sources.active("plausible")                       # bootstrap zette 'm al actief
    st.observations.record_daily("wd", "visitors_day", 42, bron="plausible", datum="2026-07-04")
    migrate_data_sources(dd)
    rows = cockpit2._Stores(dd).observations.daily_series("plausible_visitors_day", bron="plausible")
    assert len(rows) == 1 and rows[0]["value"] == 42            # legacy → canoniek
    assert not cockpit2._Stores(dd).observations.daily_series("visitors_day", bron="plausible")


def test_collector_schrijft_alleen_actief_en_niet_none_idempotent(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.sources.set_active("gsc", True)
    reg = SkillRegistry(); reg.register(_FakeSource({"clicks": 100, "impressions": None}))
    today = datetime.date(2026, 7, 6)
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=today)
    assert w == [("gsc", "clicks", "2026-07-05")]              # alleen het niet-None-veld
    rows = cockpit2._Stores(dd).observations.daily_series("gsc_clicks_day", bron="gsc")
    assert len(rows) == 1 and rows[0]["value"] == 100
    # 2e run: datapunt bestaat al voor de verwachte periode → niets (idempotent/zelfherstellend)
    w2 = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                    cockpit2._Stores(dd).observations, _ctx(), today=today)
    assert w2 == []


def test_collector_slaat_inactieve_bron_over(tmp_path):
    dd = _dd(tmp_path)
    reg = SkillRegistry(); reg.register(_FakeSource({"clicks": 5, "impressions": 5}))
    # gsc NIET geactiveerd → geen writes
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=datetime.date(2026, 7, 6))
    assert w == []


def test_collector_actief_maar_onconfigureerd_schrijft_niet_en_zet_status(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd); st.sources.set_active("gsc", True)
    class _Unconf(_FakeSource):
        def is_configured(self, context): return False
    reg = SkillRegistry(); reg.register(_Unconf({"clicks": 9, "impressions": 9}))
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=datetime.date(2026, 7, 6))
    assert w == []                                             # geen write
    assert cockpit2._Stores(dd).sources.configured("gsc") is False   # status vastgelegd voor de UI


def test_datasource_contract_daily_values_subset(tmp_path):
    """Elke DataSourceSkill: daily_values-sleutels ⊆ available_metrics (contract-guard)."""
    from nooch_village.skills_impl.plausible import PlausibleSkill
    p = PlausibleSkill()
    vals = p.daily_values(_ctx(), "2026-07-05")               # geen creds → alle None, maar wel de juiste sleutels
    assert set(vals) <= set(p.available_metrics()) and set(vals) == set(p.available_metrics())
    assert p.frequency("visitors") == "daily" and p.SOURCE == "plausible"


def test_shopify_datasource_contract_en_failclosed():
    """Fase 2: ShopifySalesSkill is een DataSourceSkill met SOURCE='shopify'. daily_values is fail-closed
    per veld (geen creds → alle None) en de sleutels ⊆ available_metrics. is_configured checkt store +
    (token óf client_id+secret) — leest alleen, raakt SHOPIFY_API_SECRET (webhook) niet aan."""
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    sk = ShopifySalesSkill()
    assert isinstance(sk, DataSourceSkill) and sk.SOURCE == "shopify" and sk.frequency("orders") == "daily"
    vals = sk.daily_values(_ctx(), "2026-07-05")
    assert set(vals) == set(sk.available_metrics()) and all(v is None for v in vals.values())
    assert sk.is_configured(types.SimpleNamespace(settings={"SHOPIFY_STORE": "x", "SHOPIFY_TOKEN": "t"}))
    assert sk.is_configured(types.SimpleNamespace(
        settings={"SHOPIFY_STORE": "x", "SHOPIFY_CLIENT_ID": "c", "SHOPIFY_CLIENT_SECRET": "s"}))
    assert not sk.is_configured(types.SimpleNamespace(settings={"SHOPIFY_STORE": "x"}))
    assert not sk.is_configured(_ctx())


def test_shopify_blijft_inactief_tot_expliciete_activatie(tmp_path):
    """Shopify staat NIET default actief; de collector pakt 'm pas op na sources activate shopify."""
    from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
    dd = _dd(tmp_path)
    assert not cockpit2._Stores(dd).sources.active("shopify")     # default inactief
    reg = SkillRegistry(); reg.register(ShopifySalesSkill())
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=datetime.date(2026, 7, 6))
    assert w == []                                               # inactief → geen fetch/write


class _LaggedSource(_FakeSource):
    """Fake bron met vertraging (zoals GSC): de collector moet today − 1 − lag_days ophalen."""
    SOURCE = "gsc"
    lag_days = 3


def test_gsc_datasource_contract_failclosed_en_lag():
    """Fase 3: GscPerformanceSkill is een DataSourceSkill (SOURCE='gsc', lag_days=3). daily_values is
    fail-closed per veld (geen creds → alle None), sleutels ⊆ available_metrics; is_configured checkt
    site + bestaand token-bestand (unconfigured ≠ dood)."""
    import os
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    g = GscPerformanceSkill()
    assert isinstance(g, DataSourceSkill) and g.SOURCE == "gsc" and g.lag_days == 3
    ctx = types.SimpleNamespace(settings={}, data_dir="/tmp/none")
    vals = g.daily_values(ctx, "2026-07-02")
    assert set(vals) == set(g.available_metrics()) and all(v is None for v in vals.values())
    assert not g.is_configured(ctx)                                  # geen site/token → unconfigured


def test_collector_lag_haalt_beschikbare_dag_niet_gisteren(tmp_path):
    """Een bron met lag_days haalt de meest recente BESCHIKBARE dag (today − 1 − lag), niet gisteren —
    zodat GSC (2-3 dagen vertraging) wél vult. 'Geen datapunt voor gisteren' is dan normaal."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd); st.sources.set_active("gsc", True)
    reg = SkillRegistry(); reg.register(_LaggedSource({"clicks": 50, "impressions": 900}))
    today = datetime.date(2026, 7, 6)
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=today)
    # today − 1 − 3 = 2026-07-02, NIET gisteren (2026-07-05)
    assert ("gsc", "clicks", "2026-07-02") in w and ("gsc", "impressions", "2026-07-02") in w
    obs = cockpit2._Stores(dd).observations
    assert not obs.daily_series("gsc_clicks_day", bron="gsc") == []   # gevuld
    assert [r["datum"] for r in obs.daily_series("gsc_clicks_day", bron="gsc")] == ["2026-07-02"]
    # geen datapunt voor gisteren is prima (dat is niet 'due' bij een lag-bron)


def test_gsc_blijft_inactief_tot_activatie(tmp_path):
    from nooch_village.skills_impl.gsc import GscPerformanceSkill
    dd = _dd(tmp_path)
    assert not cockpit2._Stores(dd).sources.active("gsc")            # default inactief
    reg = SkillRegistry(); reg.register(GscPerformanceSkill())
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=datetime.date(2026, 7, 6))
    assert w == []


def test_expected_period_weekly_en_monthly():
    """De frequentie-bewuste periode-sleutel: weekly = maandag van de week, monthly = eerste van de
    maand, daily = vorige volledige dag (met lag teruggeschoven). Beide snapshot-sleutels meegebouwd."""
    from nooch_village.collector import _expected_period
    wed = datetime.date(2026, 7, 8)                       # woensdag
    assert _expected_period("weekly", wed) == "2026-07-06"     # maandag van die week
    assert _expected_period("monthly", wed) == "2026-07-01"    # eerste van de maand
    assert _expected_period("daily", wed) == "2026-07-07"      # vorige dag
    assert _expected_period("daily", wed, lag_days=3) == "2026-07-04"
    assert _expected_period("weekly", wed, lag_days=7) == "2026-06-29"   # maandag van de week ervoor


def test_openalex_datasource_contract_snapshot_failclosed(monkeypatch):
    """OpenAlex is een snapshot-DataSourceSkill: SOURCE='openalex', weekly, keyless (is_configured=True).
    daily_values legt de STAND vast (absolute tellers), fail-closed per veld, sleutels ⊆ available_metrics."""
    from nooch_village.skills_impl.openalex import OpenalexSkill
    sk = OpenalexSkill()
    assert isinstance(sk, DataSourceSkill) and sk.SOURCE == "openalex"
    assert sk.frequency("works") == "weekly" and sk.is_configured(_ctx())
    assert set(sk.available_metrics()) == {"works", "citations"}
    monkeypatch.setattr(sk, "_fetch_with_backoff",
                        lambda req: (_ for _ in ()).throw(RuntimeError("boom")))   # geen netwerk
    vals = sk.daily_values(_ctx(), "2026-07-06")
    assert set(vals) == set(sk.available_metrics()) and all(v is None for v in vals.values())
    monkeypatch.setattr(sk, "_fetch_with_backoff",
                        lambda req: {"results": [{"works_count": 1234, "cited_by_count": 56789}]})
    assert sk.daily_values(_ctx(), "2026-07-06") == {"works": 1234, "citations": 56789}


class _WeeklySnapshot(DataSourceSkill):
    name = "wk"; SOURCE = "openalex"; DEFAULT_FREQUENCY = "weekly"; required_env = ()
    def __init__(self, vals): self._vals = vals
    def run(self, payload, context): return {}
    def available_metrics(self): return ["works", "citations"]
    def is_configured(self, context): return True
    def daily_values(self, context, datum): return dict(self._vals)


def test_collector_weekly_snapshot_stand_onder_weeksleutel_idempotent(tmp_path):
    """Een weekly snapshot-bron legt de STAND vast onder de week-sleutel (maandag), één meting per week
    (idempotent); een volgende week is een nieuwe sleutel."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd); st.sources.set_active("openalex", True)
    reg = SkillRegistry(); reg.register(_WeeklySnapshot({"works": 1234, "citations": 56789}))
    obs = lambda: cockpit2._Stores(dd).observations
    srcs = lambda: cockpit2._Stores(dd).sources
    # woensdag 2026-07-08 → week-maandag 2026-07-06
    w = collect_daily_observations(reg, srcs(), obs(), _ctx(), today=datetime.date(2026, 7, 8))
    assert ("openalex", "works", "2026-07-06") in w and ("openalex", "citations", "2026-07-06") in w
    assert [r["value"] for r in obs().daily_series("openalex_works_day", bron="openalex")] == [1234]   # de STAND
    # zelfde week (vrijdag) → niets (één meting/week)
    assert collect_daily_observations(reg, srcs(), obs(), _ctx(), today=datetime.date(2026, 7, 10)) == []
    # volgende week (maandag 2026-07-13) → nieuwe meting onder nieuwe sleutel
    w3 = collect_daily_observations(reg, srcs(), obs(), _ctx(), today=datetime.date(2026, 7, 15))
    assert ("openalex", "works", "2026-07-13") in w3
    assert [r["datum"] for r in obs().daily_series("openalex_works_day", bron="openalex")] == ["2026-07-06", "2026-07-13"]


def test_openalex_blijft_inactief_tot_activatie(tmp_path):
    from nooch_village.skills_impl.openalex import OpenalexSkill
    dd = _dd(tmp_path)
    assert not cockpit2._Stores(dd).sources.active("openalex")
    reg = SkillRegistry(); reg.register(OpenalexSkill())
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=datetime.date(2026, 7, 8))
    assert w == []                                       # inactief → geen fetch/write


def test_semanticscholar_snapshot_contract_en_failclosed(monkeypatch):
    """Semantic Scholar is een snapshot-DataSourceSkill (SOURCE='semanticscholar', kind='snapshot',
    monthly, keyless → is_configured=True). daily_values legt de STAND vast (auteur paperCount/
    citationCount), fail-closed per veld, sleutels ⊆ available_metrics."""
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
    sk = SemanticScholarSkill()
    assert isinstance(sk, DataSourceSkill) and sk.SOURCE == "semanticscholar"
    assert sk.kind == "snapshot" and sk.frequency("papers") == "monthly" and sk.is_configured(_ctx())
    assert set(sk.available_metrics()) == {"papers", "citations"}
    monkeypatch.setattr(sk, "_fetch_with_backoff", lambda url, headers: "HTTP 500: boom")   # geen netwerk
    vals = sk.daily_values(_ctx(), "2026-07-01")
    assert set(vals) == set(sk.available_metrics()) and all(v is None for v in vals.values())
    monkeypatch.setattr(sk, "_fetch_with_backoff",
                        lambda url, headers: {"data": [{"paperCount": 312, "citationCount": 18450}]})
    assert sk.daily_values(_ctx(), "2026-07-01") == {"papers": 312, "citations": 18450}


class _MonthlySnapshot(DataSourceSkill):
    name = "ms"; SOURCE = "semanticscholar"; kind = "snapshot"; DEFAULT_FREQUENCY = "monthly"; required_env = ()
    def __init__(self, vals): self._vals = vals
    def run(self, payload, context): return {}
    def available_metrics(self): return ["papers", "citations"]
    def is_configured(self, context): return True
    def daily_values(self, context, datum): return dict(self._vals)


def test_collector_monthly_snapshot_stand_onder_maandsleutel_idempotent(tmp_path):
    """Een monthly snapshot legt de STAND vast onder de maand-sleutel (1e van de maand), één meting per
    maand (idempotent); een volgende maand is een nieuwe sleutel."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd); st.sources.set_active("semanticscholar", True)
    reg = SkillRegistry(); reg.register(_MonthlySnapshot({"papers": 312, "citations": 18450}))
    srcs = lambda: cockpit2._Stores(dd).sources
    obs = lambda: cockpit2._Stores(dd).observations
    w = collect_daily_observations(reg, srcs(), obs(), _ctx(), today=datetime.date(2026, 7, 20))
    assert ("semanticscholar", "citations", "2026-07-01") in w                 # 1e van juli
    assert [r["value"] for r in obs().daily_series("semanticscholar_papers_day", bron="semanticscholar")] == [312]
    # zelfde maand → niets (één meting/maand)
    assert collect_daily_observations(reg, srcs(), obs(), _ctx(), today=datetime.date(2026, 7, 28)) == []
    # volgende maand → nieuwe sleutel
    w3 = collect_daily_observations(reg, srcs(), obs(), _ctx(), today=datetime.date(2026, 8, 5))
    assert ("semanticscholar", "papers", "2026-08-01") in w3


def test_semanticscholar_blijft_inactief_tot_activatie(tmp_path):
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
    dd = _dd(tmp_path)
    assert not cockpit2._Stores(dd).sources.active("semanticscholar")
    reg = SkillRegistry(); reg.register(SemanticScholarSkill())
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources,
                                   cockpit2._Stores(dd).observations, _ctx(), today=datetime.date(2026, 7, 20))
    assert w == []
