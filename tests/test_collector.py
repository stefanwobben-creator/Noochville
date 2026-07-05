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
