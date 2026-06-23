"""Ingestie van mens-gecureerde insights in de kennislaag (NotesStore).

Een eerste, gecontroleerde ingest-proces — de voorloper van een ingestie-rol: schrijf
voorgevormde Insight-kaartjes in de notes-store, dedup op id, en leg de expliciete links
in een tweede pass via de keystone (notes.link, gevalideerd). Geen LLM, geen netwerk.

Kaartjes komen binnen op GroundingStatus.UNRESOLVED (mens-voorstel); promotie blijft een
latere, bewuste stap.
"""
from __future__ import annotations

from nooch_village.insight import Insight


def ingest_insights(notes, items: list[dict]) -> dict:
    """Voeg mens-gecureerde insights toe aan de notes-store.

    Dedup op id (bestaat al → overslaan, geen overschrijven). Links worden in een tweede
    pass gelegd via notes.link, dus gevalideerd: beide kaartjes moeten bestaan, anders
    wordt de link stil overgeslagen. Geeft {'added': [...], 'skipped': [...], 'linked': int}.
    """
    added: list[str] = []
    skipped: list[str] = []
    for it in items:
        if notes.get(it["id"]) is not None:
            skipped.append(it["id"])
            continue
        notes.add(Insight(
            id=it["id"],
            claim=it["claim"],
            source=it.get("source", ""),
            source_date=it.get("source_date"),
            tags=list(it.get("tags", [])),
        ))
        added.append(it["id"])

    linked = 0
    for it in items:
        for target in it.get("links_to", []):
            if notes.link(it["id"], target) is not None:
                linked += 1

    return {"added": added, "skipped": skipped, "linked": linked}
