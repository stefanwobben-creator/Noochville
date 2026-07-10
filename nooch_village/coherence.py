"""Gedeelde LLM-coherentie-evaluatie voor C-trechter en B-observer."""
from __future__ import annotations
import re

_COHERENCE_PROMPT = """\
Beoordeel of de volgende beschrijving één heldere, distincte rol beschrijft, \
of een vage thematische cluster van keywords.

Beschrijving: {gap_description}

Antwoord met precies dit formaat:
VERDICT: coherent
REASON: <één zin, max 20 woorden>

of:
VERDICT: vague
REASON: <één zin, max 20 woorden>

Voorbeelden coherent: 'juridische claims controleren', 'klantverhalen ophalen \
en verspreiden', 'persberichten schrijven'.
Voorbeelden vague: 'missie-alignment, transparantie, kernwaorden', \
'duurzaamheid en marketing', 'algemene communicatie'.\
"""


def parse_verdict_reason(raw: str, valid_verdicts: frozenset[str]) -> tuple[str, str]:
    """Parse een VERDICT:/REASON:-response, markdown- en whitespace-tolerant.

    Strip leading markdown-opmaak (* _ ` #) per regel vóór vergelijking.
    Returns (verdict, reason_text) of ("unparseable", raw[:80]).
    Gedeeld door evaluate_coherence en Noochie._weigh_in.
    """
    verdict = ""
    reason_text = ""
    for line in raw.splitlines():
        s = re.sub(r"^[*_`#\s]+", "", line).rstrip("*_` ").strip()
        if s.lower().startswith("verdict:"):
            verdict = s[len("verdict:"):].strip().lower()
        elif s.lower().startswith("reason:"):
            reason_text = s[len("reason:"):].strip()
    if verdict in valid_verdicts:
        return (verdict, reason_text)
    return ("unparseable", raw[:80])


def evaluate_coherence(gap_description: str) -> tuple[str, str]:
    """Vraag de LLM of een gap-beschrijving één heldere rol vormt.

    Returns (verdict, reason) met verdict in:
      "coherent"    — LLM beoordeelt als heldere, distincte rol
      "vague"       — LLM beoordeelt als vage cluster
      "unparseable" — antwoord onherkenbaar
      "error"       — geen response of exception
    """
    prompt = _COHERENCE_PROMPT.format(gap_description=gap_description)
    try:
        from nooch_village.llm import reason as _llm_reason
        raw = _llm_reason(prompt, call_site="coherence_gate")
    except Exception as exc:
        return ("error", str(exc))

    if raw is None:
        return ("error", "geen LLM-response")

    v, r = parse_verdict_reason(raw, frozenset({"coherent", "vague"}))
    if v == "unparseable":
        return ("unparseable", raw[:80])
    return (v, r)
