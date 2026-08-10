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
        out = reason(prompt, call_site="skill_synthesize",
                     ladder=_hoog_inzet_ladder("skill_synthesize"))
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


def _hoog_inzet_ladder(call_site: str):
    """De dorpsbrede hoog-inzet-ladder voor deze call-site.

    Bewust ZONDER persona-override: een skill kent zijn rol niet (de context die hij krijgt draagt
    geen role_id), dus die keuze is hier niet te maken. De persona-override werkt wél op de
    rol-gebonden sites (plan_checklist, einddocument, noochie_weigh_in) via `_persona_ladder`.

    Fail-soft: gaat de keuze stuk, dan de dorpsladder — een ladder mag een call nooit blokkeren."""
    try:
        from nooch_village.llm_keuze import ladder_voor
        return ladder_voor(call_site)
    except Exception:                                # noqa: BLE001
        return None
