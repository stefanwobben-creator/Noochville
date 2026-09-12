"""verband_voorstel — hebben twee kennis-kaarten een écht inhoudelijk verband?

De Librarian draait dit in haar dagreflectie over kandidaat-paren en leest `verband`; een ja gaat
als voorstel naar de human-inbox (de mens legt het touwtje). Een dorpsrol kan hem ook als
checklist-item plannen.

SCOPE 57 (skill-review 12-09-2026): drie oorzaken gaven één antwoord, `{"verband": False}` —
geen model, een onparseerbaar antwoord én een echt nee lazen alle drie als "geen verband", en
een kale bool telt op de wall niet als inhoud ("🕳 geen resultaat"). Nu: geen model → `error`,
onparseerbaar → `error`, echt nee → `no_data` met reden (📭), ja → de verbindende claim. De
Librarian-lus (`uitslag.get("verband")`) leest alle vier onveranderd.
"""
from __future__ import annotations
import re
from nooch_village.skills import Skill

# Liberaal: het Engelse token is het contract, het Nederlandse de overgangs-tolerantie voor een
# model dat doorschiet (prompt en parser horen bij elkaar — zie test_i18n_prompt_grens).
_ANTWOORD = re.compile(r"(?:CONNECTION|VERBAND):\s*(yes|no|ja|nee)\b\s*\|?\s*(?:CLAIM:\s*(.*))?",
                       re.IGNORECASE | re.DOTALL)
_JA = {"yes", "ja"}


def _kaart(v) -> dict:
    return v if isinstance(v, dict) else {}


class VerbandVoorstelSkill(Skill):
    name = "verband_voorstel"
    cost = "free"
    description = ("Judge whether two knowledge cards have a real, non-trivial connection and, if so, "
                   "propose the one claim that links them. A shared word is not a connection; two "
                   "cards saying the same thing are not either.")
    input_schema = ("kaart_a: {word: str, claim: str} (required — the first card); "
                    "kaart_b: {word: str, claim: str} (required — the second card)")
    required_payload = ("kaart_a", "kaart_b")
    output_schema = ("verband: True, claim: str | ok, verband: False, no_data, reason (no real "
                     "connection) | error (no model / unparseable answer)")

    def validate_payload(self, payload: dict, context) -> list:
        """Beide kaarten moeten een claim dragen; een kaart zonder tekst is niets om te verbinden."""
        p = payload or {}
        redenen = []
        for naam in ("kaart_a", "kaart_b"):
            k = p.get(naam)
            if k is not None and not str(_kaart(k).get("claim") or "").strip():
                redenen.append(f"'{naam}' must be an object with a non-empty 'claim'")
        return redenen

    def run(self, payload: dict, context) -> dict:
        p = payload or {}
        a, b = _kaart(p.get("kaart_a")), _kaart(p.get("kaart_b"))
        if not str(a.get("claim") or "").strip() or not str(b.get("claim") or "").strip():
            return {"error": "two cards are required: 'kaart_a' and 'kaart_b', each with a 'claim'"}
        from nooch_village.llm import reason
        from nooch_village.language import instruction
        prompt = (
            "You judge whether two knowledge cards about sustainable footwear have a meaningful, "
            "non-trivial substantive connection. A shared word is NOT a connection; there must be a "
            "real thought that links the two. Also NOT a connection: two cards that say the same "
            "thing, or that both share an empty or negative outcome (such as 'both found no "
            "evidence'). A connection must tie two DIFFERENT substantive ideas together, not note "
            "that two cards have the same or no content. Use only the two cards below; add no "
            "outside facts.\n\n"
            f"CARD A (about '{a.get('word', '')}'): {a.get('claim', '')}\n"
            f"CARD B (about '{b.get('word', '')}'): {b.get('claim', '')}\n\n"
            "Answer on EXACTLY one line in this format:\n"
            "CONNECTION: yes|no | CLAIM: <one sentence that links the two, only when yes>\n"
            "When in doubt or without a real connection: CONNECTION: no\n"
            + instruction()
        )
        out = reason(prompt, call_site="skill_verband", max_tokens=200)
        if not out or not str(out).strip():
            return {"error": "no answer from the model — connection not judged (fail-closed)"}
        m = _ANTWOORD.search(str(out))
        if not m:
            return {"error": f"the model's answer is not in the CONNECTION: yes|no | CLAIM: … format "
                             f"({len(str(out))} chars) — connection not judged"}
        claim = (m.group(2) or "").strip()
        if m.group(1).lower() not in _JA or not claim:
            return {"ok": True, "verband": False, "no_data": True,
                    "reason": "no substantive connection between the two cards"}
        return {"verband": True, "claim": claim}
