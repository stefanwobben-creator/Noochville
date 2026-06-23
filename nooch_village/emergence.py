"""Emergentie-trigger: bepaalt welke kaartjes 'bevestigd' genoeg zijn voor diep
vervolgonderzoek.

Een trend die maar één keer langskomt kan een eendagsvlieg zijn. Pas als hetzelfde
kaartje vaak genoeg opnieuw gegrond wordt (grounding_count bij of boven de drempel),
verdient de trend dat de scientist de waaróm uitzoekt. Zo investeren we diepgang waar
de wereld het herhaaldelijk bevestigt, en sparen we quota op ruis.

Puur en thread-vrij: alleen lezen op Insight-velden, geen I/O, geen bus.
"""
from __future__ import annotations

from nooch_village.insight import Insight

# Aantal groundings voordat een trend 'bevestigd' (geëmergeerd) heet.
# Stefan, STATE: koppel/verdiep pas na ~3 groundings (herhaling verdient gewicht).
EMERGENCE_THRESHOLD = 3


def is_emerged(note: Insight, threshold: int = EMERGENCE_THRESHOLD) -> bool:
    """True zodra het kaartje vaak genoeg gegrond is (grounding_count >= drempel).
    Eronder: nog een eendagsvlieg, geen diep onderzoek waard."""
    return note.grounding_count >= threshold


def emerged(notes: list[Insight], threshold: int = EMERGENCE_THRESHOLD) -> list[Insight]:
    """Selecteer de bevestigde kaartjes uit een lijst, in dezelfde volgorde."""
    return [n for n in notes if is_emerged(n, threshold)]
