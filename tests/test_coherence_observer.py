"""Tests voor CoherenceObserver — B-pad observatie, puur loggend.

Vier invarianten:
  1. Logs "B-observer: coherent (...)" bij een coherent LLM-verdict.
  2. Logs "B-observer: vague (...)"    bij een vague LLM-verdict.
  3. Logs "B-observer: error (...)"    bij een LLM-exception.
  4. Publiceert geen extra events, muteert event.data niet (observer-only bewijs).
"""
from __future__ import annotations
from unittest.mock import patch, call

from nooch_village.event_bus import EventBus, Event
from nooch_village.observers.coherence_observer import CoherenceObserver


def _make_bus_and_observer():
    bus = EventBus(name="test")
    observer = CoherenceObserver(bus)
    return bus, observer


# ── 1. Coherent verdict ───────────────────────────────────────────────────────

def test_observer_logs_coherent_on_clear_gap():
    """LLM geeft 'coherent' → observer logt 'B-observer: coherent (...)'."""
    bus, observer = _make_bus_and_observer()

    with patch("nooch_village.llm.reason",
               return_value="VERDICT: coherent\nREASON: duidelijke afgebakende taak"):
        with patch.object(observer.log, "info") as mock_log:
            bus.publish(Event("means_gap_sensed", {
                "gap_key": "juridische_claims",
                "description": "juridische claims controleren en afhandelen",
            }, "test"))

    logged = " ".join(str(c) for c in mock_log.call_args_list)
    assert "B-observer:" in logged and "coherent" in logged


# ── 2. Vague verdict ──────────────────────────────────────────────────────────

def test_observer_logs_vague_on_keyword_cluster():
    """LLM geeft 'vague' → observer logt 'B-observer: vague (...)'."""
    bus, observer = _make_bus_and_observer()

    with patch("nooch_village.llm.reason",
               return_value="VERDICT: vague\nREASON: keyword-cluster zonder mandaat"):
        with patch.object(observer.log, "info") as mock_log:
            bus.publish(Event("means_gap_sensed", {
                "gap_key": "missie_transparantie",
                "description": "missie-alignment, transparantie, kernwaarden",
            }, "test"))

    logged = " ".join(str(c) for c in mock_log.call_args_list)
    assert "B-observer:" in logged and "vague" in logged


# ── 3. Exception → error ──────────────────────────────────────────────────────

def test_observer_logs_error_on_exception():
    """LLM gooit exception → observer logt 'B-observer: error (...)'."""
    bus, observer = _make_bus_and_observer()

    with patch("nooch_village.llm.reason",
               side_effect=RuntimeError("verbinding verbroken")):
        with patch.object(observer.log, "info") as mock_log:
            bus.publish(Event("means_gap_sensed", {
                "gap_key": "kapot_gat",
                "description": "iets wat de LLM niet haalt",
            }, "test"))

    logged = " ".join(str(c) for c in mock_log.call_args_list)
    assert "B-observer: error" in logged


# ── 4. Observer-only: geen extra events, geen mutatie ────────────────────────

def test_observer_does_not_block_or_mutate():
    """Observer publiceert geen extra events en muteert event.data niet.

    Dit is het kritieke bewijs dat de observer puur observerend is.
    """
    bus, observer = _make_bus_and_observer()

    # Luister op events die de observer ten onrechte zou kunnen publiceren
    unexpected = []
    for name in ("coherence_verdict", "proposal_raised", "tension_sensed",
                 "means_gap_updated", "governance_changed"):
        bus.subscribe(name, lambda e: unexpected.append(e))

    original_data = {
        "gap_key": "test_gap",
        "description": "missie-alignment keywords cluster",
    }
    data_snapshot = dict(original_data)

    with patch("nooch_village.llm.reason",
               return_value="VERDICT: vague\nREASON: keyword-cluster"):
        bus.publish(Event("means_gap_sensed", original_data, "test"))

    assert unexpected == [], (
        f"Observer publiceerde onverwachte events: {[e.name for e in unexpected]}"
    )
    assert original_data == data_snapshot, (
        "Observer heeft event.data gemuteerd"
    )
