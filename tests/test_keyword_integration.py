"""Tests voor keyword_integration — pure uitvoeringskern. Geen netwerk, geen echte credits."""
from __future__ import annotations
import pytest
from nooch_village.keyword_batch import propose_batch
from nooch_village.keyword_integration import run_approved_keyword_batch


# ── Test-helpers ──────────────────────────────────────────────────────────────

class _FakeRunner:
    """Nep-runner: retourneert vooraf ingestelde rows, telt aanroepen."""
    def __init__(self, rows: list[dict]):
        self.call_count = 0
        self._rows = rows

    def __call__(self, candidates, country, data_source):
        self.call_count += 1
        return self._rows


class _FakeBus:
    """Nep-bus: vang gepubliceerde events op."""
    def __init__(self):
        self.events: list = []

    def publish(self, event):
        self.events.append(event)

    def keyword_proposed_words(self) -> list[str]:
        return [
            e.data["word"] for e in self.events
            if e.name == "keyword_proposed"
        ]


class _FakeLibrary:
    """Nep-bibliotheek: bekende woorden blokkeren publicatie (dedup)."""
    def __init__(self, known: set[str] | None = None):
        self._known: set[str] = known or set()

    def status(self, word: str):
        return {"status": "approved"} if word in self._known else None


def _batch(market: str = "nl", tier: str = "core") -> dict:
    return propose_batch(market, tier=tier)


def _run(batch, rows, *, min_volume=100, known=None, from_id="test"):
    """Draai run_approved_keyword_batch met nep-objecten."""
    runner  = _FakeRunner(rows)
    bus     = _FakeBus()
    library = _FakeLibrary(known or set())
    summary = run_approved_keyword_batch(
        batch, runner, bus, library,
        from_id=from_id, min_volume=min_volume, approved_by="test-user",
    )
    return summary, runner, bus


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_alleen_termen_boven_min_volume_worden_gepubliceerd():
    batch = _batch()
    rows = [
        {"keyword": "vegan schoenen",   "vol": 3400, "cpc": 0.5,  "competition": 0.7},
        {"keyword": "duurzame schoenen","vol":   50, "cpc": 0.3,  "competition": 0.5},
        {"keyword": "plasticvrije skor","vol":    0, "cpc": 0.0,  "competition": 0.0},
    ]
    summary, _, bus = _run(batch, rows, min_volume=100)
    assert "vegan schoenen" in summary["published"]
    assert "duurzame schoenen" not in summary["published"]
    assert "plasticvrije skor" not in summary["published"]
    assert summary["published"] == bus.keyword_proposed_words()


def test_gepubliceerde_demand_bevat_seo_data_en_consument_velden():
    """demand.locale en demand.signal worden correct doorgegeven aan de Librarian."""
    batch = _batch("fr")
    rows  = [{"keyword": "chaussures vegan", "vol": 10000, "cpc": 0.19, "competition": 0.62}]
    _, _, bus = _run(batch, rows, min_volume=100)

    assert len(bus.events) == 1
    demand = bus.events[0].data["demand"]

    # Consument-vereiste velden
    assert demand["locale"] == "fr"
    assert demand["signal"] == "positive"    # conventie van alle callers
    assert demand["source"] == "keywords_everywhere"

    # SEO-data
    assert demand["volume"]      == 10000
    assert demand["cpc"]         == 0.19
    assert demand["competition"] == 0.62
    assert demand["market"]      == "fr"


def test_credits_spent_gelijk_aan_measure_batch_uitkomst():
    batch = _batch("gb")
    rows  = [{"keyword": "vegan shoes", "vol": 22200, "cpc": 0.21, "competition": 1.0}]
    summary, _, _ = _run(batch, rows, min_volume=1)
    assert summary["credits_spent"] == batch["estimated_credits"]


def test_dedup_bekende_term_niet_opnieuw_gepubliceerd():
    batch = _batch()
    rows = [
        {"keyword": "vegan schoenen",    "vol": 3400, "cpc": 0.5, "competition": 0.7},
        {"keyword": "duurzame schoenen", "vol":  800, "cpc": 0.3, "competition": 0.5},
    ]
    # "vegan schoenen" is al bekend in de bibliotheek
    summary, _, bus = _run(batch, rows, min_volume=100, known={"vegan schoenen"})
    assert "vegan schoenen"    not in summary["published"]
    assert "vegan schoenen"    in  summary["skipped_dedup"]
    assert "duurzame schoenen" in  summary["published"]
    assert bus.keyword_proposed_words() == ["duurzame schoenen"]


def test_summary_tellingen_kloppen():
    batch = _batch()
    rows = [
        {"keyword": "vegan schoenen",    "vol": 3400, "cpc": 0.5, "competition": 0.7},
        {"keyword": "duurzame schoenen", "vol":  800, "cpc": 0.3, "competition": 0.5},
        {"keyword": "leervrije skor",    "vol":    0, "cpc": 0.0, "competition": 0.0},
    ]
    summary, _, _ = _run(batch, rows, min_volume=100)
    assert summary["measured"] == 3   # alle rows terug van de runner
    assert summary["live"]     == 2   # twee boven min_volume
    assert len(summary["published"]) == 2
    assert summary["errors"] == []


def test_misvormde_batch_raist_geen_partiële_spend_of_publicatie():
    """estimated_credits < len(candidates) → measure_batch raist ValueError.

    Runner mag niet aangeroepen zijn; niets gepubliceerd; geen partiële spend.
    """
    batch = _batch()
    echte_tel = len(batch["candidates"])
    assert echte_tel >= 2
    batch["estimated_credits"] = echte_tel - 1   # lager dan werkelijk

    rows   = [{"keyword": "vegan schoenen", "vol": 9999, "cpc": 1.0, "competition": 0.9}]
    runner = _FakeRunner(rows)
    bus    = _FakeBus()
    lib    = _FakeLibrary()

    with pytest.raises(ValueError, match="creditplafond"):
        run_approved_keyword_batch(
            batch, runner, bus, lib,
            from_id="test", min_volume=1, approved_by="test-user",
        )

    assert runner.call_count == 0, "runner mag niet aangeroepen zijn bij gate-fout"
    assert bus.events == [],        "niets mag gepubliceerd zijn bij gate-fout"
