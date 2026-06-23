"""Zelf-overbodigheid (pioniers-reflectie): is een rol nog nodig, of zijn al z'n
accountabilities inmiddels door andere live rollen gedekt?

Spiegelbeeld van gap-sensing. Gap-sensing vraagt "wat mist mij?"; dit vraagt "ben
ik nog nodig?". Een volledig gedekte rol is kandidaat om zichzelf op te heffen
(remove_role, mens-gegateerd). De pionier die verdwijnt zodra de bodem hersteld is:
een regeneratief systeem moet niet alleen aandikken maar ook zichzelf kunnen snoeien.

Puur en thread-vrij: alleen tekstvergelijking, geen I/O, geen bus, geen records-API.
"""
from __future__ import annotations

import re


def _tokens(text: str) -> set[str]:
    """Betekenisvolle tokens: woorden van >= 4 tekens, kleingeletterd. Korte
    functiewoorden (the, and, de, op) vallen weg zodat overlap inhoudelijk telt."""
    return {t for t in re.split(r"\W+", text.lower()) if len(t) >= 4}


def accountability_covered(acc: str, other_accs: list[str], min_shared: int = 2) -> bool:
    """Een accountability is gedekt als minstens één andere accountability er
    `min_shared` betekenisvolle tokens mee deelt. Lege of triviale tekst (te weinig
    eigen tokens) dekt nooit; fail-closed richting behouden van de rol."""
    mine = _tokens(acc)
    if len(mine) < min_shared:
        return False
    return any(len(mine & _tokens(other)) >= min_shared for other in other_accs)


def is_redundant(my_accs: list[str], others: dict[str, list[str]],
                 min_shared: int = 2) -> tuple[bool, list[str]]:
    """Volledig redundant = ELKE eigen accountability is door minstens één andere
    rol gedekt. Geeft (redundant, gesorteerde lijst dekkende rol-ids).

    Fail-closed richting behouden: een rol zonder accountabilities, of met ook maar
    één accountability die nergens gedekt is, is NIET redundant.
    """
    if not my_accs:
        return False, []
    coverers: set[str] = set()
    for acc in my_accs:
        gedekt_door = [rid for rid, accs in others.items()
                       if accountability_covered(acc, accs, min_shared)]
        if not gedekt_door:
            return False, []
        coverers.update(gedekt_door)
    return True, sorted(coverers)
