"""Gedeelde LLM-coherentie-evaluatie voor C-trechter en B-observer."""
from __future__ import annotations

_COHERENCE_PROMPT = """\
Beoordeel of de volgende beschrijving één heldere, distincte rol beschrijft, \
of een vage thematische cluster van keywords.

Beschrijving: {gap_description}

Antwoord met precies één regel in dit formaat:
VERDICT: coherent
REASON: <één zin, max 20 woorden>

of:
VERDICT: vague
REASON: <één zin, max 20 woorden>

Voorbeelden coherent: 'juridische claims controleren', 'klantverhalen ophalen \
en verspreiden', 'persberichten schrijven'.
Voorbeelden vague: 'missie-alignment, transparantie, kernwaarden', \
'duurzaamheid en marketing', 'algemene communicatie'.\
"""


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
        raw = _llm_reason(prompt)
    except Exception as exc:
        return ("error", str(exc))

    if raw is None:
        return ("error", "geen LLM-response")

    verdict = ""
    reason_text = ""
    for line in raw.splitlines():
        s = line.strip()
        if s.lower().startswith("verdict:"):
            verdict = s[len("verdict:"):].strip().lower()
        elif s.lower().startswith("reason:"):
            reason_text = s[len("reason:"):].strip()

    if verdict == "coherent":
        return ("coherent", reason_text)
    if verdict == "vague":
        return ("vague", reason_text)
    return ("unparseable", raw[:80])
