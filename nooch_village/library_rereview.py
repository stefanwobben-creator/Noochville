"""Her-review van geëscaleerde bibliotheek-termen met de gefixte heuristiek.

Termen die ooit (onterecht) escaleerden blijven hangen: de dedup blokkeert dat de aanjager
ze opnieuw voorstelt. Deze maintenance-stap haalt elke escalated-term opnieuw door de
heuristiek, met de destijds opgeslagen vraag-data (evidence) als demand, en hercureert naar
approved/forbidden waar de uitkomst nu duidelijk is. Bij twijfel (nog steeds escalate, of
geen vraag) blijft de term staan. Geen LLM, geen netwerk, geen credits.
"""
from __future__ import annotations

from nooch_village.skills_impl.library_skills import KeywordReviewSkill

# heuristiek-uitkomst → bibliotheek-status
_DECISION_STATUS = {"approve": "approved", "reject": "forbidden"}


def rereview_escalated(library, context, *, apply: bool = True, review=None) -> dict:
    """Her-beoordeel alle escalated-termen. apply=False = droogdraai (niets schrijven).

    Geeft terug: {'approved': [...], 'forbidden': [...], 'unchanged': int, 'total': int}.
    """
    review = review or KeywordReviewSkill()
    approved: list[str] = []
    forbidden: list[str] = []
    unchanged = 0

    for word, entry in list(library.all().items()):
        if entry.get("status") != "escalated":
            continue
        demand = entry.get("evidence", {}) or {}
        decision, reason = review._heuristic(word, demand, context)
        new_status = _DECISION_STATUS.get(decision)
        if new_status is None:                      # nog steeds escalate → laat staan
            unchanged += 1
            continue
        if apply:
            library.curate(word, new_status, reason, evidence=demand, by="rereview")
        (approved if new_status == "approved" else forbidden).append(word)

    return {
        "approved":  approved,
        "forbidden": forbidden,
        "unchanged": unchanged,
        "total":     len(approved) + len(forbidden) + unchanged,
    }
