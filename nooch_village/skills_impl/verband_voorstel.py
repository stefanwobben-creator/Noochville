from __future__ import annotations
import re
from nooch_village.skills import Skill


class VerbandVoorstelSkill(Skill):
    name = "verband_voorstel"
    cost = "free"
    description = "Beoordeelt of twee kaarten een zinvol verband hebben en stelt een verbindende claim voor."

    def run(self, payload: dict, context) -> dict:
        a = payload.get("kaart_a", {})
        b = payload.get("kaart_b", {})
        voorstel = self._llm(a, b)
        if voorstel is None:
            return {"verband": False}
        return {"verband": True, "claim": voorstel}

    def _llm(self, a: dict, b: dict) -> str | None:
        from nooch_village.llm import reason
        prompt = (
            "Je beoordeelt of twee kennis-kaarten over duurzame schoenen een zinvol, "
            "niet-triviaal inhoudelijk verband hebben. Een gedeeld woord is GEEN verband; "
            "er moet een echte gedachte zijn die de twee verbindt. Ook GEEN verband: "
            "twee kaarten die hetzelfde zeggen, of die allebei een lege of negatieve "
            "uitkomst delen (zoals 'beide vonden geen onderbouwing'). Een verband moet "
            "twee VERSCHILLENDE inhoudelijke ideeen aan elkaar knopen, niet constateren "
            "dat twee kaarten dezelfde of geen inhoud hebben.\n\n"
            f"KAART A (over '{a.get('word', '')}'): {a.get('claim', '')}\n"
            f"KAART B (over '{b.get('word', '')}'): {b.get('claim', '')}\n\n"
            "Antwoord op EXACT één regel in dit formaat:\n"
            "VERBAND: ja|nee | CLAIM: <één zin die de twee verbindt, alleen bij ja>\n"
            "Bij twijfel of geen echt verband: VERBAND: nee"
        )
        out = reason(prompt)
        if not out:
            return None
        m = re.search(r"VERBAND:\s*(ja|nee)\s*\|\s*CLAIM:\s*(.+)", out, re.IGNORECASE)
        if not m:
            return None
        if m.group(1).lower() != "ja":
            return None
        claim = m.group(2).strip()
        return claim or None
