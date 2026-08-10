"""Skill: schrijft het dagelijkse dorpsbulletin via LLM op basis van village-events."""
from __future__ import annotations
import logging, os
from datetime import date
from nooch_village.skills import Skill

log = logging.getLogger(__name__)


class BulletinSchrijvenSkill(Skill):
    name = "bulletin_schrijven"
    cost = "free"
    side_effect_free = False
    description = "Schrijft het dagelijkse dorpsbulletin via LLM op basis van village-events."

    def run(self, payload: dict, context) -> dict:
        events: list[dict] = payload.get("events", [])
        datum: str = payload.get("datum", date.today().isoformat())
        field_note: str = payload.get("field_note", "")

        if events:
            event_regels = "\n".join(
                f"- {e.get('name', '?')} (door: {e.get('by', '?')})"
                + (f" — {e['note']}" if e.get("note") else "")
                for e in events
            )
        else:
            event_regels = "(geen events vandaag)"

        if field_note:
            fn_sectie = f"\nVeld-notitie van vandaag:\n{field_note}\n"
        else:
            fn_sectie = "\n(Geen veld-notitie beschikbaar vandaag.)\n"

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
            f"Write only what you actually see in the events or the field note, invent nothing. "
            f"Start with '# Village bulletin {datum}'."
        )

        from nooch_village.llm import reason as llm_reason
        content = llm_reason(prompt, call_site="skill_bulletin", ladder=_hoog_inzet_ladder("skill_bulletin"))
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
