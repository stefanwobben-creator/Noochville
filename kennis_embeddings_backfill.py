#!/usr/bin/env python3
"""kennis_embeddings_backfill — vul de semantische index (founder 23 jul).

Embeddt alle actieve laag-1 kaartjes (notes.json) in kennis_embeddings.json, zodat de voorkant-poort
parafrase-duplicaten kan vinden (biobased-drieling etc.). Idempotent en goedkoop bij re-runs: een
kaartje waarvan de claim-hash al klopt wordt overgeslagen; alleen nieuwe of gewijzigde claims worden
(opnieuw) geëmbed. Gearchiveerde kaartjes worden niet geïndexeerd en uit de index verwijderd.

Batched (één API-call per BATCH kaartjes) en fail-soft: mislukt een batch (geen sleutel, quota), dan
slaat hij die over en gaat door — draai het script later nog eens om de rest te vullen.

Draaien op de server ALS DE APP-GEBRUIKER (rechten + venv + GEMINI_API_KEY uit de env):
    cd /opt/noochville && sudo -u nooch --preserve-env=GEMINI_API_KEY ./venv/bin/python kennis_embeddings_backfill.py
Herhaalbaar; veilig om wekelijks te draaien (indexeert nieuw bijgekomen kaartjes).
"""
import os
import sys

from nooch_village.notes_store import NotesStore
from nooch_village.kennis_embeddings import EmbeddingStore, embed_many, _hash

DATA = os.getenv("NOOCH_DATA_DIR", "data")
BATCH = int(os.getenv("EMBED_BATCH", "64"))


def main() -> int:
    notes = NotesStore(f"{DATA}/notes.json")
    store = EmbeddingStore(f"{DATA}/kennis_embeddings.json")

    actief = [a for a in notes.all() if not a.archived]
    actieve_ids = {a.id for a in actief}

    # Gearchiveerde/verdwenen kaartjes uit de index halen (houd hem schoon).
    weg = [nid for nid, _ in list(store.items()) if nid not in actieve_ids]
    for nid in weg:
        store.drop(nid)

    # Alleen nieuwe of gewijzigde claims (hash-vergelijk) opnieuw embedden.
    todo = [a for a in actief if store.hash_of(a.id) != _hash(a.claim)]
    print(f"kaartjes actief: {len(actief)} | al geïndexeerd: {len(actief) - len(todo)} | "
          f"te (her)indexeren: {len(todo)} | uit index verwijderd: {len(weg)}")

    gedaan = 0
    mislukt = 0
    for i in range(0, len(todo), BATCH):
        groep = todo[i:i + BATCH]
        vecs = embed_many([a.claim for a in groep])
        for a, v in zip(groep, vecs):
            if v:
                store.upsert(a.id, a.claim, v)
                gedaan += 1
            else:
                mislukt += 1
        store.save()                       # per batch bewaren → veilig af te breken en te hervatten
        print(f"  batch {i // BATCH + 1}: +{sum(1 for v in vecs if v)} geëmbed "
              f"(totaal {gedaan}/{len(todo)})")

    print(f"\nKlaar. Geïndexeerd: {gedaan} | mislukt (geen embedding): {mislukt} | "
          f"index-omvang nu: {len(store)}.")
    if mislukt and gedaan == 0:
        print("⚠ Niets geëmbed — staat GEMINI_API_KEY in de env? (fail-soft: de poort blijft lexicaal.)",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
