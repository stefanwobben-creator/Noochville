from __future__ import annotations
import re, json
from nooch_village.skills import Skill
from nooch_village.llm import reason
from nooch_village.skills_impl.field_note import MISSION

# Heuristiek (werkt zonder LLM-key): transparante regels i.p.v. een black box.
MISSION_CORE = ["plasticvrij", "plastic free", "zonder plastic", "plantbased",
                "plant-based", "duurzaam", "duurzame", "circulair", "ethisch",
                "op bestelling", "made in europe", "europa"]
RISK = {
    "vegan": "vegan wordt vaak met plastic (PU/PVC) geassocieerd; risico op off-mission publiek",
    "goedkoop": "goedkoop trekt prijsvechters; botst met de eerlijke prijs",
    "cheap": "cheap trekt prijsvechters; botst met de eerlijke prijs",
    "leer": "leer is door de missie uitgesloten",
    "leather": "leather is door de missie uitgesloten",
}
FORBIDDEN_CLAIM = ["biologisch afbreekbaar", "100%", "co2-neutraal", "co2 neutraal", "klimaatneutraal"]


class LibraryLookupSkill(Skill):
    name = "library_lookup"
    description = "Leest de status van een woord uit de bibliotheek (read-only, voor iedereen)."

    def run(self, payload: dict, context) -> dict:
        word = payload["word"]
        e = context.library.status(word)
        return {"word": word,
                "status": e["status"] if e else "unknown",
                "rationale": e.get("rationale", "") if e else ""}


class KeywordReviewSkill(Skill):
    name = "keyword_review"
    description = "Beoordeelt een kandidaat-woord tegen de missie (LLM of heuristiek) + vraag-bewijs."

    def run(self, payload: dict, context) -> dict:
        word = payload["word"]
        demand = payload.get("demand", {})
        existing = context.library.status(word)
        if existing and existing["status"] in ("approved", "forbidden", "avoid"):
            return {"word": word, "decision": "known", "status": existing["status"],
                    "reason": "al vastgelegd in de bibliotheek"}

        h_decision, h_reason = self._heuristic(word, demand)
        llm = self._llm(word, demand)
        decision, reason_txt, basis = (llm[0], llm[1], "llm") if llm else (h_decision, h_reason, "heuristic")
        return {"word": word, "decision": decision, "reason": reason_txt, "basis": basis,
                "demand": demand, "alignment_heuristic": h_decision}

    def _has_demand(self, demand: dict) -> bool:
        if not demand:
            return False
        return demand.get("signal") in ("rising", "positive") or (demand.get("interest", 0) or 0) > 10

    def _heuristic(self, word: str, demand: dict):
        w = word.lower()
        for term in FORBIDDEN_CLAIM:
            if term in w:
                return "reject", f"bevat een onbewezen claim ('{term}')"
        for term, why in RISK.items():
            if re.search(rf"\b{re.escape(term)}", w):
                return "escalate", why
        core = any(c in w for c in MISSION_CORE)
        if core and self._has_demand(demand):
            return "approve", "missie-kern en er is aantoonbare vraag"
        if core:
            return "escalate", "past bij de missie maar geen aangetoonde vraag"
        return "escalate", "geen duidelijk missie-signaal; menselijk oordeel gevraagd"

    def _llm(self, word: str, demand: dict):
        prompt = (
            f"Je bent de Librarian van Nooch.earth, hoeder van de goedgekeurde woordenschat.\n"
            f"Missie:\n{MISSION}\n\n"
            f"Kandidaat-woord: '{word}'. Vraag-signaal: {json.dumps(demand, ensure_ascii=False)}.\n"
            "Mag dit woord veilig in content gebruikt worden, gezien de missie (geen plastic, "
            "geen leer, eerlijke prijs, transparantie)? Let op verborgen conflicten, bijvoorbeeld "
            "dat 'vegan' vaak met plastic geassocieerd wordt.\n"
            "Antwoord op EXACT één regel in dit formaat:\n"
            "DECISION: approve|reject|escalate | REASON: <korte reden>"
        )
        out = reason(prompt)
        if not out:
            return None
        m = re.search(r"DECISION:\s*(approve|reject|escalate)\s*\|\s*REASON:\s*(.+)", out, re.I | re.S)
        if not m:
            return None
        return (m.group(1).lower(), m.group(2).strip())
