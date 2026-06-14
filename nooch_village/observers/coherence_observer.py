"""B-observer: log hoe de LLM-coherentiepoort oordeelt over means_gap_sensed-items.

Puur observerend — geen blokkade, geen routing-wijziging, geen inbox-aanpassing.
Geeft de datagrondslag om later te beslissen of de poort blokkerend mag worden op B.
"""
from __future__ import annotations
import logging

from nooch_village.coherence import evaluate_coherence


class CoherenceObserver:
    """Parallelle subscriber op means_gap_sensed; logt het LLM-coherentievonnis.

    Losgekoppeld van _on_means_gap in village.py: geen gedeelde state,
    geen invloed op inbox of routing. Uitzetten = instantiatie weghalen.
    """

    def __init__(self, bus) -> None:
        self.log = logging.getLogger("coherence_observer")
        bus.subscribe("means_gap_sensed", self._on_means_gap)

    def _on_means_gap(self, event) -> None:
        description = event.data.get("description", "")
        gap_key     = event.data.get("gap_key", "?")
        verdict, reason_text = evaluate_coherence(description)
        if verdict in ("coherent", "vague"):
            self.log.info(
                "B-observer: %s (%s) — gap_key=%s", verdict, reason_text, gap_key)
        else:
            self.log.info(
                "B-observer: error (%s) — gap_key=%s", reason_text, gap_key)
