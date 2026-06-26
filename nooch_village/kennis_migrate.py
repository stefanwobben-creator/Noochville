"""Migratie met terugwerkende kracht: bestaande kaartjes hun SOORT geven.

Conservatief en mens-gated:
- Een kaartje dat al een `kind` heeft, blijft ongemoeid (respecteer eerdere beslissingen).
- Twijfel (classifier geeft None) → blijft onbeslist, gaat naar mens-review. Geen gokje.
- Definities → niet de kennislaag in, maar gemarkeerd voor het Lexicon.

`classify` is injecteerbaar: standaard de heuristiek (werkt zonder netwerk); op een machine met LLM
kan een rijkere classifier worden meegegeven die op de twijfelgevallen terugvalt op de heuristiek.
"""
from __future__ import annotations

from nooch_village.insight import Insight, ClaimKind
from nooch_village.claim_classify import classify_kind, looks_like_definition


def plan_migration(notes: list[Insight], classify=classify_kind) -> dict:
    """Maak een migratieplan (verandert niets). Geeft rijen + samenvatting.
    Rij: {id, claim, current, proposed, note}. proposed=None → onbeslist of definitie."""
    rows = []
    for n in notes:
        if n.kind is not None:
            rows.append({"id": n.id, "claim": (n.claim or "")[:70], "current": n.kind.value,
                         "proposed": None, "note": "al gezet — overslaan"})
            continue
        if looks_like_definition(n.claim or ""):
            rows.append({"id": n.id, "claim": (n.claim or "")[:70], "current": None,
                         "proposed": None, "note": "definitie → Lexicon (niet de kennislaag in)"})
            continue
        et = getattr(n.evidence_type, "value", None)
        k = classify(n.claim or "", et, n.source)
        rows.append({"id": n.id, "claim": (n.claim or "")[:70], "current": None,
                     "proposed": (k.value if k else None),
                     "note": "" if k else "onbeslist → mens-review"})

    from collections import Counter
    per = Counter(r["proposed"] for r in rows if r["proposed"] and r["note"] != "al gezet — overslaan")
    summary = {
        "totaal": len(rows),
        "al_gezet": sum(1 for r in rows if r["note"] == "al gezet — overslaan"),
        "definitie_lexicon": sum(1 for r in rows if "Lexicon" in r["note"]),
        "onbeslist_review": sum(1 for r in rows if r["note"] == "onbeslist → mens-review"),
        "toe_te_kennen": dict(per),
    }
    return {"rows": rows, "summary": summary}


def apply_plan(store, plan: dict) -> int:
    """Voer een plan uit: ken `proposed` toe aan de kaartjes die een soort kregen.
    Slaat 'al gezet', definities en onbeslist over (die blijven None → mens beslist).
    Geeft het aantal toegekende kaartjes."""
    applied = 0
    for r in plan["rows"]:
        if not r["proposed"]:
            continue
        if store.set_kind(r["id"], ClaimKind(r["proposed"])):
            applied += 1
    return applied
