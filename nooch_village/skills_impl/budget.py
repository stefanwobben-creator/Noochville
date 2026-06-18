from __future__ import annotations
import json, os
from nooch_village.skills import Skill


class BudgetSkill(Skill):
    name = "budget_adjust"
    cost = "free"
    side_effect_free = False
    description = "Past de begroting aan: echte, duurzame mutatie op data/budget.json."

    def run(self, payload: dict, context) -> dict:
        path = os.path.join(context.data_dir, "budget.json")
        budget = json.load(open(path)) if os.path.exists(path) else {"total_eur": 0.0, "lines": {}}
        line = payload["line"]
        delta = float(payload["delta_eur"])
        budget["lines"][line] = round(budget["lines"].get(line, 0.0) + delta, 2)
        budget["total_eur"] = round(sum(budget["lines"].values()), 2)
        json.dump(budget, open(path, "w"), indent=2, ensure_ascii=False)
        return {"line": line, "delta_eur": delta,
                "new_line_total": budget["lines"][line], "budget_total_eur": budget["total_eur"]}
