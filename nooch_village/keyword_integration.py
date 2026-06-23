"""Pure uitvoeringskern: batch meten en levende termen als keyword_proposed publiceren.

Geen dorps-machinerie, geen inbox-plumbing — alleen de meet-en-publiceer-pijp.
"""
from __future__ import annotations

from nooch_village.keyword_matrix import MARKET_LANGUAGES
from nooch_village.keyword_measure import measure_batch
from nooch_village.roles import _publish_keyword_proposed


def run_approved_keyword_batch(
    batch: dict,
    runner,
    bus,
    library,
    *,
    from_id: str,
    min_volume: int,
    approved_by: str,
) -> dict:
    """Meet een goedgekeurde keyword-batch en publiceer levende termen als keyword_proposed.

    Gooit PermissionError of ValueError als de credit-gate in measure_batch faalt —
    de runner is dan nooit aangeroepen en er is niets gepubliceerd.

    Per-term-fouten na een geslaagde meting worden gevangen: de spend is al gedaan,
    dus de overige termen gaan door. Fouten landen in summary["errors"].

    Returns:
        market, tier, credits_spent, measured, live, published, skipped_dedup, errors
    """
    approval = {
        "approved":        True,
        "credits_ceiling": batch["estimated_credits"],
        "by":              approved_by,
    }
    # Kan raisen: PermissionError (niet goedgekeurd) of ValueError (ceiling overschreden).
    # Beide propageren ongewijzigd — runner is dan niet aangeroepen.
    result = measure_batch(batch, approval, runner)

    market = batch["market"]
    # Een per-taal-batch draagt zijn eigen locale; valt terug op de eerste taal van de
    # markt als die ontbreekt (oude, gemengde batches).
    locale = batch.get("locale") or MARKET_LANGUAGES.get(market, [market])[0]

    live_results = [r for r in result["results"] if r.get("vol", 0) >= min_volume]

    published:     list[str] = []
    skipped_dedup: list[str] = []
    errors:        list[dict] = []

    for row in live_results:
        word = row["keyword"]
        demand = {
            "signal":      "positive",
            "source":      "keywords_everywhere",
            "locale":      locale,
            "volume":      row.get("vol", 0),
            "cpc":         row.get("cpc", 0.0),
            "competition": row.get("competition", 0.0),
            "market":      market,
            "data_source": batch.get("data_source", "cli"),
        }
        try:
            ok = _publish_keyword_proposed(bus, from_id, word, demand, library)
            if ok:
                published.append(word)
            else:
                skipped_dedup.append(word)
        except Exception as exc:
            errors.append({"word": word, "error": str(exc)})

    return {
        "market":        market,
        "tier":          batch.get("tier", ""),
        "credits_spent": result["credits_spent"],
        "measured":      len(result["results"]),
        "live":          len(live_results),
        "published":     published,
        "skipped_dedup": skipped_dedup,
        "errors":        errors,
    }
