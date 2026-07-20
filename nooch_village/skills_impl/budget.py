from __future__ import annotations
import json, os
from nooch_village.skills import Skill


class BudgetSkill(Skill):
    name = "budget_adjust"
    cost = "free"
    side_effect_free = False
    description = "Past de begroting aan: echte, duurzame mutatie op data/budget.json."
    # Contract vóór een SIDE-EFFECT (schrijft budget.json): de planner weigert een item zonder
    # 'line' of 'delta_eur', zodat een halve payload niet live op de boekhouding crasht.
    required_payload = ("line", "delta_eur")
    input_schema = "line: str (verplicht — begrotingsregel); delta_eur: getal (verplicht — mutatie)"

    def run(self, payload: dict, context) -> dict:
        line = (payload or {}).get("line")
        raw_delta = (payload or {}).get("delta_eur")
        if not line or raw_delta in (None, ""):
            return {"error": "ontbrekende parameter: 'line' en 'delta_eur' zijn beide verplicht"}
        try:
            delta = float(raw_delta)
        except (TypeError, ValueError):
            return {"error": f"'delta_eur' is geen getal: {raw_delta!r}"}
        path = os.path.join(context.data_dir, "budget.json")
        budget = json.load(open(path)) if os.path.exists(path) else {"total_eur": 0.0, "lines": {}}
        budget["lines"][line] = round(budget["lines"].get(line, 0.0) + delta, 2)
        budget["total_eur"] = round(sum(budget["lines"].values()), 2)
        json.dump(budget, open(path, "w"), indent=2, ensure_ascii=False)
        return {"line": line, "delta_eur": delta,
                "new_line_total": budget["lines"][line], "budget_total_eur": budget["total_eur"]}
