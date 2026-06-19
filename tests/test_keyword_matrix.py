"""Tests voor keyword_matrix — pure functies, geen I/O."""
from __future__ import annotations
import pytest
from nooch_village.keyword_matrix import core_candidates, longtail_candidates


def test_core_nl_bevat_nl_en_en_termen():
    result = core_candidates("nl")
    assert "vegan schoenen" in result
    assert "sustainable shoes" in result
    assert "vegane schuhe" not in result


def test_core_gb_uitsluitend_engels():
    result = core_candidates("gb")
    # Alleen woorden die exclusief niet-Engels zijn (sneakers/vegan zijn ook Engels)
    NON_EN = {
        "schoenen", "schuhe", "sneaker", "skor",
        "duurzame", "plasticvrije", "leervrije",
        "vegane", "nachhaltige", "plastikfreie", "lederfreie",
        "veganska", "hållbara",
        "dames", "heren", "damen", "herren", "dam", "herr",
    }
    for term in result:
        words = set(term.split())
        assert not (words & NON_EN), f"Niet-Engelse term gevonden in gb: '{term}'"


def test_elke_kandidaat_minimaal_twee_woorden():
    for market in ("nl", "de", "gb", "se", "fr", "es", "it"):
        for term in core_candidates(market):
            assert len(term.split()) >= 2, f"core '{term}' heeft minder dan 2 woorden ({market})"
        for term in longtail_candidates(market):
            assert len(term.split()) >= 2, f"longtail '{term}' heeft minder dan 2 woorden ({market})"


def test_longtail_de_bevat_duitse_modifier_niet_engelse_op_duitse_term():
    result = longtail_candidates("de")
    assert "vegane schuhe damen" in result
    # Engels modifier op een Duitse term mag niet voorkomen
    assert "vegane schuhe women" not in result
    assert "vegane schuhe men" not in result


def test_onbekende_markt_raises_valueerror():
    with pytest.raises(ValueError, match="Onbekende markt"):
        core_candidates("xx")
    with pytest.raises(ValueError, match="Onbekende markt"):
        longtail_candidates("xx")


def test_output_gesorteerd_en_zonder_duplicaten():
    for market in ("nl", "de", "gb", "se", "fr", "es", "it"):
        core = core_candidates(market)
        assert core == sorted(set(core)), f"core({market}) is niet gesorteerd of bevat duplicaten"
        longtail = longtail_candidates(market)
        assert longtail == sorted(set(longtail)), f"longtail({market}) is niet gesorteerd of bevat duplicaten"


def test_romaanse_woordvolgorde_fr():
    core = core_candidates("fr")
    assert "chaussures vegan" in core, "FR core: verwacht 'chaussures vegan' (naamwoord eerst)"
    assert "vegan chaussures" not in core, "FR core: 'vegan chaussures' mag niet voorkomen"


def test_romaanse_woordvolgorde_es():
    assert "zapatillas veganas" in core_candidates("es")


def test_romaanse_woordvolgorde_it():
    assert "scarpe vegane" in core_candidates("it")


def test_longtail_fr_woordvolgorde():
    longtail = longtail_candidates("fr")
    assert "chaussures vegan femme" in longtail, "FR longtail: verwacht 'chaussures vegan femme'"
