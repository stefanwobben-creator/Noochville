"""Umbrella-verbreding voor niche keyword-research: 'biodegradable barefoot shoes' → 'barefoot shoes'.
De afleiding is fail-closed en geeft nooit de niche-term zelf terug; in _propose_related komt de umbrella
als eigen kandidaat de pipeline in (dedup tegen bibliotheek + bestaande labels)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village import umbrella
from nooch_village.roles import WebsiteWatcherWorker
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger
from nooch_village.library import Library


# ── umbrella_terms (puur, reason_fn geïnjecteerd) ──────────────────────────────

def test_umbrella_terms_map_en_dedup_zelf():
    kws = ["biodegradable barefoot shoes", "barefoot shoes"]
    out = umbrella.umbrella_terms(
        kws, reason_fn=lambda p: '{"umbrellas": ["barefoot shoes", "barefoot shoes"]}')
    # niche-term krijgt de umbrella; de basisterm (umbrella == zichzelf) valt weg
    assert out == {"biodegradable barefoot shoes": "barefoot shoes"}


def test_umbrella_terms_null_en_lege_input():
    assert umbrella.umbrella_terms(["x"], reason_fn=lambda p: '{"umbrellas": [null]}') == {}
    assert umbrella.umbrella_terms([], reason_fn=lambda p: "{}") == {}


def test_umbrella_terms_faalt_closed_bij_onparsbaar():
    assert umbrella.umbrella_terms(["x"], reason_fn=lambda p: "geen json") == {}
    assert umbrella.umbrella_terms(["x"], reason_fn=lambda p: None) == {}


# ── _propose_related voegt de umbrella als kandidaat toe ────────────────────────

def _make_watcher(tmp_path):
    bus = EventBus(name="test")
    context = SimpleNamespace(settings={"reflect_interval_seconds": "0", "keyword_umbrella": "1"},
                              data_dir=str(tmp_path), projects=ProjectLedger(str(tmp_path / "p.json")),
                              records=None, observations=None, strategy=None,
                              library=Library(str(tmp_path / "library.json")))
    record = Record(id="website_watcher", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(purpose="groei", accountabilities=[], domains=[], skills=[]),
                    source="seed")
    return WebsiteWatcherWorker(record, bus, SkillRegistry(), context), bus


def test_propose_related_neemt_umbrella_mee(tmp_path):
    watcher, bus = _make_watcher(tmp_path)
    voorgesteld = []
    bus.subscribe("keyword_proposed", lambda e: voorgesteld.append(e.data.get("word")))

    trends = {"geo": "", "keywords": {"shoes": {
        "top_related": [{"query": "vegan trail running shoes", "value": 8}]}}}

    # umbrella gestubd + prioritize als passthrough (niets valt af), zodat we de propose-stap toetsen
    def passthrough(cands, ctx):
        return [{**c, "dropped": False} for c in cands]

    with patch("nooch_village.umbrella.umbrella_terms",
               lambda kws, **k: {"vegan trail running shoes": "trail running shoes"}), \
         patch("nooch_village.intent.prioritize", passthrough):
        watcher._propose_related(trends)

    assert "vegan trail running shoes" in voorgesteld          # de niche-term
    assert "trail running shoes" in voorgesteld                # én de umbrella erbij


def test_propose_related_umbrella_uit_via_config(tmp_path):
    watcher, bus = _make_watcher(tmp_path)
    watcher.context.settings["keyword_umbrella"] = "0"          # schakelaar uit
    voorgesteld = []
    bus.subscribe("keyword_proposed", lambda e: voorgesteld.append(e.data.get("word")))
    trends = {"geo": "", "keywords": {"shoes": {"top_related": [{"query": "vegan trail running shoes", "value": 8}]}}}

    called = {"n": 0}

    def passthrough(cands, ctx):
        return [{**c, "dropped": False} for c in cands]

    with patch("nooch_village.umbrella.umbrella_terms",
               lambda kws, **k: called.__setitem__("n", called["n"] + 1) or {}), \
         patch("nooch_village.intent.prioritize", passthrough):
        watcher._propose_related(trends)

    assert called["n"] == 0                                     # uit → geen umbrella-call
    assert "trail running shoes" not in voorgesteld
