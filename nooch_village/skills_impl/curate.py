"""CurateSkill — de kwaliteitspoort van de kennislaag.

Wikkelt de curate-engine in een skill: fuzzy input → atomaire, Engelse, complete kaart-dicts,
met links naar bestaande kaartjes. De Librarian (domein-eigenaar) gebruikt dit als enige
schrijfweg naar de NotesStore.

SCOPE 57 (skill-review 12-09-2026): zonder input_schema raadde de planner de sleutel ('input',
'data', 'context') en de skill las alleen `fuzzy`/`text` → 6 van 10 runs leeg; en drie oorzaken
(geen model, onparseerbaar, niets geldig) gaven dezelfde lege lijst. Nu: de sleutels als aliassen,
een schema, en `error` / `no_data` / kaarten als drie verschillende antwoorden.
"""
from __future__ import annotations
import datetime
from nooch_village.skills import Skill
from nooch_village.curate import curate_uitkomst

# De payload-sleutels die als 'de ruwe tekst' gelden — de eerste is de afspraak, de rest zijn de
# namen die de planner live koos. Een lijst (claims) wordt regel-voor-regel één tekst.
_INVOER = ("fuzzy", "text", "input", "data")


def _ruwe_tekst(payload: dict) -> str:
    for k in _INVOER:
        v = (payload or {}).get(k)
        if isinstance(v, (list, tuple)):
            v = "\n".join(str(x) for x in v if str(x).strip())
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


class CurateSkill(Skill):
    name = "curate"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    description = (
        "Curate rough input (a finding, a claim, a paragraph, any language) into atomic English "
        "insight cards: one claim per card, with grounds, linked to existing cards. The quality "
        "gate of the knowledge layer; the Librarian writes the cards."
    )
    input_schema = ("fuzzy: str (required — the raw text or a list of claims to curate; 'text', "
                    "'input' and 'data' are accepted as the same field); "
                    "source: str (optional — where it came from, default 'curator'); "
                    "source_date: str (optional — ISO date, default today)")
    required_payload = (_INVOER,)          # of-of: één van de vier sleutels
    output_schema = ("cards: list of {id, claim, grounds, source, source_date, status, evidence_type, "
                     "concept_id, tags, links_to} | error (no model / not JSON) | no_data+reason "
                     "(no complete card)")

    def run(self, payload: dict, context) -> dict:
        fuzzy = _ruwe_tekst(payload or {})
        if not fuzzy:
            return {"error": "no input: 'fuzzy' (or text/input/data) is required — the raw text to curate",
                    "cards": []}
        source = (payload or {}).get("source") or "curator"
        source_date = (payload or {}).get("source_date") or datetime.date.today().isoformat()
        notes = getattr(context, "notes", None) if context is not None else None
        existing = [n.id for n in notes.all()][:60] if notes is not None else []
        return curate_uitkomst(fuzzy, source=source, source_date=source_date, existing_ids=existing)
