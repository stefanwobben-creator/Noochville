#!/usr/bin/env python3
"""Stel met de LLM concepten voor bij ongekoppelde library-keywords.

Loopt over elke library-entry zonder concept_id, biedt de LLM de approved
lexicon-concepten aan (met hun rationale), en verzamelt de voorstellen.
Toont alleen, schrijft niets. De mens beoordeelt voordat er gekoppeld wordt.

Gebruik:
  python scripts/suggest_concepts.py
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nooch_village.library import Library
from nooch_village.lexicon import Lexicon
from nooch_village.concept_suggest import suggest_concept

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def main() -> None:
    library = Library(os.path.join(DATA_DIR, "library.json"))
    lexicon = Lexicon(os.path.join(DATA_DIR, "lexicon.json"))

    approved = [
        {"concept_id": cid, "words": e.get("words", {}), "rationale": e.get("rationale", "")}
        for cid, e in lexicon._data.items()
        if e.get("status") == "approved"
    ]
    print(f"{len(approved)} approved concepten als doel: "
          f"{sorted(c['concept_id'] for c in approved)}\n")

    unlinked = [w for w, e in library._data.items() if not e.get("concept_id")]
    print(f"{len(unlinked)} ongekoppelde keywords te beoordelen.\n")

    suggestions = []
    for word in unlinked:
        cid = suggest_concept(word, approved)
        if cid:
            suggestions.append((word, cid))

    print(f"Voorstellen: {len(suggestions)}  |  geen voorstel: "
          f"{len(unlinked) - len(suggestions)}\n")
    for word, cid in sorted(suggestions):
        print(f"  {word}   ->  {cid}")

    if not suggestions:
        print("(Geen voorstellen. Zonder ANTHROPIC_API_KEY geeft de LLM niets terug, "
              "controleer of de key gezet is.)")


if __name__ == "__main__":
    main()
