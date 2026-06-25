"""SynthesizeCardsSkill — verbind twee kennis-kaartjes tot één emergente hypothese.

De creatieve sprong: niet samenvatten, maar de niet-voor-de-hand-liggende verbinding leggen die
ontstaat als je twee losse inzichten naast elkaar legt. Fail-closed: zonder LLM geen synthese
(geen verzonnen verband)."""
from __future__ import annotations
import logging
from nooch_village.skills import Skill

log = logging.getLogger(__name__)


class SynthesizeCardsSkill(Skill):
    name = "synthesize_cards"
    cost = "llm"
    side_effect_free = True
    description = ("Legt een creatieve, niet-voor-de-hand-liggende verbinding tussen twee "
                  "kennis-kaartjes en formuleert de emergente hypothese (geen samenvatting).")

    def run(self, payload: dict, context) -> dict:
        from nooch_village.llm import reason
        a = (payload.get("card_a") or "").strip()
        b = (payload.get("card_b") or "").strip()
        if not a or not b:
            return {"error": "twee kaartjes vereist"}
        mission = getattr(getattr(context, "mission", None), "purpose", "") or \
            "Nooch.earth: het duurzaamste schoenenmerk, plasticvrij en zonder leer."
        prompt = (
            f"Missie: {mission}\n\n"
            f"Kaartje A: {a}\n"
            f"Kaartje B: {b}\n\n"
            "Leg de niet-voor-de-hand-liggende verbinding tussen A en B. Niet samenvatten — "
            "formuleer de ÉNE emergente hypothese die ontstaat als je ze naast elkaar legt, en "
            "waarom dat voor Nooch een kans of inzicht is.\n\n"
            "Antwoord exact zo:\n"
            "SYNTHESE: <één scherpe zin: de emergente hypothese>\n"
            "WAAROM: <één zin: waarom dit voor Nooch relevant is>"
        )
        out = reason(prompt)
        if not out:
            return {"error": "geen LLM beschikbaar (fail-closed)"}
        synthese, waarom = "", ""
        for raw in out.splitlines():
            line = raw.strip().lstrip("*-•# ").strip()
            low = line.lower()
            if low.startswith("synthese") and ":" in line:
                synthese = line.split(":", 1)[1].strip().strip("* ").strip()
            elif low.startswith("waarom") and ":" in line:
                waarom = line.split(":", 1)[1].strip().strip("* ").strip()
        if not synthese:
            return {"error": "onverstaanbaar antwoord (fail-closed)"}
        return {"synthese": synthese[:240], "waarom": waarom[:240]}
