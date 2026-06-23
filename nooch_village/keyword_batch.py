"""Pure batch-voorstel-builder. Importeert alleen keyword_matrix, geen dorps-machinerie."""
from __future__ import annotations
from nooch_village.keyword_matrix import (
    core_candidates, longtail_candidates,
    core_candidates_for_locale, longtail_candidates_for_locale,
    LOCALE_GEO,
)

_VALID_TIERS = {"core", "longtail"}


def propose_batch(market: str, tier: str = "core", data_source: str = "cli") -> dict:
    """Bouwt een meet-batch-voorstel voor keywords_everywhere.

    Geen betaalde call, geen state — puur de matrix-output bundelen met
    kostenschatting en metadata. Onbekende markt → ValueError (via matrix).
    Onbekende tier → ValueError (hier).

    Returns:
        market          str       — de markt
        country         str       — keywords_everywhere country-param (nu gelijk aan market)
        data_source     str       — "cli" of "gkp"
        tier            str       — "core" of "longtail"
        candidates      list[str] — uit de matrix, max 100 (skill-cap)
        estimated_credits int     — 1 credit per keyword
    """
    if tier not in _VALID_TIERS:
        raise ValueError(f"Onbekende tier '{tier}' — kies 'core' of 'longtail'")

    candidates = core_candidates(market) if tier == "core" else longtail_candidates(market)

    return {
        "market":            market,
        "country":           market,
        "data_source":       data_source,
        "tier":              tier,
        "candidates":        candidates,
        "estimated_credits": len(candidates),
    }


def propose_locale_batch(locale: str, tier: str = "core", data_source: str = "cli") -> dict:
    """Bouwt een meet-batch voor één taal, gemeten in de bijbehorende geo.

    Eén taal, één geo: Engelse termen gaan naar de gb-geo, Nederlandse naar nl. Zo wordt
    elk woord gemeten waar het echt gezocht wordt ("EN-woord in EN-bron"). De batch draagt
    een expliciete `locale` zodat het label tot in keyword_proposed klopt.

    Onbekende taal → ValueError (via matrix). Onbekende tier → ValueError (hier).

    Returns: locale, market (=geo), country (=geo), data_source, tier, candidates,
    estimated_credits.
    """
    if tier not in _VALID_TIERS:
        raise ValueError(f"Onbekende tier '{tier}' — kies 'core' of 'longtail'")
    if locale not in LOCALE_GEO:
        raise ValueError(f"Onbekende taal '{locale}' — kies uit {sorted(LOCALE_GEO)}")

    geo = LOCALE_GEO[locale]
    candidates = (core_candidates_for_locale(locale) if tier == "core"
                  else longtail_candidates_for_locale(locale))

    return {
        "locale":            locale,
        "market":            geo,
        "country":           geo,
        "data_source":       data_source,
        "tier":              tier,
        "candidates":        candidates,
        "estimated_credits": len(candidates),
    }
