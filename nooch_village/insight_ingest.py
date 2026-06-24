from __future__ import annotations
import hashlib
from nooch_village.insight import Insight, GroundingStatus


def _slug(word: str) -> str:
    h = hashlib.sha256(word.lower().encode()).hexdigest()[:10]
    return f"grounding_{h}"


def insight_from_grounding(
    word: str,
    assessment: str,
    evidence: list[dict] | None = None,
    concept_id: str | None = None,
) -> Insight | None:
    """Bouw een ongegrond kaartje uit een grounding-assessment. Fail-closed.

    Geen assessment betekent geen kaartje (None). Het kaartje ontstaat op
    GroundingStatus.UNRESOLVED als AI-voorstel; promotie blijft mens-gated.

    Het kaartje draagt expliciete `grounds` (het bewijs achter de claim), zodat het
    onder hetzelfde curator-contract valt als de rest van de kennislaag. Geen bronnen
    is zelf een eerlijk bewijsstuk ("niets gevonden in ..."). Het kaartje wordt vóór
    teruggave gevalideerd via curate.validate_card (id-slug + claim + grounds gevuld);
    faalt dat, dan None (fail-closed, geen misvormd kaartje in de laag).
    """
    if not assessment or not assessment.strip():
        return None
    evidence = evidence or []
    titels = "; ".join(e.get("title", "?") for e in evidence[:3]) if evidence else ""
    if evidence:
        grounds = "Grounded in: " + "; ".join(
            f"{e.get('title','?')} ({e.get('year','?')})" for e in evidence[:3])
    else:
        grounds = "No academic sources found (searched OpenAlex + Semantic Scholar, v1)."

    card = Insight(
        id=_slug(word),
        claim=assessment.strip(),
        source=f"grounding:{word}",
        word=word,
        status=GroundingStatus.UNRESOLVED,
        reference=titels or None,
        grounds=grounds,
        concept_id=concept_id,
    )
    # Contract-poort, gedeeld met de curator: id-slug + claim + grounds gevuld.
    from nooch_village.curate import validate_card
    if not validate_card({"id": card.id, "claim": card.claim, "grounds": card.grounds}):
        return None
    return card
