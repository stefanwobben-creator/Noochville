"""Tests voor de werktaal van het dorp (Engels default). Thread-vrij, puur."""
from __future__ import annotations

from nooch_village.language import instruction, language_name, DEFAULT_LOCALE


def test_default_is_engels():
    assert language_name() == "English"
    assert language_name(None) == "English"
    assert language_name("") == "English"
    assert instruction() == "Write your answer in English."


def test_expliciete_locale_andere_taal():
    assert language_name("nl") == "Dutch"
    assert instruction("nl") == "Write your answer in Dutch."
    assert instruction("DE") == "Write your answer in German."  # hoofdletter-ongevoelig


def test_onbekende_locale_valt_terug_op_engels():
    assert language_name("xx") == "English"
    assert instruction("xx") == "Write your answer in English."


def test_default_locale_constant():
    assert DEFAULT_LOCALE == "en"
