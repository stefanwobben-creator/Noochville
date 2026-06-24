"""CurateSkill — de kwaliteitspoort van de kennislaag.

Wikkelt de curate-engine in een skill: fuzzy input → atomaire, Engelse, complete kaart-dicts,
met links naar bestaande kaartjes. De Librarian (domein-eigenaar) gebruikt dit als enige
schrijfweg naar de NotesStore.
"""
from __future__ import annotations
import datetime
from nooch_village.skills import Skill
from nooch_village.curate import curate


class CurateSkill(Skill):
    name = "curate"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    description = (
        "Cureert fuzzy input tot atomaire, Engelse insight-kaartjes (Engels-only, één claim "
        "per kaartje, compleet, gelinkt). De kwaliteitspoort van de kennislaag."
    )

    def run(self, payload: dict, context) -> dict:
        fuzzy = (payload.get("fuzzy") or payload.get("text") or "").strip()
        if not fuzzy:
            return {"cards": []}
        source = payload.get("source", "curator")
        source_date = payload.get("source_date") or datetime.date.today().isoformat()
        notes = getattr(context, "notes", None)
        existing = [n.id for n in notes.all()][:60] if notes is not None else []
        cards = curate(fuzzy, source=source, source_date=source_date, existing_ids=existing)
        return {"cards": cards}
