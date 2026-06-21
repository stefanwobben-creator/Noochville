#!/usr/bin/env python3
"""Koppel library-keywords aan hun lexicon-concept (deterministisch).

Loopt door data/library.json en zet concept_id op elke entry waarvan het woord
exact in het lexicon voorkomt (via Lexicon.concept_for_word). Varianten die niet
in het lexicon staan blijven ongekoppeld; die wachten op de latere laag.

Idempotent: entries die al een concept_id hebben worden overgeslagen.

Gebruik:
  python scripts/backfill_library_concepts.py            # dry-run, schrijft niks
  python scripts/backfill_library_concepts.py --apply    # zet de koppelingen
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nooch_village.library import Library
from nooch_village.lexicon import Lexicon

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def main(apply: bool) -> None:
    library = Library(os.path.join(DATA_DIR, "library.json"))
    lexicon = Lexicon(os.path.join(DATA_DIR, "lexicon.json"))

    to_link: list[tuple[str, str]] = []
    already = 0
    no_match = 0

    for word in list(library.all().keys()):
        entry = library.all()[word]
        if entry.get("concept_id") is not None:
            already += 1
            continue
        cid = lexicon.concept_for_word(word)
        if cid is None:
            no_match += 1
            continue
        to_link.append((word, cid))

    print(f"Te koppelen: {len(to_link)}  |  al gekoppeld: {already}  |  geen lexicon-match: {no_match}\n")
    for word, cid in to_link:
        print(f"  {word}  ->  {cid}")

    if not apply:
        print("\nDry-run, niks weggeschreven. Draai met --apply om te koppelen.")
        return

    for word, cid in to_link:
        library.link_concept(word, cid)
    print(f"\n{len(to_link)} koppeling(en) weggeschreven naar data/library.json.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
