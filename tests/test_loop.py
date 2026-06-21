"""Loop-integratietest: discovery-keten zonder netwerk-latency.

Runt analyst + Noochie op echte threads met gemockte skills.
Verifieert de volledige keten:
  queued → (analyst) running → blocked(noochie) → (Noochie adviseert)
  → blocked(analyst) → (analyst verwerkt advies) → done.
"""
from __future__ import annotations
import time
import pytest
import pandas as pd
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from nooch_village.roles import WebsiteWatcherWorker, Noochie
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill, _normalize_rising_value
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.projects import ProjectLedger
from nooch_village.monitoring import MonitoringStore

_FAKE_PLAUSIBLE = {"results": {"visitors": {"value": 42}, "pageviews": {"value": 88}}}
_FAKE_TRENDS    = {"keywords": {}, "related": []}
_FAKE_NOTE      = {"path": None, "tension": False, "reason": ""}
_TIMEOUT        = 20  # seconden max


def _record(role_id, skills=None):
    return Record(
        id=role_id,
        type=RecordType.ROLE,
        parent="noochville",
        definition=RoleDefinition(
            purpose="test",
            accountabilities=[],
            domains=[],
            skills=skills or [],
        ),
        source="seed",
    )


@pytest.fixture()
def loop_setup(tmp_path):
    bus      = EventBus(name="loop-test")
    registry = SkillRegistry()
    for skill in (PlausibleSkill(), TrendsSkill(), FieldNoteSkill()):
        registry.register(skill)

    ledger     = ProjectLedger(str(tmp_path / "projects.json"))
    monitoring = MonitoringStore(str(tmp_path / "role_metrics.json"))

    context = SimpleNamespace(
        settings={"reflect_interval_seconds": "0"},
        data_dir=str(tmp_path),
        projects=ledger,
        records=None,
        observations=None,
        monitoring=monitoring,
        library=None,
        strategy={},
    )

    analyst = WebsiteWatcherWorker(
        _record("website_watcher", ["plausible_stats", "google_trends", "field_note"]),
        bus, registry, context,
    )
    noochie = Noochie(
        _record("noochie"),
        bus, registry, context,
    )

    return SimpleNamespace(
        bus=bus, ledger=ledger, monitoring=monitoring,
        analyst=analyst, noochie=noochie,
    )


def test_discovery_loop(loop_setup):
    s = loop_setup

    with (
        patch.object(PlausibleSkill, "run", return_value=_FAKE_PLAUSIBLE),
        patch.object(TrendsSkill,    "run", return_value=_FAKE_TRENDS),
        patch.object(FieldNoteSkill, "run", return_value=_FAKE_NOTE),
        patch("nooch_village.llm.reason", return_value=None),
    ):
        s.analyst.start()
        s.noochie.start()
        try:
            pid = s.ledger.create(
                "website_watcher",
                {"kind": "discovery", "skill": "plausible_stats"},
                "human",
            )
            s.bus.publish(Event("dag_begint", {"label": "test"}, "test"))

            deadline = time.time() + _TIMEOUT
            while time.time() < deadline:
                p = s.ledger.get(pid)
                if p and p["status"] == "done":
                    break
                time.sleep(0.05)
        finally:
            s.analyst.stop()
            s.noochie.stop()
            s.analyst.join(timeout=5)
            s.noochie.join(timeout=5)

    p = s.ledger.get(pid)
    assert p is not None
    assert p["status"] == "done", f"Verwacht 'done', got '{p['status']}'"
    assert p["outcome"] and "monitoring" in p["outcome"]

    metrics = s.monitoring.get_metrics("website_watcher")
    assert len(metrics) > 0, "Geen metrics in monitoring na discovery"
    assert any(m in metrics for m in ("visitors", "pageviews"))


# ── Tests voor rising_related parsing ─────────────────────────────────────────

def test_normalize_rising_value_breakout():
    val, is_breakout = _normalize_rising_value("Breakout")
    assert val == 10000
    assert is_breakout is True


def test_normalize_rising_value_integer():
    val, is_breakout = _normalize_rising_value(350)
    assert val == 350
    assert is_breakout is False


