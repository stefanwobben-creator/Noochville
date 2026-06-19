"""Keyword-meet-orchestratie met credit-gate. Geen dorps-machinerie, geen netwerk."""
from __future__ import annotations
from typing import Callable


def measure_batch(
    batch: dict,
    approval: dict | None,
    runner: Callable[[list[str], str, str], list[dict]],
) -> dict:
    """Orchestreert een keyword-meting via een geïnjecteerde runner, achter een credit-gate.

    Gate (fail-closed, in volgorde — runner wordt NIET aangeroepen bij weigering):
      1. approval is None of approved is niet exact True → PermissionError
      2. credits_ceiling ontbreekt of estimated_credits > credits_ceiling → ValueError
      3. Roep runner precies één keer aan.

    Args:
        batch:    propose_batch-vormig dict (candidates, country, data_source, estimated_credits, ...)
        approval: {"approved": bool, "credits_ceiling": int, "by": str} of None
        runner:   callable(candidates, country, data_source) -> list[dict]

    Returns:
        market, tier, data_source, country, requested, credits_spent, results
    """
    if approval is None or approval.get("approved") is not True:
        raise PermissionError("batch niet goedgekeurd — runner niet aangeroepen")

    ceiling = approval.get("credits_ceiling")
    if ceiling is None or batch["estimated_credits"] > ceiling:
        raise ValueError(
            f"batch overschrijdt goedgekeurd creditplafond "
            f"({batch['estimated_credits']} > {ceiling})"
        )

    results = runner(batch["candidates"], batch["country"], batch["data_source"])

    return {
        "market":        batch["market"],
        "tier":          batch["tier"],
        "data_source":   batch["data_source"],
        "country":       batch["country"],
        "requested":     batch["candidates"],
        "credits_spent": len(batch["candidates"]),
        "results":       results,
    }
