"""De KE-aanjager: zet per taal een meet-batch in de human inbox.

Lost de twee live geziene gaten op: er was geen trigger die een keyword-batch voorstelde,
en de meting mengde talen in één geo. Hier wordt per taal één batch voorgesteld, elk met
de juiste geo (en→gb, nl→nl). Credits blijven mens-gated: dit zet alleen voorstellen klaar,
de mens keurt goed in de human inbox. Geen netwerk, geen credits, geen dorps-threads.
"""
from __future__ import annotations

from nooch_village.keyword_batch import propose_locale_batch

# Engels is de default-werktaal van het dorp; Nederlands is de thuismarkt.
DEFAULT_LOCALES: list[str] = ["en", "nl"]


def propose_locale_batches(inbox, locales: list[str] | None = None,
                           tier: str = "core") -> list[dict]:
    """Zet voor elke taal een meet-batch in de human inbox.

    Dedup zit in add_keyword_batch (zelfde taal/geo/tier die nog pending is → geen duplicaat).
    Geeft per batch terug: locale, geo, candidates (aantal), iid.
    """
    locales = locales or DEFAULT_LOCALES
    queued: list[dict] = []
    for loc in locales:
        b = propose_locale_batch(loc, tier=tier)
        iid = inbox.add_keyword_batch(
            b["market"], b["tier"], b["candidates"], b["estimated_credits"],
            geo=b["country"], locale=b["locale"],
        )
        queued.append({
            "locale":     loc,
            "geo":        b["country"],
            "candidates": len(b["candidates"]),
            "iid":        iid,
        })
    return queued
