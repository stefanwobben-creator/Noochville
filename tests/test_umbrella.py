"""Umbrella-verbreding voor niche keyword-research: 'biodegradable barefoot shoes' → 'barefoot shoes'.
De afleiding is fail-closed en geeft nooit de niche-term zelf terug; in _propose_related komt de umbrella
als eigen kandidaat de pipeline in (dedup tegen bibliotheek + bestaande labels)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village import umbrella
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





