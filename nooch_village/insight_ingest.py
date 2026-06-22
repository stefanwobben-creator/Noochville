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
    De bronnen worden in reference samengevat.
    """
    if not assessment or not assessment.strip():
        return None
    evidence = evidence or []
    titels = "; ".join(e.get("title", "?") for e in evidence[:3]) if evidence else ""
    return Insight(
        id=_slug(word),
        claim=assessment.strip(),
        source=f"grounding:{word}",
        word=word,
        status=GroundingStatus.UNRESOLVED,
        reference=titels or None,
        concept_id=concept_id,
    )
