"""Tests voor find_forbidden_words."""
from __future__ import annotations
from nooch_village.publication_check import find_forbidden_words, FORBIDDEN_IN_SALES


def test_plastic_in_text():
    assert find_forbidden_words("Onze plastic zool", FORBIDDEN_IN_SALES) == ["plastic"]


def test_plasticvrij_is_not_a_hit():
    assert find_forbidden_words("Een volledig plasticvrij ontwerp", FORBIDDEN_IN_SALES) == []


def test_leervrije_is_not_a_hit():
    assert find_forbidden_words("leervrije bovenkant", FORBIDDEN_IN_SALES) == []


def test_case_insensitive_both_words():
    assert find_forbidden_words("PLASTIC en Leer naast elkaar", FORBIDDEN_IN_SALES) == ["plastic", "leer"]


def test_clean_text_gives_empty():
    assert find_forbidden_words("Gemaakt van acht planten", FORBIDDEN_IN_SALES) == []
