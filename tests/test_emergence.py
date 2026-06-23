"""Tests voor de emergentie-trigger (Fase 1 brokje 3). Thread-vrij, puur.

Legt vast: onder de drempel = nog niet bevestigd, op of boven = bevestigd,
de standaarddrempel is 3, een eigen drempel wordt gerespecteerd, en emerged()
filtert een lijst met behoud van volgorde.
"""
from __future__ import annotations

from nooch_village.insight import Insight
from nooch_village.emergence import (
    EMERGENCE_THRESHOLD, is_emerged, emerged, select_for_deepening,
)


def _kaart(kid: str, count: int, links: list[str] | None = None) -> Insight:
    return Insight(id=kid, claim="c", source="test", grounding_count=count,
                   links_to=links or [])


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


# ── brokje 7: budget- en diepte-rem (select_for_deepening) ────────────────────

def test_select_alleen_bevestigde_trends():
    """Onbevestigde kaartjes (onder de drempel) doen niet mee."""
    kaarten = [_kaart("vers", 1), _kaart("trend", 4)]
    gekozen = [n.id for n in select_for_deepening(kaarten, budget=5)]
    assert gekozen == ["trend"]


def test_select_budget_en_sterkste_eerst():
    """Meer bevestigde trends dan budget → alleen de sterkste, op volgorde van teller."""
    kaarten = [_kaart("a", 3), _kaart("b", 9), _kaart("c", 5)]
    gekozen = [n.id for n in select_for_deepening(kaarten, budget=2)]
    assert gekozen == ["b", "c"]   # 9 en 5, niet de 3


def test_select_slaat_kind_kaartjes_over():
    """Diepte één hop: een kind-kaartje (met uitgaande link) wordt niet verdiept.
    Het kind wijst naar een ánder kaartje ('x'), zodat de trend niet als al-verdiept telt."""
    kaarten = [_kaart("trend", 5), _kaart("kind", 5, links=["x"])]
    gekozen = [n.id for n in select_for_deepening(kaarten, budget=5)]
    assert gekozen == ["trend"]    # het kind doet niet mee, de trend wel


def test_select_slaat_al_verdiepte_trend_over():
    """Eén vraag per trend: een trend die al een kind heeft, wordt overgeslagen."""
    # 'kind' wijst naar 'trend' → trend heeft al een kind
    kaarten = [_kaart("trend", 8, ), _kaart("kind", 1, links=["trend"])]
    gekozen = [n.id for n in select_for_deepening(kaarten, budget=5)]
    assert gekozen == []           # trend al verdiept, kind onbevestigd


def test_select_budget_nul_of_negatief_is_leeg():
    kaarten = [_kaart("trend", 9)]
    assert select_for_deepening(kaarten, budget=0) == []
    assert select_for_deepening(kaarten, budget=-1) == []
