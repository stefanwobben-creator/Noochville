"""Tests voor de emergentie-trigger (Fase 1 brokje 3). Thread-vrij, puur.

Legt vast: onder de drempel = nog niet bevestigd, op of boven = bevestigd,
de standaarddrempel is 3, een eigen drempel wordt gerespecteerd, en emerged()
filtert een lijst met behoud van volgorde.
"""
from __future__ import annotations

from nooch_village.insight import Insight
from nooch_village.emergence import EMERGENCE_THRESHOLD, is_emerged, emerged


def _kaart(kid: str, count: int) -> Insight:
    return Insight(id=kid, claim="c", source="test", grounding_count=count)


def test_standaarddrempel_is_drie():
    """De standaarddrempel ligt op 3; een wijziging hoort bewust te zijn."""
    assert EMERGENCE_THRESHOLD == 3


def test_onder_drempel_niet_bevestigd():
    assert is_emerged(_kaart("a", 1)) is False
    assert is_emerged(_kaart("b", 2)) is False


def test_op_drempel_bevestigd():
    """Precies op de drempel telt al als bevestigd (>=)."""
    assert is_emerged(_kaart("c", 3)) is True


def test_boven_drempel_bevestigd():
    assert is_emerged(_kaart("d", 7)) is True


def test_eigen_drempel_wordt_gerespecteerd():
    kaart = _kaart("e", 2)
    assert is_emerged(kaart, threshold=2) is True
    assert is_emerged(kaart, threshold=5) is False


def test_emerged_filtert_lijst_met_volgorde():
    """emerged() houdt alleen bevestigde kaartjes over, in dezelfde volgorde."""
    kaarten = [_kaart("a", 1), _kaart("b", 3), _kaart("c", 2), _kaart("d", 5)]
    resultaat = [n.id for n in emerged(kaarten)]
    assert resultaat == ["b", "d"]


def test_emerged_lege_lijst():
    assert emerged([]) == []
