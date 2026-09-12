"""Skill: schrijft het dagelijkse dorpsbulletin via LLM op basis van village-events.

Periodiek (Noochie, op `dag_eindigt`) — géén rugzak-skill. Live (2d5e7fac383b) plande een rol hem
vijfmaal als checklist-item met een payload zonder events; elke run schreef "(geen events vandaag)"
over het echte bulletin van die dag heen. Sinds scope 57 zijn `events` verplicht en levert een lege
dag `no_data` op: er wordt dan niets geschreven en niets overschreven.
"""
from __future__ import annotations
import logging, os
from datetime import date
from nooch_village.skills import Skill
from nooch_village.llm_keuze import skill_ladder

log = logging.getLogger(__name__)

# Eén regel per event in de prompt; een dag met honderden events (een radar-storm) hoort niet
# integraal in één call — de eerste zijn de dag-opening en de puls, de rest is herhaling.
_MAX_EVENTS = 80


class BulletinSchrijvenSkill(Skill):
    name = "bulletin_schrijven"
    cost = "free"
    side_effect_free = False
    description = ("Write today's village bulletin (four fixed headings) from the day's village "
                   "events and the Field Note, to data/bulletins/bulletin_<date>.md. Periodic: "
                   "Noochie runs it at the end of the day; it needs real events, not a topic.")
    input_schema = ("events: list of {name: str, by: str, note?: str} (required — the events of the "
                    "day as collected by Noochie; an empty list writes nothing); "
                    "datum: str (optional — ISO date, default today); "
                    "field_note: str (optional — the Field Note text of the day)")
    required_payload = ("events",)
    output_schema = "path, datum, event_count, text | no_data+reason (empty day) | error (no model)"

    def run(self, payload: dict, context) -> dict:
        p = payload or {}
        events = p.get("events") or []
        events = [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []
        datum: str = str(p.get("datum") or date.today().isoformat())
        field_note: str = str(p.get("field_note") or "")

        if not events:
            # Geen events = geen dag om over te schrijven. Bewust `no_data` en niet een leeg
            # bulletin: dat laatste overschreef live het echte dagbestand (zie moduledocstring).
            return {"no_data": True, "datum": datum, "event_count": 0,
                    "reason": "no village events for this day — no bulletin written, nothing overwritten"}

        event_regels = "\n".join(
            f"- {e.get('name', '?')} (by: {e.get('by', '?')})"
            + (f" — {e['note']}" if e.get("note") else "")
            for e in events[:_MAX_EVENTS]
        )
        if len(events) > _MAX_EVENTS:
            event_regels += f"\n- … and {len(events) - _MAX_EVENTS} more events not listed"

        if field_note:
            fn_sectie = f"\nToday's Field Note:\n{field_note}\n"
        else:
            fn_sectie = "\n(No Field Note available today.)\n"

        prompt = (
            f"You are Noochie, the dream keeper and bridge of NoochVille (ENFP). "
            f"Warm, enthusiastic and mission-driven.\n"
            f"Date: {datum}\n\n"
            f"Events that happened in the village today:\n{event_regels}\n"
            f"{fn_sectie}\n"
            f"Write a short daily village bulletin in English with exactly these four headings "
            f"(markdown ## level):\n"
            f"## What I saw today\n"
            f"## Who was active\n"
            f"## What I notice\n"
            f"## See you tomorrow\n\n"
            f"Warm in tone, informative, max 200 words in total. "
            f"Write only what you actually see in the events or the field note, invent nothing; "
            f"if something is unknown, say so. "
            f"Start with '# Village bulletin {datum}'."
        )

        from nooch_village.llm import reason as llm_reason
        content = llm_reason(prompt, call_site="skill_bulletin", max_tokens=700,
                             ladder=skill_ladder("skill_bulletin"))
        if content is None:
            log.warning("BulletinSchrijvenSkill: LLM niet beschikbaar — bulletin overgeslagen")
            return {"error": "llm_unavailable"}

        bulletins_dir = os.path.join(getattr(context, "data_dir", ".") or ".", "bulletins")
        os.makedirs(bulletins_dir, exist_ok=True)
        path = os.path.join(bulletins_dir, f"bulletin_{datum}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        log.info("📋 bulletin geschreven: %s", path)
        # `text` = het bulletin zelf: het pad alleen is geen inhoud (de wall toonde een bestandsnaam).
        return {"path": path, "datum": datum, "event_count": len(events), "text": content}
