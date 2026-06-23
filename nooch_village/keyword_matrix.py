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

# Welke geo (keywords_everywhere country-param) hoort bij welke taal? Een term wordt
# gemeten in de markt waar die taal echt gezocht wordt: Engels in Groot-Brittannië,
# niet in Nederland. Dit dwingt "EN-woord in EN-bron, NL-woord in NL-bron" af op de meting.
LOCALE_GEO: dict[str, str] = {
    "nl": "nl",
    "en": "gb",
    "de": "de",
    "sv": "se",
    "fr": "fr",
    "es": "es",
    "it": "it",
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


def _phrase(lang: str, qual: str, cat: str, mod: str | None = None) -> str:
    """Bouw één keyword-frase in de juiste woordvolgorde voor de taal."""
    if lang in ADJECTIVE_AFTER_NOUN:
        base = f"{cat} {qual}"
    else:
        base = f"{qual} {cat}"
    return f"{base} {mod}" if mod else base


def core_candidates_for_locale(locale: str) -> list[str]:
    """Kwalificator x categorie voor één taal. Dedup, gesorteerd, min. 2 woorden.

    Onbekende taal → ValueError.
    """
    if locale not in QUALIFIERS:
        raise ValueError(f"Onbekende taal '{locale}' — kies uit {sorted(QUALIFIERS)}")
    return sorted({
        _phrase(locale, qual, cat)
        for qual in QUALIFIERS[locale]
        for cat in CATEGORIES[locale]
    })


def longtail_candidates_for_locale(locale: str) -> list[str]:
    """Kwalificator x categorie x modifier voor één taal. Dedup, gesorteerd, min. 3 woorden.

    Onbekende taal → ValueError.
    """
    if locale not in QUALIFIERS:
        raise ValueError(f"Onbekende taal '{locale}' — kies uit {sorted(QUALIFIERS)}")
    return sorted({
        _phrase(locale, qual, cat, mod)
        for qual in QUALIFIERS[locale]
        for cat in CATEGORIES[locale]
        for mod in MODIFIERS[locale]
    })


def core_candidates(market: str) -> list[str]:
    """Kwalificator x categorie over alle talen van de markt. Dedup, gesorteerd.

    Elke kandidaat heeft minimaal 2 woorden. Onbekende markt → ValueError.
    """
    if market not in MARKET_LANGUAGES:
        raise ValueError(f"Onbekende markt '{market}' — kies uit {sorted(MARKET_LANGUAGES)}")
    candidates: set[str] = set()
    for lang in MARKET_LANGUAGES[market]:
        candidates.update(core_candidates_for_locale(lang))
    return sorted(candidates)


def longtail_candidates(market: str) -> list[str]:
    """Kwalificator x categorie x modifier over alle talen van de markt. Dedup, gesorteerd.

    Elke kandidaat heeft minimaal 3 woorden. Onbekende markt → ValueError.
    """
    if market not in MARKET_LANGUAGES:
        raise ValueError(f"Onbekende markt '{market}' — kies uit {sorted(MARKET_LANGUAGES)}")
    candidates: set[str] = set()
    for lang in MARKET_LANGUAGES[market]:
        candidates.update(longtail_candidates_for_locale(lang))
    return sorted(candidates)
