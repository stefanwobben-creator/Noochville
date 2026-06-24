"""Fundament: grounding-kaartjes vallen onder hetzelfde contract als de curator.

Elk grounding-kaartje draagt expliciete grounds (bewijs) en haalt curate.validate_card.
Geen bronnen → eerlijke 'niets gevonden'-grounds (nog steeds geldig). De woord-id en
emergentie-mechaniek blijven ongemoeid. Geen netwerk."""
from __future__ import annotations

from nooch_village.insight_ingest import insight_from_grounding, _slug
from nooch_village.curate import validate_card


def test_grounding_met_bronnen_heeft_grounds_en_haalt_contract():
    ev = [{"title": "A study on hemp fibre", "year": 2021, "source": "openalex"}]
    card = insight_from_grounding("hemp", "Hemp is relevant to sustainable materials.", ev)
    assert card is not None
    assert card.grounds and "Grounded in:" in card.grounds
    assert "A study on hemp fibre" in card.grounds
    # haalt dezelfde contract-poort als de curator
    assert validate_card({"id": card.id, "claim": card.claim, "grounds": card.grounds})


def test_grounding_zonder_bronnen_heeft_eerlijke_grounds():
    card = insight_from_grounding("noighwotch", "Term not grounded in literature.", [])
    assert card is not None
    assert "No academic sources found" in card.grounds
    assert validate_card({"id": card.id, "claim": card.claim, "grounds": card.grounds})


def test_lege_assessment_geeft_geen_kaartje():
    assert insight_from_grounding("x", "   ", []) is None
    assert insight_from_grounding("x", "", []) is None


def test_woord_id_blijft_deterministisch_voor_emergentie():
    """De woord-id mag NIET veranderen: emergentie leunt op enrich-bij-duplicaat."""
    a = insight_from_grounding("vegan", "Assessment one.", [])
    b = insight_from_grounding("vegan", "Assessment two (later).", [])
    assert a.id == b.id == _slug("vegan")     # zelfde woord → zelfde kaartje-id
