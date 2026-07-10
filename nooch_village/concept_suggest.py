from __future__ import annotations
from nooch_village.llm import reason

GEEN = "GEEN"


def _format_concepts(concepts: list[dict]) -> str:
    lines = []
    for c in concepts:
        words = " / ".join(c.get("words", {}).values())
        lines.append(f"- {c['concept_id']}: {c.get('rationale', '')} (woorden: {words})")
    return "\n".join(lines)


def suggest_concept(keyword: str, concepts: list[dict], reason_fn=None) -> str | None:
    """Stel met de LLM een concept voor bij een keyword. Fail-closed.

    Geeft een concept_id uit `concepts` terug, of None als de LLM niet beschikbaar is,
    twijfelt (GEEN antwoordt), of iets teruggeeft dat niet exact een aangeboden
    concept_id is. De aanroeper geeft alleen approved concepten mee.
    """
    if not concepts:
        return None
    valid = {c["concept_id"] for c in concepts}
    prompt = (
        "Je koppelt een zoekwoord aan het best passende frame, of aan geen enkel frame.\n"
        f"Zoekwoord: {keyword}\n\n"
        "Frames:\n"
        f"{_format_concepts(concepts)}\n\n"
        f"Antwoord met exact een concept_id uit de lijst, of het woord {GEEN} als geen "
        "frame echt past. Geef alleen dat ene woord, geen uitleg. Twijfel je, antwoord "
        f"{GEEN}."
    )
    if reason_fn is None:
        import functools
        reason_fn = functools.partial(reason, call_site="concept_suggest")
    raw = reason_fn(prompt)
    if not raw:
        return None
    answer = raw.strip()
    if answer in valid:
        return answer
    return None
