"""Werktaal van het dorp: Engels is de default voor alle gegronde kennis en
LLM-output, tenzij expliciet een andere taal/locale gevraagd wordt.

Waarom (gevalideerd in simulatie, 2026-06-23): de verbind-laag (relevant_for)
matcht op letterlijke woorden. Eén consistente taal is voorwaarde voor een
werkende kennisgraaf; mengtaal isoleert kaartjes (een Nederlandse kind-kaart
hangt aan niets tussen Engelse zaad-kaarten). Engels is die ene taal.

Eén bron van waarheid: alle LLM-prompts die kaartjes voeden hangen `instruction()`
aan, zodat de output-taal centraal te sturen is.
"""
from __future__ import annotations

DEFAULT_LOCALE = "en"

_LANG_NAME = {
    "en": "English",
    "nl": "Dutch",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
}


def language_name(locale: str | None = None) -> str:
    """Naam van de doeltaal. Valt terug op de default (Engels) bij None, leeg of
    onbekend, zodat de werktaal alleen wijkt bij een expliciet bekende locale."""
    if not locale:
        return _LANG_NAME[DEFAULT_LOCALE]
    return _LANG_NAME.get(locale.lower(), _LANG_NAME[DEFAULT_LOCALE])


def instruction(locale: str | None = None) -> str:
    """Prompt-instructie voor de werktaal: standaard Engels, tenzij een locale
    expliciet een andere taal vraagt. Hang dit aan elke kaart-voedende prompt."""
    return f"Write your answer in {language_name(locale)}."
