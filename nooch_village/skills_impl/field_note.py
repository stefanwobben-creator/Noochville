"""field_note — de groei-data duiden tegen de missie en de Field Note schrijven.

Periodiek (de website-watcher, elke ochtendpuls) — géén rugzak-skill. Live werd hij zevenmaal als
checklist-item gepland met een payload zonder data (null, of `{topic, content}`); elke run
overschreef de echte Field Note en de `pulse_raw` van die dag met niets. Sinds scope 57 is
`plausible` verplicht en levert data zonder `results` `no_data` op: er wordt dan niets geschreven.
"""
from __future__ import annotations
import os, json
from datetime import datetime
from nooch_village.skills import Skill
from nooch_village.llm import reason
from nooch_village.grounding import ground_field_note
from nooch_village.evidence_ledger import EvidenceLedger

MISSION = (
    "Nooch.earth bewijst dat ethisch en duurzaam ondernemen winstgevend is. "
    "Kernwaarden: meliorisme (altijd beter), ubuntu (succes samen met klant, producent, planeet), "
    "geen externaliteiten (geen plastic, geen leer, in Europa geproduceerd, op bestelling), transparantie. "
    "Doel: organische groei richting 1000 klanten per jaar via missie-gedreven keywords."
)


class FieldNoteSkill(Skill):
    name = "field_note"
    cost = "free"
    side_effect_free = False
    description = ("Interpret today's growth data (Plausible visitors, trends) against the Nooch "
                   "mission and write the Field Note to data/output/field_note_<date>.md; senses a "
                   "visitor drop of 15% or more against the previous pulse. Periodic: the website "
                   "watcher runs it each morning with real Plausible data.")
    input_schema = ("plausible: dict (required — the plausible_stats result with a 'results' block; "
                    "without it nothing is written); trends: dict (optional — the trends result); "
                    "prose: bool (optional, default true — false skips the model narrative and only "
                    "records the day's raw data and the tension check)")
    required_payload = ("plausible",)
    output_schema = ("path, text (the note), tension, reason, grounded, issues, prose | "
                     "no_data+reason (no results in the data) | error")

    def run(self, payload: dict, context) -> dict:
        p = payload or {}
        plausible = p.get("plausible") or {}
        trends = p.get("trends") or {}
        # `prose` poort de dure LLM-duiding. Standaard True (backward-compat); de puls zet 'm wekelijks.
        prose = p.get("prose", True)
        today = datetime.now().strftime("%Y-%m-%d")

        # GEEN DATA, GEEN NOTE. Een payload zonder `results` (een planner-aanroep met een thema, of
        # een Plausible-fout) heeft niets om te duiden; doorschrijven overschreef de echte dagnote.
        if not isinstance(plausible, dict) or not isinstance(plausible.get("results"), dict) \
                or not plausible.get("results"):
            fout = plausible.get("error") if isinstance(plausible, dict) else None
            return {"no_data": True, "path": None, "tension": False, "prose": bool(prose),
                    "reason": ("no Plausible results in the payload"
                               + (f" (source error: {str(fout)[:120]})" if fout else "")
                               + " — no Field Note written, nothing overwritten")}

        dd = getattr(context, "data_dir", ".") or "."
        # --- tension-detectie: vergelijk bezoekers met de vorige puls (ALTIJD, goedkoop, geen LLM) ---
        visitors = self._visitors(plausible)
        baseline_path = os.path.join(dd, "last_pulse.json")
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

        # --- ruwe data ALTIJD wegschrijven (goedkoop, bouwt dagelijks historie op) ---
        out_dir = os.path.join(dd, "output")
        os.makedirs(out_dir, exist_ok=True)
        raw_path = os.path.join(out_dir, f"pulse_raw_{today}.json")
        with open(raw_path, "w") as f:
            json.dump({"plausible": plausible, "trends": trends}, f, ensure_ascii=False, indent=2)

        # --- de dure LLM-duiding (proza) is gepoort: standaard wekelijks, niet elke dag ---
        if not prose:
            return {"path": None, "tension": tension, "reason": reason_txt,
                    "grounded": None, "issues": [], "prose": False}

        body = self._compose(plausible, trends, visitors, last_visitors, tension, reason_txt, context)

        # Grondings-poort (De Kroniek): een LLM-duiding mag geen cijfers/datums verzinnen die niet uit de
        # data volgen. Ongegrond → MARKEREN i.p.v. schoon publiceren (de mens ziet dat 't onbetrouwbaar is).
        issues = ground_field_note(body, plausible, today)
        if issues:
            body = ("> ⚠️ ONGEGROND — deze Field Note bevat data die niet uit de bron volgt:\n"
                    + "".join(f">  - {i}\n" for i in issues) + ">\n\n" + body)

        path = os.path.join(out_dir, f"field_note_{today}.md")
        with open(path, "w") as f:
            f.write(body)

        # Onthouden: leg de grondings-uitkomst vast in de Kroniek (fail-safe — nooit de puls breken).
        try:
            led = EvidenceLedger(os.path.join(dd, "evidence_ledger.jsonl"))
            led.record(role_id="website_watcher", skill="field_note", query=today, source="grounding",
                       status="fout" if issues else "bevestigd", result_ref=os.path.basename(path),
                       meta={"issues": issues} if issues else None)
        except Exception:
            pass

        # `text` = de note zelf: het pad alleen is geen inhoud (de wall toonde een bestandsnaam).
        return {"path": path, "text": body, "tension": tension, "reason": reason_txt,
                "grounded": not issues, "issues": issues, "prose": True}

    # --- helpers ---
    def _visitors(self, plausible):
        try:
            return int(plausible["results"]["visitors"]["value"])
        except Exception:
            return None

    def _data_block(self, plausible, trends):
        return json.dumps({"plausible": plausible, "trends": trends}, ensure_ascii=False, indent=2)

    def _compose(self, plausible, trends, visitors, last_visitors, tension, reason_txt, context=None):
        today = datetime.now().strftime("%Y-%m-%d")
        # 1. Probeer LLM-redenering
        prompt = (
            f"You are Corry Coconut, website watcher of Nooch.earth. Mission:\n{MISSION}\n\n"
            f"Here is today's growth data (JSON):\n{self._data_block(plausible, trends)}\n\n"
            "Write a Field Note in English (max 250 words). Voice: sober and factual, no marketing "
            "language, no exaggeration. Interpretation is allowed, but only where it follows "
            "directly from the data. Name only fields that are actually in the data; leave empty "
            "fields out and invent nothing.\n\n"
            "Cover three points:\n"
            "(1) What stands out in the traffic and the trends. Weave in the concrete data: "
            "visitors, average visit duration, busiest pages, main traffic sources, strongest "
            "countries, notable UTM or campaign sources, and the rising or falling search terms "
            "with their interest values.\n"
            "(2) What this means for mission-driven growth — grounded in the numbers from point 1.\n"
            "(3) The most important action for tomorrow."
        )
        # Grounding-call: de Field Note is de stem van de rol die hem schrijft, dus zijn persona mag
        # het model kiezen. `context` komt sinds scope 57 als parameter mee: hiervoor verwees deze
        # regel naar een naam die hier niet bestond (NameError, stil gevangen), dus de ladder-keuze
        # draaide nooit en de note kwam altijd van de dorpsladder.
        _ladder = None
        try:
            from nooch_village.llm_keuze import llm_voorkeur
            _ladder = llm_voorkeur(context, getattr(context, "field_note_role", "analyst"),
                                   "skill_field_note")
        except Exception:
            pass
        llm = reason(prompt, call_site="skill_field_note", ladder=_ladder)
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
