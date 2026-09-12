"""voorstel_schrijven — Noochie werkt een vage spanning uit tot een concreet voorstel.

Noochie is de brug tussen The Source en de bewoners. Deze skill neemt een gevoelde
spanning (een means-gap, een gat) en maakt er met de LLM een concreet voorstel van dat
de mens kan beoordelen: een heldere scope, een kandidaat-aanpak en de afwegingen.

Mens-facing rapportage → Engels (de taal van de cockpit sinds i18n fase 1). Fail-closed: geen LLM →
geen voorstel (de mens moet niet op een verzonnen plan kunnen afgaan).
"""
from __future__ import annotations

from nooch_village.skills import Skill
from nooch_village.llm_keuze import skill_ladder


class VoorstelSchrijvenSkill(Skill):
    name = "voorstel_schrijven"
    description = ("Turn a vague tension into a concrete proposal the founder can judge: SCOPE, "
                   "APPROACH and TRADE-OFF in three lines, grounded in the constitution, the "
                   "Chronicle and earlier projects. Fail-closed: no model, no proposal.")
    cost = "free"            # begrensde LLM-tokenkost, zoals bulletin_schrijven
    side_effect_free = True  # leest + geeft terug; schrijft zelf niets
    input_schema = ("tension: str (required — the felt tension or gap, in one to three sentences); "
                    "role: str (optional — the role that felt it); gap_key: str (optional)")
    # Stond leeg terwijl het schema 'verplicht' zei: een lege tension werd pas live een ⚠️ op de
    # wall. Nu houdt de poort het item bij het plannen open (scope 57).
    required_payload = ("tension",)
    output_schema = "ok: bool, voorstel: str | error: str"

    def run(self, payload: dict, context=None) -> dict:
        tension = (payload.get("tension") or "").strip()
        role = (payload.get("role") or "").strip()
        if not tension:
            return {"ok": False, "error": "geen spanning meegegeven"}

        # Grounding: dezelfde sectie die de productie-prompts krijgen — grondwet, Kroniek,
        # inzichten mét falsifier, eerdere projecten. Een voorstel dat de mens moet beoordelen is
        # juist de plek waar een verzonnen aanname het duurst is. Fail-soft: geen data_dir of een
        # kapotte store → leeg blok, prompt ongewijzigd.
        grond = ""
        try:
            from nooch_village.kennis_context import kennis_blok, kennis_voor
            grond = kennis_blok(kennis_voor(getattr(context, "data_dir", None) or "", tension))
        except Exception:                                # noqa: BLE001 — nooit een voorstel blokkeren
            grond = ""

        from nooch_village.llm import reason
        prompt = (
            (grond + "\n\n" if grond else "")
            + "You are Noochie, the bridge between The Source (the founder) and the inhabitants of "
            "NoochVille (sustainable, plant-based shoe brand: no plastic, no leather, fair, "
            "transparent). A role felt this tension and asks you to turn it into a concrete "
            "proposal that The Source can judge.\n\n"
            f"Tension{f' (felt by {role})' if role else ''}:\n\"{tension}\"\n\n"
            "Write a short, concrete proposal in English, in exactly these three lines:\n"
            "SCOPE: <the concrete outcome you propose, one sentence>\n"
            "APPROACH: <the first concrete steps, one or two sentences>\n"
            "TRADE-OFF: <the most important trade-off or condition, one sentence>\n"
            "Invent no facts; stay with what follows from the tension. Stay inside the CONSTITUTION "
            "above, do not re-investigate what THE CHRONICLE already confirms, and do not present a "
            "knowledge gap as a finding. No extra text."
        )
        out = reason(prompt, call_site="skill_voorstel", ladder=skill_ladder("skill_voorstel"))
        if not out or not out.strip():
            return {"ok": False, "error": "geen LLM beschikbaar — geen voorstel (fail-closed)"}
        return {"ok": True, "voorstel": out.strip(), "by": "noochie"}

