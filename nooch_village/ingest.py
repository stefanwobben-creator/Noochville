"""Ingestie van mens-gecureerde insights in de kennislaag (NotesStore).

Een eerste, gecontroleerde ingest-proces — de voorloper van een ingestie-rol: schrijf
voorgevormde Insight-kaartjes in de notes-store, dedup op id, en leg de expliciete links
in een tweede pass via de keystone (notes.link, gevalideerd). Geen LLM, geen netwerk.

Kaartjes komen binnen op GroundingStatus.UNRESOLVED (mens-voorstel); promotie blijft een
latere, bewuste stap.
"""
from __future__ import annotations

from nooch_village.insight import Insight

# Velden die een ingest-item rechtstreeks op een Insight mag zetten. links_to staat hier
# bewust NIET in: links gaan altijd via notes.link (gevalideerd) in de tweede pass.
_INGEST_FIELDS = set(Insight.model_fields) - {"links_to", "created_at", "last_updated_at"}


def ingest_insights(notes, items: list[dict]) -> dict:
    """Voeg mens-gecureerde insights toe aan de notes-store.

    Elk item is een dict met minstens id/claim/source; verdere Insight-velden (status,
    grounds, evidence_type, source_date, tags, word, …) worden doorgegeven als ze in
    _INGEST_FIELDS staan. Onbekende sleutels worden genegeerd. Dedup op id (bestaat al →
    overslaan, geen overschrijven). Links worden in een tweede pass gelegd via notes.link,
    dus gevalideerd: beide kaartjes moeten bestaan, anders wordt de link stil overgeslagen.
    Geeft {'added': [...], 'skipped': [...], 'linked': int}.
    """
    added: list[str] = []
    skipped: list[str] = []
    for it in items:
        if notes.get(it["id"]) is not None:
            skipped.append(it["id"])
            continue
        fields = {k: v for k, v in it.items() if k in _INGEST_FIELDS}
        notes.add(Insight(**fields))
        added.append(it["id"])

    linked = 0
    for it in items:
        for target in it.get("links_to", []):
            if notes.link(it["id"], target) is not None:
                linked += 1

    return {"added": added, "skipped": skipped, "linked": linked}
