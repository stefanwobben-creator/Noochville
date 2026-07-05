"""Dode-bron-sensor: senst op de OVERGANG fresh→stale (indicator_freshness), niet op de toestand.
Dedup via de vorige-status per indicator; opleving→herdood senst opnieuw; unconfigured/none nooit;
kind-aware drempel gerespecteerd; de spanning landt generiek in de human_inbox."""
from __future__ import annotations
import datetime
import os
import types

from nooch_village.observations import ObservationStore
from nooch_village.source_status import SourceStatusStore
from nooch_village.skills import DataSourceSkill, SkillRegistry
from nooch_village.deadsource import DeadSourceState, sense_dead_sources


class _Src(DataSourceSkill):
    def __init__(self, source): self._src = source
    @property
    def SOURCE(self): return self._src
    name = "s"; required_env = ()
    def run(self, p, c): return {}
    def available_metrics(self, context=None): return ["clicks"]
    def is_configured(self, c): return True
    def daily_values(self, c, datum): return {}


def _setup(tmp_path, source="gsc"):
    dd = str(tmp_path)
    obs = ObservationStore(os.path.join(dd, "o.jsonl"))
    srcs = SourceStatusStore(os.path.join(dd, "s.json")); srcs.set_active(source, True)
    ctx = types.SimpleNamespace(observations=obs, sources=srcs, data_dir=dd)
    reg = SkillRegistry(); reg.register(_Src(source))
    return dd, obs, srcs, ctx, reg


def _run(dd, reg, ctx, today, emitted):
    st = DeadSourceState(os.path.join(dd, "dead.json"))
    return sense_dead_sources(reg, ctx, st, lambda *a: emitted.append(a[:2]), today=today)


def test_overgang_senst_eenmaal_en_dedupt(tmp_path):
    dd, obs, _, ctx, reg = _setup(tmp_path)
    D = datetime.date(2026, 7, 1)
    obs.record_daily("g", "gsc_clicks_day", 5, bron="gsc", datum=D.isoformat())      # flux → drempel 7
    em = []
    _run(dd, reg, ctx, D + datetime.timedelta(days=2), em);  assert em == []          # fresh → prev=fresh
    _run(dd, reg, ctx, D + datetime.timedelta(days=10), em); assert em == [("gsc", "clicks")]   # SENSE
    em.clear()
    _run(dd, reg, ctx, D + datetime.timedelta(days=11), em); assert em == []          # stale→stale = dedup


def test_pre_existing_stale_senst_niet(tmp_path):
    """Een bron die al dood is bij de eerste puls (geen vorige 'fresh') senst niet — geen tension-storm."""
    dd, obs, _, ctx, reg = _setup(tmp_path)
    obs.record_daily("g", "gsc_clicks_day", 5, bron="gsc", datum="2026-07-01")
    em = []
    _run(dd, reg, ctx, datetime.date(2026, 7, 20), em)                                # meteen stale
    assert em == []


def test_opleving_dan_herdood_senst_opnieuw(tmp_path):
    dd, obs, _, ctx, reg = _setup(tmp_path)
    D = datetime.date(2026, 7, 1)
    obs.record_daily("g", "gsc_clicks_day", 5, bron="gsc", datum=D.isoformat())
    em = []
    _run(dd, reg, ctx, D + datetime.timedelta(days=2), em)                            # fresh
    _run(dd, reg, ctx, D + datetime.timedelta(days=10), em); em.clear()               # SENSE (1e dood)
    D2 = D + datetime.timedelta(days=11)
    obs.record_daily("g", "gsc_clicks_day", 7, bron="gsc", datum=D2.isoformat())      # opleving
    _run(dd, reg, ctx, D2 + datetime.timedelta(days=1), em); assert em == []          # fresh → geen sense
    _run(dd, reg, ctx, D2 + datetime.timedelta(days=10), em)                          # opnieuw dood
    assert em == [("gsc", "clicks")]                                                  # SENSE opnieuw


def test_trage_bron_binnen_kind_aware_drempel_senst_niet(tmp_path):
    """Een gezonde weekly-bron (drempel 10d) is bij 8 dagen nog 'fresh' — geen valse spanning, terwijl
    een flux-bron (7d) daar al dood zou zijn."""
    dd, obs, _, ctx, reg = _setup(tmp_path, source="openalex")                        # weekly → drempel 10
    D = datetime.date(2026, 7, 1)
    obs.record_daily("o", "openalex_clicks_day", 5, bron="openalex", datum=D.isoformat())
    em = []
    _run(dd, reg, ctx, D + datetime.timedelta(days=8), em)                            # age 8 ≤ 10 → fresh
    _run(dd, reg, ctx, D + datetime.timedelta(days=8), em)                            # fresh→fresh
    assert em == []


def test_unconfigured_en_none_sensen_nooit(tmp_path):
    dd, obs, srcs, ctx, reg = _setup(tmp_path)
    D = datetime.date(2026, 7, 1)
    obs.record_daily("g", "gsc_clicks_day", 5, bron="gsc", datum=D.isoformat())
    st = DeadSourceState(os.path.join(dd, "dead.json")); st.set("gsc:clicks", "fresh"); st.save()
    em = []
    # unconfigured (actief + geen creds) → indicator_freshness = 'unconfigured' → geen sense
    srcs.set_configured("gsc", False)
    sense_dead_sources(reg, ctx, DeadSourceState(os.path.join(dd, "dead.json")),
                       lambda *a: em.append(a[:2]), today=D + datetime.timedelta(days=10))
    assert em == []
    # none (geen reeks) → geen sense
    dd2, obs2, srcs2, ctx2, reg2 = _setup(tmp_path.joinpath("b") if hasattr(tmp_path, "joinpath") else tmp_path)
    st2 = DeadSourceState(os.path.join(dd2, "dead.json")); st2.set("gsc:clicks", "fresh"); st2.save()
    sense_dead_sources(reg2, ctx2, DeadSourceState(os.path.join(dd2, "dead.json")),
                       lambda *a: em.append(a[:2]), today=D + datetime.timedelta(days=10))
    assert em == []


def test_village_handler_schrijft_generieke_means_gap(tmp_path):
    """De source_died-handler schrijft generiek (role_id=None) een means-gap met per-episode gap_key en
    context (laatste-datum + cadans)."""
    from nooch_village.village import Village
    from nooch_village.human_inbox import HumanInbox
    from nooch_village.event_bus import Event
    inbox = HumanInbox(str(tmp_path / "inbox.json"))
    fake = types.SimpleNamespace(human_inbox=inbox)
    Village._on_source_died(fake, Event("source_died", {
        "source": "plausible", "field": "visitors", "last_datum": "2026-07-04",
        "days_ago": 9, "cadans": "dagelijks", "by": "website_watcher"}, "website_watcher"))
    items = [it for it in inbox._items.values() if it["type"] == "means_gap"]
    assert len(items) == 1
    it = items[0]
    assert it["subject"] == "deadsource:plausible:visitors@2026-07-04"                # per-episode key
    assert it["context"]["role_id"] is None                                           # generiek
    assert "9 dagen geleden" in it["context"]["description"] and "dagelijks" in it["context"]["description"]
