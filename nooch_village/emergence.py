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


def select_for_deepening(
    notes: list[Insight],
    budget: int,
    threshold: int = EMERGENCE_THRESHOLD,
) -> list[Insight]:
    """Kies welke kaartjes deze ronde diep onderzoek krijgen, met drie remmen tegelijk:

    - emergentie: alleen bevestigde kaartjes (grounding_count >= drempel);
    - diepte (één hop): geen kind-kaartjes — een kaartje dat zelf uit iets anders
      geboren is (een uitgaande link heeft) wordt niet verder verdiept;
    - geen herhaling (één vraag per trend): een trend die al een kind heeft (waar
      een ander kaartje naar wijst) wordt overgeslagen;
    - budget: hooguit `budget` kaartjes, sterkste trends eerst (grounding_count desc,
      daarna id voor een stabiele volgorde).

    Puur en thread-vrij. Aanname (v1): elke uitgaande/inkomende link telt als
    geboren-uit; associatieve dwarslinks (3c) zijn nu nog zeldzaam en mogen een
    kaartje hooguit conservatief van verdieping uitsluiten.
    """
    if budget <= 0:
        return []
    heeft_kind = {tid for n in notes for tid in n.links_to}  # ids waar iets naar wijst
    eligible = [
        n for n in notes
        if is_emerged(n, threshold)   # bevestigd
        and not n.links_to            # geen kind-kaartje (depth 1)
        and n.id not in heeft_kind    # nog niet verdiept (geen bestaand kind)
    ]
    eligible.sort(key=lambda n: (-n.grounding_count, n.id))
    return eligible[:budget]
