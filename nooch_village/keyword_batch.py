"""Pure batch-voorstel-builder. Importeert alleen keyword_matrix, geen dorps-machinerie."""
from __future__ import annotations
from nooch_village.keyword_matrix import core_candidates, longtail_candidates

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
