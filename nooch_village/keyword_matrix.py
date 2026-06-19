"""Pure keyword-matrix generator. Geen dorps-machinerie, geen I/O, geen events, geen credits."""
from __future__ import annotations

MARKET_LANGUAGES: dict[str, list[str]] = {
    "nl": ["nl", "en"],
    "de": ["de", "en"],
    "gb": ["en"],
    "se": ["en", "sv"],
    "fr": ["fr"],
    "es": ["es"],
    "it": ["it"],
}

QUALIFIERS: dict[str, list[str]] = {
    "en": ["vegan", "sustainable", "plastic free", "leather free"],
    "nl": ["vegan", "duurzame", "plasticvrije", "leervrije"],
    "de": ["vegane", "nachhaltige", "plastikfreie", "lederfreie"],
    "sv": ["veganska", "hållbara"],
    "fr": ["vegan", "écologiques", "sans plastique", "sans cuir"],
    "es": ["veganas", "sostenibles", "sin plástico", "sin cuero"],
    "it": ["vegane", "sostenibili", "senza plastica", "senza pelle"],
}

CATEGORIES: dict[str, list[str]] = {
    "en": ["shoes", "sneakers"],
    "nl": ["schoenen", "sneakers"],
    "de": ["schuhe", "sneaker"],
    "sv": ["skor", "sneakers"],
    "fr": ["chaussures", "baskets"],
    "es": ["zapatos", "zapatillas"],
    "it": ["scarpe", "sneakers"],
}

MODIFIERS: dict[str, list[str]] = {
    "en": ["women", "men"],
    "nl": ["dames", "heren"],
    "de": ["damen", "herren"],
    "sv": ["dam", "herr"],
    "fr": ["femme", "homme"],
    "es": ["mujer", "hombre"],
    "it": ["donna", "uomo"],
}

# Talen waarbij het bijvoeglijk naamwoord NA het zelfstandig naamwoord staat.
ADJECTIVE_AFTER_NOUN: set[str] = {"fr", "es", "it"}


def core_candidates(market: str) -> list[str]:
    """Kwalificator x categorie per taal van de markt. Dedup, gesorteerd.

    Elke kandidaat heeft minimaal 2 woorden. Alleen talen van de markt komen erin.
    Romaanse talen (ADJECTIVE_AFTER_NOUN) gebruiken naamwoord-eerst volgorde.
    Onbekende markt → ValueError.
    """
    if market not in MARKET_LANGUAGES:
        raise ValueError(f"Onbekende markt '{market}' — kies uit {sorted(MARKET_LANGUAGES)}")
    candidates: set[str] = set()
    for lang in MARKET_LANGUAGES[market]:
        for qual in QUALIFIERS[lang]:
            for cat in CATEGORIES[lang]:
                if lang in ADJECTIVE_AFTER_NOUN:
                    candidates.add(f"{cat} {qual}")
                else:
                    candidates.add(f"{qual} {cat}")
    return sorted(candidates)


def longtail_candidates(market: str) -> list[str]:
    """Kwalificator x categorie x modifier per taal van de markt. Dedup, gesorteerd.

    Modifier is taal-gematched aan de kwalificator en categorie (dezelfde taal).
    Romaanse talen (ADJECTIVE_AFTER_NOUN) gebruiken naamwoord-eerst volgorde.
    Elke kandidaat heeft minimaal 3 woorden. Onbekende markt → ValueError.
    """
    if market not in MARKET_LANGUAGES:
        raise ValueError(f"Onbekende markt '{market}' — kies uit {sorted(MARKET_LANGUAGES)}")
    candidates: set[str] = set()
    for lang in MARKET_LANGUAGES[market]:
        for qual in QUALIFIERS[lang]:
            for cat in CATEGORIES[lang]:
                for mod in MODIFIERS[lang]:
                    if lang in ADJECTIVE_AFTER_NOUN:
                        candidates.add(f"{cat} {qual} {mod}")
                    else:
                        candidates.add(f"{qual} {cat} {mod}")
    return sorted(candidates)
