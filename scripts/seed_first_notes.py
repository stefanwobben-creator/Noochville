#!/usr/bin/env python3
"""Zaai de eerste zes permanente notes in data/notes.json.

Idempotent: bestaande notes worden overgeslagen.

Gebruik:
  python scripts/seed_first_notes.py
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nooch_village.permanent_note import PermanentNote
from nooch_village.notes_store import NotesStore

NOTES = [
    PermanentNote(
        id="vegan_sneakers_zijn_plastic",
        claim="De meeste vegan sneakers zijn gemaakt van plastic, niet van plantaardige of natuurlijke materialen.",
        source="Vegan sneakers: what they are and what's inside (nooch.earth)",
        source_date=None,
        links_to=["vegan_materialen_opsomming", "vegan_betekenis_correctie"],
        tags=[],
    ),
    PermanentNote(
        id="vegan_materialen_opsomming",
        claim="Een typische vegan sneaker bevat PU-leer of polyester voor de bovenkant, EVA-schuim voor de zool, nylon stiksels en synthetische lijm.",
        source="Vegan sneakers: what they are and what's inside (nooch.earth)",
        source_date=None,
        links_to=["vegan_sneakers_zijn_plastic", "vegan_olie_per_paar"],
        tags=[],
    ),
    PermanentNote(
        id="vegan_betekenis_correctie",
        claim="Vegan betekent zonder dierlijke materialen, niet zonder plastic.",
        source="Vegan sneakers: what they are and what's inside (nooch.earth)",
        source_date=None,
        links_to=["vegan_sneakers_zijn_plastic"],
        tags=[],
    ),
    PermanentNote(
        id="vegan_olie_per_paar",
        claim="Een paar vegan sneakers bevat ongeveer drie kwart liter aardolie.",
        source="Vegan sneakers: what they are and what's inside (nooch.earth)",
        source_date=None,
        links_to=["vegan_materialen_opsomming"],
        tags=[],
    ),
    PermanentNote(
        id="nooch_plant_based_keuze",
        claim="Nooch koos voor plant-based ontwerp in plaats van vegan-zonder-plastic; acht planten leveren de materialen voor één Nooch-sneaker.",
        source="Vegan sneakers: what they are and what's inside (nooch.earth)",
        source_date=None,
        links_to=["vegan_sneakers_zijn_plastic", "vegan_betekenis_correctie"],
        tags=[],
    ),
    PermanentNote(
        id="mother_earth_ceo_69pct",
        claim="Voor 69% van Nooch-klanten is bewustzijn over duurzaamheid een doorslaggevende aankoopreden.",
        source="Customer Insights deck (oktober 2025)",
        source_date="2025-10-01",
        links_to=["nooch_plant_based_keuze"],
        tags=[],
    ),
]


def seed() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    store = NotesStore(path=os.path.join(root, "data", "notes.json"))
    for note in NOTES:
        try:
            store.add(note)
            print(f"Toegevoegd: {note.id}")
        except ValueError:
            print(f"Overgeslagen (bestaat al): {note.id}")


if __name__ == "__main__":
    seed()
