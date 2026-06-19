"""Pure keyword-matrix generator. Geen dorps-machinerie, geen I/O, geen events, geen credits."""
from __future__ import annotations

MARKET_LANGUAGES: dict[str, list[str]] = {
    "nl": ["nl", "en"],
    "de": ["de", "en"],
    "gb": ["en"],
    "se": ["en", "sv"],
}

QUALIFIERS: dict[str, list[str]] = {
    "en": ["vegan", "sustainable", "plastic free", "leather free"],
    "nl": ["vegan", "duurzame", "plasticvrije", "leervrije"],
    "de": ["vegane", "nachhaltige", "plastikfreie", "lederfreie"],
    "sv": ["veganska", "hållbara"],
}

CATEGORIES: dict[str, list[str]] = {
    "en": ["shoes", "sneakers"],
    "nl": ["schoenen", "sneakers"],
    "de": ["schuhe", "sneaker"],
    "sv": ["skor", "sneakers"],
}

MODIFIERS: dict[str, list[str]] = {
    "en": ["women", "men"],
    "nl": ["dames", "heren"],
    "de": ["damen", "herren"],
    "sv": ["dam", "herr"],
}


def core_candidates(market: str) -> list[str]:
    """Kwalificator x categorie per taal van de markt. Dedup, gesorteerd.

    Elke kandidaat heeft minimaal 2 woorden. Alleen talen van de markt komen erin.
    Onbekende markt → ValueError.
    """
    if market not in MARKET_LANGUAGES:
        raise ValueError(f"Onbekende markt '{market}' — kies uit {sorted(MARKET_LANGUAGES)}")
    candidates: set[str] = set()
    for lang in MARKET_LANGUAGES[market]:
        for qual in QUALIFIERS[lang]:
            for cat in CATEGORIES[lang]:
                candidates.add(f"{qual} {cat}")
    return sorted(candidates)


def longtail_candidates(market: str) -> list[str]:
    """Kwalificator x categorie x modifier per taal van de markt. Dedup, gesorteerd.

    Modifier is taal-gematched aan de kwalificator en categorie (dezelfde taal).
    Elke kandidaat heeft minimaal 3 woorden. Onbekende markt → ValueError.
    """
    if market not in MARKET_LANGUAGES:
        raise ValueError(f"Onbekende markt '{market}' — kies uit {sorted(MARKET_LANGUAGES)}")
    candidates: set[str] = set()
    for lang in MARKET_LANGUAGES[market]:
        for qual in QUALIFIERS[lang]:
            for cat in CATEGORIES[lang]:
                for mod in MODIFIERS[lang]:
                    candidates.add(f"{qual} {cat} {mod}")
    return sorted(candidates)
