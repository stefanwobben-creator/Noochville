"""Kleine statistiek-primitieven die door meerdere meetlagen worden gedeeld.

Bestaat om één reden: het Wilson-score-interval leefde in `experiments/stage0/eval_triage.py` en
werd door de Founder Flow opnieuw nodig. "Reference, don't copy" (CLAUDE.md) — één gezaghebbende
plek, twee lezers. Verandert de statistiek, dan verandert hij overal mee.

Waarom Wilson en niet een puntschatting: bij de aantallen waarop we hier oordelen (tientallen
beslissingen, geen duizenden) is een punt van 90% niet te onderscheiden van 75%. Een poort die op
het punt beslist, promoveert op ruis. Daarom oordeelt elke poort in dit project op de ONDERGRENS
van het 95%-interval — precies zoals de Stage-0-dismiss-precision dat voorschrijft.
"""
from __future__ import annotations

import math

Z95 = 1.959963984540054  # tweezijdig 95%


def wilson(successes: float, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score-interval voor een proportie. Robuust bij kleine n (anders dan de
    normaal-benadering, die bij p≈1 een ondergrens boven 1 of onder 0 kan geven).

    `successes` mag fractioneel zijn (verwachting over een gelijkspel-groep); voor het interval
    wordt hij dan afgerond — de caller hoort dat zichtbaar te maken, niet weg te moffelen."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def wilson_lower(successes: float, n: int, z: float = Z95) -> float:
    """Alleen de ondergrens — de waarde waarop een promotie-poort hoort te beslissen."""
    return wilson(successes, n, z)[0]
