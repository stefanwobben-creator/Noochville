"""Plausible page_path-dimensie: drempel-entree (≥3 bezoeken/dag), persistente volledige dagreeks,
afwezig=0, backfill-meta, fail-closed. Additief naast country + totalen (collector-hook)."""
from __future__ import annotations
import datetime
import types

from nooch_village.observations import ObservationStore
from nooch_village.skills_impl.plausible import PlausibleSkill


def _ctx():
    return types.SimpleNamespace(settings={"PLAUSIBLE_API_KEY": "k", "PLAUSIBLE_SITE_ID": "s"})


def _breakdown(pages):
    return lambda params: [{"page": p, "visitors": v} for p, v in pages.items()]


def test_page_threshold_entry(tmp_path):
    """Een pagina komt in de meetset bij ≥3 op één dag; <3 (nog niet gekwalificeerd) niet."""
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    PlausibleSkill().collect_extra_series(_ctx(), datetime.date(2026, 7, 8), obs,
                                          _get=_breakdown({"/impact-forest": 5, "/about": 2, "/": 9}))
    metrics = {r["metric"] for r in obs._read_all()}
    assert metrics == {"plausible_page_visitors_day::impact_forest", "plausible_page_visitors_day::home"}
    assert "plausible_page_visitors_day::about" not in metrics       # 2 < 3 → geen entree
    assert all(r["datum"] == "2026-07-07" for r in obs._read_all())  # laatst-complete dag
    assert all(r["meta"]["dimension"] == "page_path" for r in obs._read_all())
    assert {r["meta"]["value"] for r in obs._read_all()} == {"/impact-forest", "/"}


def test_page_persistent_onder_drempel(tmp_path):
    """Een reeds gekwalificeerde pagina wordt doorgemeten, ook onder de drempel (volledige dagreeks)."""
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    sk = PlausibleSkill()
    sk.collect_extra_series(_ctx(), datetime.date(2026, 7, 8), obs, _get=_breakdown({"/impact-forest": 5}))
    sk.collect_extra_series(_ctx(), datetime.date(2026, 7, 9), obs, _get=_breakdown({"/impact-forest": 1, "/x": 1}))
    rows = [(r["datum"], r["value"]) for r in obs._read_all() if r["metric"] == "plausible_page_visitors_day::impact_forest"]
    assert sorted(rows) == [("2026-07-07", 5), ("2026-07-08", 1)]    # dag 2 (1<3) toch geschreven
    assert not any(r["metric"].endswith("::x") for r in obs._read_all())   # /x nooit gekwalificeerd


def test_page_afwezig_is_nul(tmp_path):
    """Gekwalificeerde pagina die een dag niet in de respons zit → 0 (echte waarde, geen gat)."""
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    sk = PlausibleSkill()
    sk.collect_extra_series(_ctx(), datetime.date(2026, 7, 8), obs, _get=_breakdown({"/impact-forest": 5}))
    sk.collect_extra_series(_ctx(), datetime.date(2026, 7, 9), obs, _get=_breakdown({"/other": 4}))  # impact-forest weg
    rows = {r["datum"]: r["value"] for r in obs._read_all() if r["metric"] == "plausible_page_visitors_day::impact_forest"}
    assert rows == {"2026-07-07": 5, "2026-07-08": 0}


def test_page_backfill_meta(tmp_path):
    """backfill_page_paths schrijft de dagreeks per pagina met meta backfill:true; 0 blijft 0 (geen interpolatie)."""
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    ts = lambda params: [{"date": "2026-06-01", "visitors": 4}, {"date": "2026-06-02", "visitors": 0},
                         {"date": "2026-06-03", "visitors": 7}]
    PlausibleSkill().backfill_page_paths(_ctx(), obs, "2026-06-01", "2026-06-03", ["/impact-forest"], _get=ts)
    rows = sorted((r["datum"], r["value"], r["meta"].get("backfill")) for r in obs._read_all())
    assert rows == [("2026-06-01", 4, True), ("2026-06-02", 0, True), ("2026-06-03", 7, True)]


def test_page_failclosed_geen_creds(tmp_path, monkeypatch):
    monkeypatch.delenv("PLAUSIBLE_API_KEY", raising=False)
    monkeypatch.delenv("PLAUSIBLE_SITE_ID", raising=False)
    obs = ObservationStore(str(tmp_path / "o.jsonl"))
    ctx = types.SimpleNamespace(settings={})
    assert PlausibleSkill().collect_extra_series(ctx, datetime.date(2026, 7, 8), obs, _get=_breakdown({"/a": 9})) == []
    assert obs._read_all() == []


def test_collector_roept_collect_extra_series_additief(tmp_path):
    """De collector draait collect_extra_series NAAST de totaal-/dimensie-paden (additieve hook)."""
    from nooch_village.collector import collect_daily_observations
    from nooch_village import cockpit2
    from nooch_village.skills import SkillRegistry, DataSourceSkill

    class _P(DataSourceSkill):
        name = "p"; SOURCE = "plausible"; required_env = ()
        def available_metrics(self, c=None): return ["visitors"]
        def is_configured(self, c): return True
        def daily_values(self, c, d): return {"visitors": 42}
        def run(self, p, c): return {}
        def collect_extra_series(self, c, today, obs):
            obs.record_daily("plausible", "plausible_page_visitors_day::home", 9, bron="plausible",
                             datum="2026-07-07", meta={"dimension": "page_path", "value": "/"})
            return [("plausible", "page_visitors::home", "2026-07-07")]
    dd = str(tmp_path / "poc"); cockpit2._bootstrap(dd)
    cockpit2._Stores(dd).sources.set_active("plausible", True)
    reg = SkillRegistry(); reg.register(_P())
    w = collect_daily_observations(reg, cockpit2._Stores(dd).sources, cockpit2._Stores(dd).observations,
                                   types.SimpleNamespace(settings={}), today=datetime.date(2026, 7, 8))
    assert ("plausible", "visitors", "2026-07-07") in w                       # totaal-pad draaide óók
    assert ("plausible", "page_visitors::home", "2026-07-07") in w            # + de extra-reeks
    assert "/" in cockpit2._Stores(dd).observations.dimensioned_series("plausible_page_visitors_day", bron="plausible")
