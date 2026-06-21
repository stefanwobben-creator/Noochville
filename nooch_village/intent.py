"""Intentielaag: prioriteer acties aan de hand van strategie-heuristieken en actieve doelen.

Gebruik:
    from nooch_village.intent import prioritize
    ranked = prioritize(actions, context)

Elke actie is een dict met minimaal 'label' en 'description'.
Terugkeer: gesorteerde lijst (beste eerst) met 'score', 'dropped' en 'drop_reason' toegevoegd.
"""
from __future__ import annotations
from nooch_village.config import Context
from nooch_village.policy import INTENT_VIOLATIONS as _POLICY_VIOLATIONS

_SCHOEN_WOORDEN = (
    "schoen", "schoenen", "shoe", "shoes",
    "sneaker", "sneakers", "schuh", "schuhe",
    "boot", "boots", "laars", "laarzen", "stiefel",
    "sandaal", "sandalen", "sandal", "sandals", "sandale",
    "loafer", "loafers", "espadrille", "espadrilles",
    "pump", "pumps", "slipper", "slippers",
    "barefoot", "minimalist",
    "footwear", "schoeisel",
)


def _is_schoen_domein(desc_l: str) -> bool:
    """Grof domeinfilter: bevat de term een schoen-categoriewoord?
    Bewust grof — vangt off-domein ruis (brood, kernenergie, funderingsherstel),
    laat aan de randen een enkele legitieme term vallen (kale merknaam). Te verfijnen later."""
    return any(w in desc_l for w in _SCHOEN_WOORDEN)


def _violates_policy(desc_l: str) -> str | None:
    for pattern, reason in _POLICY_VIOLATIONS:
        if pattern in desc_l:
            return reason
    return None


def _goal_score(desc_l: str, goals: list[dict]) -> float:
    """Punten voor elke bijdrage-signal van een actief doel die in de actie voorkomt."""
    score = 0.0
    for goal in goals:
        if not goal.get("active", True):
            continue
        for signal in goal.get("contributes_via", []):
            if signal.lower() in desc_l:
                score += 1.0
    return score


def _strategy_score(desc_l: str, heuristics: list[str]) -> float:
    """Kleine bonus als de actie woorden deelt met een strategie-heuristiek."""
    score = 0.0
    for h in heuristics:
        for word in h.lower().split():
            if len(word) >= 7 and word in desc_l:
                score += 0.3
                break   # één match per heuristiek is genoeg
    return score


def prioritize(actions: list[dict], context: Context) -> list[dict]:
    """Rangschik acties op bijdrage aan doelen binnen de strategie.

    Prioriteitsvolgorde (hard ingebakken):
      Missie > Policy > Strategie > Doel
    Een doel mag nooit een policy of de missie overrulen.
    Acties die een policy schenden worden gemarkeerd als dropped=True.
    """
    strategy_data = getattr(context, "strategy", None) or {}
    heuristics = strategy_data.get("strategy", [])
    goals = strategy_data.get("goals", [])

    result = []
    for action in actions:
        desc_l = (action.get("description", "") + " " + action.get("label", "")).lower()
        violation = _violates_policy(desc_l)
        if violation:
            result.append({**action, "score": -1.0, "dropped": True, "drop_reason": violation})
            continue
        if not _is_schoen_domein(desc_l):
            result.append({**action, "score": -1.0, "dropped": True,
                           "drop_reason": "geen schoen-categorie (off-domein)"})
            continue
        score = _goal_score(desc_l, goals) + _strategy_score(desc_l, heuristics)
        result.append({**action, "score": score, "dropped": False, "drop_reason": None})

    # Niet-afgevallen acties eerst (op score desc), afgevallen acties achteraan
    return sorted(result, key=lambda a: (0 if a["dropped"] else 1, a["score"]), reverse=True)
