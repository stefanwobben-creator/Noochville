"""Intentielaag: prioriteer acties aan de hand van strategie-heuristieken en actieve doelen.

Gebruik:
    from nooch_village.intent import prioritize
    ranked = prioritize(actions, context)

Elke actie is een dict met minimaal 'label' en 'description'.
Terugkeer: gesorteerde lijst (beste eerst) met 'score', 'dropped' en 'drop_reason' toegevoegd.
"""
from __future__ import annotations
from nooch_village.config import Context

# Patronen in label+description die een harde Anchor-policy schenden.
# Volgorde: meest specifiek eerst.
_POLICY_VIOLATIONS: list[tuple[str, str]] = [
    ("google ads",          "advertising is verboden via Anchor-policy"),
    ("facebook ads",        "advertising is verboden via Anchor-policy"),
    ("instagram ads",       "advertising is verboden via Anchor-policy"),
    ("betaald adverter",    "advertising is verboden via Anchor-policy"),
    ("betaalde reclame",    "advertising is verboden via Anchor-policy"),
    ("advertentiebudget",   "advertising is verboden via Anchor-policy"),
    ("advertis",            "advertising is verboden via Anchor-policy"),
    ("voorraadopbouw",      "voorraadopbouw is verboden (on-demand productie, Anchor-policy)"),
    ("overproductie",       "overproductie is verboden via Anchor-policy"),
    ("marktplaats",         "verkoop via externe kanalen is verboden; alleen nooch.earth"),
    ("bol.com",             "verkoop via externe kanalen is verboden; alleen nooch.earth"),
    ("amazon",              "verkoop via externe kanalen is verboden; alleen nooch.earth"),
]


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
        score = _goal_score(desc_l, goals) + _strategy_score(desc_l, heuristics)
        result.append({**action, "score": score, "dropped": False, "drop_reason": None})

    # Niet-afgevallen acties eerst (op score desc), afgevallen acties achteraan
    return sorted(result, key=lambda a: (0 if a["dropped"] else 1, a["score"]), reverse=True)
