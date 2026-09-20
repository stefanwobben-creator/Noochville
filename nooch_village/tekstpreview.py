"""Korte afgeleide van een lange tekst — één afleidingsplek, geen tweede feit.

Stond in `notifications.py`. Die module is in B2 (20 september 2026) met de inbox verdwenen, maar
deze twee functies gingen nooit over notificaties: het zijn tekst-hulpjes. `afslank_afhankelijkheden`
gebruikt `preview` om een regel in te korten, en dat blijft gewoon waar.

DE ELLIPS TELT MEE IN HET BUDGET — zie de opmerking hieronder. Dat is de soort afspraak die je
kwijtraakt als je zo'n functie bij een verhuizing "even opnieuw schrijft".
"""
from __future__ import annotations

PREVIEW_MAX = 160


def preview(tekst: str, n: int = PREVIEW_MAX) -> str:
    """De korte afgeleide van een volledige tekst. Eén afleidingsplek, geen tweede feit."""
    t = " ".join(str(tekst or "").split())
    if len(t) <= n:
        return t
    # De ellips telt MEE in het budget: `n` is de maximale lengte van wat je overhoudt, niet van
    # wat je afknipt. Zonder deze regel wordt een tekst zonder spaties n+1 lang, en dan klopt de
    # belofte 'hoogstens n' niet meer. Mijn eigen test wees dat aan.
    ruimte = max(1, n - 1)
    kort = t[:ruimte].rsplit(" ", 1)[0]
    return (kort or t[:ruimte]) + "…"


def volledig(n: dict) -> str:
    """De hele tekst van een notificatie.

    Valt terug op `snippet` voor items van vóór 30 aug 2026: die hebben geen `tekst`, en hun
    origineel is weg. Beter de afgekapte waarheid dan een leeg scherm — maar het is wél afgekapt,
    en dat is precies waarom dit veld nu bestaat."""
    return str((n or {}).get("tekst") or (n or {}).get("snippet") or "")
