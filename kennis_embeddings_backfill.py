#!/usr/bin/env python3
"""kennis_embeddings_backfill — vul de semantische index (founder 23 jul).

Dunne wrapper om nooch_village.kennis_embeddings.index_backfill: embedt alle actieve laag-1 kaartjes
(notes.json) in kennis_embeddings.json. Getemporiseerd onder de gratis-tier-limiet (wacht + herprobeer
bij 429) en herstartbaar (idempotent op claim-hash). Voor de nachtelijke cyclus draai je kennis_onderhoud.py,
dat deze backfill als eerste fase meeneemt; dit los script blijft handig voor een gerichte her-indexatie.

Draaien op de server ALS DE APP-GEBRUIKER, met de .env geladen (sleutel + modelnaam):
    cd /opt/noochville && sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_embeddings_backfill.py'
"""
import os
import sys

from nooch_village.notes_store import NotesStore
from nooch_village.kennis_embeddings import EmbeddingStore, index_backfill

DATA = os.getenv("NOOCH_DATA_DIR", "data")


def main() -> int:
    notes = NotesStore(f"{DATA}/notes.json")
    store = EmbeddingStore(f"{DATA}/kennis_embeddings.json")
    stats = index_backfill(notes, store, log=print)
    print(f"\nKlaar. Geïndexeerd: {stats['geindexeerd']} | mislukt: {stats['mislukt']} | "
          f"uit index verwijderd: {stats['verwijderd']} | index-omvang nu: {stats['index_omvang']}.")
    if stats["mislukt"] and stats["geindexeerd"] == 0:
        print("⚠ Niets geëmbed — staat GEMINI_API_KEY (en LLM_EMBED_MODEL) in de env?", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
