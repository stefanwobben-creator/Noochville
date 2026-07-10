"""voorstel_schrijven — Noochie werkt een vage spanning uit tot een concreet voorstel.

Noochie is de brug tussen The Source en de bewoners. Deze skill neemt een gevoelde
spanning (een means-gap, een gat) en maakt er met de LLM een concreet voorstel van dat
de mens kan beoordelen: een heldere scope, een kandidaat-aanpak en de afwegingen.

Mens-facing rapportage → Nederlands (de taal van The Source). Fail-closed: geen LLM →
geen voorstel (de mens moet niet op een verzonnen plan kunnen afgaan).
"""
from __future__ import annotations

from nooch_village.skills import Skill


class VoorstelSchrijvenSkill(Skill):
    name = "voorstel_schrijven"
    description = ("Werk een vage spanning uit tot een concreet voorstel (scope, aanpak, "
                   "afweging) dat de mens kan beoordelen.")
    cost = "free"            # begrensde LLM-tokenkost, zoals bulletin_schrijven
    side_effect_free = True  # leest + geeft terug; schrijft zelf niets
    input_schema = "tension: str (verplicht), role: str, gap_key: str"
    output_schema = "ok: bool, voorstel: str | error: str"

    def run(self, payload: dict, context=None) -> dict:
        tension = (payload.get("tension") or "").strip()
        role = (payload.get("role") or "").strip()
        if not tension:
            return {"ok": False, "error": "geen spanning meegegeven"}

        from nooch_village.llm import reason
        prompt = (
            "Je bent Noochie, de brug tussen The Source (de oprichter) en de bewoners van "
            "NoochVille (duurzaam, plantaardig schoenenmerk: geen plastic, geen leer, eerlijk, "
            "transparant). Een rol voelde deze spanning en vraagt jou er een concreet voorstel "
            "van te maken dat The Source kan beoordelen.\n\n"
            f"Spanning{f' (gevoeld door {role})' if role else ''}:\n\"{tension}\"\n\n"
            "Schrijf een kort, concreet voorstel in het Nederlands, in precies deze drie regels:\n"
            "SCOPE: <de concrete uitkomst die je voorstelt, één zin>\n"
            "AANPAK: <de eerste concrete stappen, één of twee zinnen>\n"
            "AFWEGING: <de belangrijkste afweging of voorwaarde, één zin>\n"
            "Verzin geen feiten; blijf bij wat uit de spanning volgt. Geen extra tekst."
        )
        out = reason(prompt, call_site="skill_voorstel")
        if not out or not out.strip():
            return {"ok": False, "error": "geen LLM beschikbaar — geen voorstel (fail-closed)"}
        return {"ok": True, "voorstel": out.strip(), "by": "noochie"}
