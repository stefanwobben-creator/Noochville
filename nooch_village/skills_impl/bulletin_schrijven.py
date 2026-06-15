"""Skill: schrijft het dagelijkse dorpsbulletin via LLM op basis van village-events."""
from __future__ import annotations
import logging, os
from datetime import date
from nooch_village.skills import Skill

log = logging.getLogger(__name__)


class BulletinSchrijvenSkill(Skill):
    name = "bulletin_schrijven"
    description = "Schrijft het dagelijkse dorpsbulletin via LLM op basis van village-events."

    def run(self, payload: dict, context) -> dict:
        events: list[dict] = payload.get("events", [])
        datum: str = payload.get("datum", date.today().isoformat())

        if events:
            event_regels = "\n".join(
                f"- {e.get('name', '?')} (door: {e.get('by', '?')})"
                + (f" — {e['note']}" if e.get("note") else "")
                for e in events
            )
        else:
            event_regels = "(geen events vandaag)"

        prompt = (
            f"Je bent Ronnie, de warmhartige dorpschroniqueur van NoochVille (ESFJ).\n"
            f"Datum: {datum}\n\n"
            f"Events die vandaag plaatsvonden in het dorp:\n{event_regels}\n\n"
            f"Schrijf een kort dagelijks dorpsbulletin met precies deze vier koppen "
            f"(markdown ## niveau):\n"
            f"## Wat ik vandaag zag\n"
            f"## Wie was actief\n"
            f"## Wat ik signaleer\n"
            f"## Tot morgen\n\n"
            f"Warm van toon, informatief, maximaal 200 woorden totaal. "
            f"Start met '# Dorpsbulletin {datum}'."
        )

        from nooch_village.llm import reason as llm_reason
        content = llm_reason(prompt)
        if content is None:
            log.warning("BulletinSchrijvenSkill: LLM niet beschikbaar — bulletin overgeslagen")
            return {"error": "llm_unavailable"}

        bulletins_dir = os.path.join(context.data_dir, "bulletins")
        os.makedirs(bulletins_dir, exist_ok=True)
        path = os.path.join(bulletins_dir, f"bulletin_{datum}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        log.info("📋 bulletin geschreven: %s", path)
        return {"path": path, "datum": datum, "event_count": len(events)}