def test_normalize_rising_value_ongeldige_waarde():
    val, is_breakout = _normalize_rising_value(None)
    assert val == 0
    assert is_breakout is False


def test_trends_rising_related_structuur(tmp_path):
    """TrendsSkill.run() met gemockte pytrends: rising_related verwerkt Breakout
    en integer correct; term zonder rising levert lege lijst, geen crash."""
    rising_term1 = pd.DataFrame([
        {"query": "vegan laarzen",    "value": "Breakout"},
        {"query": "plantaardig leer", "value": 320},
    ])
    top_term1 = pd.DataFrame([{"query": "vegan schoenen nl", "value": 100}])

    rising_term2 = None
    top_term2    = pd.DataFrame([{"query": "duurzame skor",   "value": 80}])

    def fake_related_queries():
        return {
            "vegan schoenen": {
                "top":    top_term1,
                "rising": rising_term1,
            },
            "duurzame sneakers": {
                "top":    top_term2,
                "rising": rising_term2,
            },
        }

    fake_interest = pd.DataFrame(
        {"vegan schoenen": [50, 60], "duurzame sneakers": [40, 45]},
        index=pd.date_range("2025-01-01", periods=2, freq="W"),
    )

    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = fake_interest
    mock_pytrends.related_queries.side_effect = fake_related_queries

    import nooch_village.config as cfg
    from nooch_village.library import Library

    ctx = SimpleNamespace(
        settings={"trends_geo": "NL"},
        data_dir=str(tmp_path),
        library=Library(str(tmp_path / "library.json")),
        lexicon=None,
    )

    with patch("pytrends.request.TrendReq", return_value=mock_pytrends):
        result = TrendsSkill().run(
            {"keywords": ["vegan schoenen", "duurzame sneakers"]}, ctx
        )

    kw = result["keywords"]

    # term 1: rising met Breakout én integer
    r1 = kw["vegan schoenen"]["rising_related"]
    assert len(r1) == 2
    breakout_row = next(r for r in r1 if r["query"] == "vegan laarzen")
    assert breakout_row["value"] == 10000
    assert breakout_row["breakout"] is True
    normal_row = next(r for r in r1 if r["query"] == "plantaardig leer")
    assert normal_row["value"] == 320
    assert normal_row["breakout"] is False

    # term 2: rising is None → lege lijst, geen crash
    r2 = kw["duurzame sneakers"]["rising_related"]
    assert r2 == []


def test_trends_timeframe_en_hl_doorgegeven(tmp_path):
    """Payload-velden timeframe en hl worden doorgegeven aan respectievelijk
    build_payload en TrendReq — geen harde defaults meer in de aanroep."""
    fake_interest = pd.DataFrame(
        {"vegan schoenen": [50, 60]},
        index=pd.date_range("2025-01-01", periods=2, freq="W"),
    )
    mock_pytrends = MagicMock()
    mock_pytrends.interest_over_time.return_value = fake_interest
    mock_pytrends.related_queries.return_value = {}

    ctx = SimpleNamespace(
        settings={"trends_geo": "NL"},
        data_dir=str(tmp_path),
        library=None,
        lexicon=None,
    )

    mock_trendreq_cls = MagicMock(return_value=mock_pytrends)

    with patch("pytrends.request.TrendReq", mock_trendreq_cls):
        TrendsSkill().run(
            {
                "keywords": ["vegan schoenen"],
                "timeframe": "today 3-m",
                "hl": "en-US",
            },
            ctx,
        )

    # TrendReq moet aangeroepen zijn met hl="en-US"
    mock_trendreq_cls.assert_called_once()
    _, kwargs = mock_trendreq_cls.call_args
    assert kwargs.get("hl") == "en-US", f"verwacht hl='en-US', got {kwargs}"

    # build_payload moet aangeroepen zijn met timeframe="today 3-m"
    mock_pytrends.build_payload.assert_called_once()
    _, bp_kwargs = mock_pytrends.build_payload.call_args
    assert bp_kwargs.get("timeframe") == "today 3-m", (
        f"verwacht timeframe='today 3-m', got {bp_kwargs}"
    )
