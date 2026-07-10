from __future__ import annotations
from nooch_village.skills import Skill


class ContentCheckSkill(Skill):
    """Eindcheck van een (door een mens herschreven) publieke tekst.

    Twee lagen:
      1. Harde claim-gate (review_publication): verboden woorden + alleen geverifieerde
         kaartjes als harde claim, per publicatie-soort. Deterministisch.
      2. LLM-toets tegen de merk-copyregels (context.copy_rules): adviezen om de tekst
         scherper op stem/framing/checks te krijgen.

    Read-only, fail-closed: zonder LLM vervalt alleen de advies-laag; de harde gate blijft
    deterministisch werken. Zonder notes-store kan de claim-laag niet toetsen.
    """
    name = "content_check"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    side_effect_free = True
    description = "Eindcheck van publieke tekst: claim-gate (verified/verboden woorden) plus LLM-toets tegen copy_rules."
    input_schema = "payload: {'text': str, 'claim_insight_ids': [str], 'kind': str, 'locale'?: str}; context.notes + context.copy_rules."
    output_schema = "{'gate_ok': bool, 'forbidden_words': [str], 'claim_issues': [dict], 'suggestions': str|None}"

    def run(self, payload: dict, context) -> dict:
        from nooch_village.publication_check import (
            review_publication, PublicationKind, PublicationReport,
        )
        text = payload.get("text", "") or ""
        claim_ids = payload.get("claim_insight_ids", [])
        try:
            kind = PublicationKind(payload.get("kind", "blog"))
        except ValueError:
            kind = PublicationKind.BLOG

        store = getattr(context, "notes", None) if context is not None else None
        report = (review_publication(text, claim_ids, kind, store)
                  if store is not None else PublicationReport())

        suggestions = self._llm_check(
            text,
            getattr(context, "copy_rules", "") if context is not None else "",
            payload.get("locale"),
        )
        return {
            "gate_ok": report.ok,
            "forbidden_words": list(report.forbidden_words),
            "claim_issues": [{"insight_id": ci.insight_id, "reason": ci.reason}
                             for ci in report.claim_issues],
            "suggestions": suggestions,
        }

    def _llm_check(self, text: str, rules: str, locale: str | None = None) -> str | None:
        from nooch_village.llm import reason
        from nooch_village.language import instruction
        if not text or not rules:
            return None
        prompt = (
            "Je bent de eindredacteur van Nooch. Toets de onderstaande tekst aan de "
            "merk-copyregels. Noem concreet en kort waar de tekst de regels schendt of "
            "beter kan (toon, de vier checks, framing, de lezer). Voldoet de tekst, "
            "antwoord dan exact: OK.\n\n"
            f"Copyregels:\n{rules}\n\n"
            f"Tekst:\n{text}\n\n"
            + instruction(locale)
        )
        out = reason(prompt, call_site="skill_content_check")
        return out.strip() if out else None
