from __future__ import annotations
import os, json
from datetime import datetime
from nooch_village.skills import Skill
from nooch_village.llm import reason

MISSION = (
    "Nooch.earth bewijst dat ethisch en duurzaam ondernemen winstgevend is. "
    "Kernwaarden: meliorisme (altijd beter), ubuntu (succes samen met klant, producent, planeet), "
    "geen externaliteiten (geen plastic, geen leer, in Europa geproduceerd, op bestelling), transparantie. "
    "Doel: organische groei richting 1000 klanten per jaar via missie-gedreven keywords."
)


class FieldNoteSkill(Skill):
    name = "field_note"
    description = "Duidt de groei-data tegen de Nooch-missie en schrijft een Field Note. Senst verval."

    def run(self, payload: dict, context) -> dict:
        plausible = payload.get("plausible", {})
        trends = payload.get("trends", {})
        today = datetime.now().strftime("%Y-%m-%d")

        # --- tension-detectie: vergelijk bezoekers met de vorige puls ---
        visitors = self._visitors(plausible)
        baseline_path = os.path.join(context.data_dir, "last_pulse.json")
        last = json.load(open(baseline_path)) if os.path.exists(baseline_path) else {}
        last_visitors = last.get("visitors")
        tension, reason_txt = False, ""
        if visitors is not None and last_visitors:
            drop = (last_visitors - visitors) / last_visitors
            if drop >= 0.15:
                tension = True
                reason_txt = f"Bezoekers gedaald van {last_visitors} naar {visitors} ({drop:.0%})."
        if visitors is not None:
            json.dump({"visitors": visitors, "date": today}, open(baseline_path, "w"))

        body = self._compose(plausible, trends, visitors, last_visitors, tension, reason_txt)

        out_dir = os.path.join(context.data_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"field_note_{today}.md")
        with open(path, "w") as f:
            f.write(body)
        return {"path": path, "tension": tension, "reason": reason_txt}

    # --- helpers ---
    def _visitors(self, plausible):
        try:
            return int(plausible["results"]["visitors"]["value"])
        except Exception:
            return None

    def _data_block(self, plausible, trends):
        return json.dumps({"plausible": plausible, "trends": trends}, ensure_ascii=False, indent=2)

    def _compose(self, plausible, trends, visitors, last_visitors, tension, reason_txt):
        today = datetime.now().strftime("%Y-%m-%d")
        # 1. Probeer LLM-redenering
        prompt = (
            f"Je bent de Growth Analyst van Nooch.earth. Missie:\n{MISSION}\n\n"
            f"Hier is de groei-data van vandaag (JSON):\n{self._data_block(plausible, trends)}\n\n"
            "Schrijf een korte Field Note in het Nederlands (max 180 woorden): wat valt op in het "
            "verkeer en de trends, wat betekent dit voor de missie-gedreven groei, en wat is de "
            "belangrijkste actie voor morgen. Nuchter, geen marketingtaal."
        )
        llm = reason(prompt)
        header = f"# Field Note {today}\n\n"
        if tension:
            header += f"> ⚠️ SPANNING: {reason_txt}\n\n"
        if llm:
            return header + llm + "\n"

        # 2. Deterministische terugval (werkt altijd, ook zonder LLM-key)
        lines = [header, "## Verkeer (Plausible)"]
        if "error" in plausible:
            lines.append(f"- Geen data: {plausible['error']}")
        else:
            lines.append(f"- Bezoekers (7d): {visitors if visitors is not None else 'onbekend'}"
                         + (f" (vorige puls: {last_visitors})" if last_visitors else ""))
        lines.append("\n## Trends")
        kw = (trends or {}).get("keywords", {})
        if not kw or "error" in (trends or {}):
            lines.append(f"- Geen trends-data: {(trends or {}).get('error', 'leeg')}")
        else:
            for k, v in kw.items():
                if "error" in v:
                    lines.append(f"- **{k}**: fout ({v['error']})")
                else:
                    rel = ", ".join(
                        r["query"] if isinstance(r, dict) else r
                        for r in v.get("top_related", [])
                    ) or "geen"
                    lines.append(f"- **{k}**: interesse {v.get('interest_latest')} ({v.get('direction')}); "
                                 f"opkomend: {rel}")
        lines.append("\n## Duiding")
        if tension:
            lines.append(f"- {reason_txt} Onderzoek welke missie-pagina terugloopt.")
        else:
            lines.append("- Geen alarmsignaal in het verkeer.")
        lines.append("- (Zet een LLM-key in .env voor een rijkere, missie-gedreven duiding.)")
        return "\n".join(lines) + "\n"
