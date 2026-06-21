#!/usr/bin/env python3
"""Erf library-concepten via parent_keyword (ketingewijs tot fixpoint).

Voor elke entry zonder concept_id maar met een evidence.parent_keyword: leid het
concept af van de parent, eerst via een al-opgeloste parent, anders via het lexicon
(concept_for_word op de parent zelf). Herhaalt tot er geen nieuwe koppeling meer bijkomt,
zodat ketens van willekeurige diepte sluiten.

Idempotent: entries die al een concept_id hebben blijven ongemoeid.

Gebruik:
  python scripts/inherit_library_concepts.py            # dry-run, schrijft niks
  python scripts/inherit_library_concepts.py --apply
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nooch_village.library import Library
from nooch_village.lexicon import Lexicon

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


AMBIGUOUS_PARENTS = {"burger", "consument"}


def main(apply: bool) -> None:
    library = Library(os.path.join(DATA_DIR, "library.json"))
    lexicon = Lexicon(os.path.join(DATA_DIR, "lexicon.json"))

    pre_linked = {w for w, e in library._data.items() if e.get("concept_id")}
    resolved = {w: library._data[w]["concept_id"] for w in pre_linked}
    derivation: dict[str, tuple[str, str]] = {}

    changed = True
    while changed:
        changed = False
        for word, entry in library._data.items():
            if word in resolved:
                continue
            parent = (entry.get("evidence") or {}).get("parent_keyword")
            if not parent:
                continue
            if parent.lower() in AMBIGUOUS_PARENTS:
                continue
            cid = resolved.get(parent.lower()) or lexicon.concept_for_word(parent)
            if cid:
                resolved[word] = cid
                derivation[word] = (parent, cid)
                changed = True

    to_link = {w: c for w, c in resolved.items() if w not in pre_linked}

    suggestions: dict[str, tuple[str, str | None]] = {}
    for word, entry in library._data.items():
        if word in resolved:
            continue
        parent = (entry.get("evidence") or {}).get("parent_keyword")
        if parent and parent.lower() in AMBIGUOUS_PARENTS:
            suggestions[word] = (parent, lexicon.concept_for_word(parent))

    unresolved = sum(
        1 for w, e in library._data.items()
        if w not in resolved and w not in suggestions
        and (e.get("evidence") or {}).get("parent_keyword")
    )
    no_parent = sum(
        1 for w, e in library._data.items()
        if not (e.get("evidence") or {}).get("parent_keyword")
    )

    print(f"Al gekoppeld: {len(pre_linked)}  |  auto via erving: {len(to_link)}  "
          f"|  suggesties (ambigu): {len(suggestions)}  "
          f"|  onopgelost: {unresolved}  |  zonder parent: {no_parent}\n")

    print("Auto te koppelen:")
    for word in sorted(to_link):
        parent, cid = derivation[word]
        print(f"  {word}   (via '{parent}')  ->  {cid}")

    print("\nSuggesties, handmatig beoordelen (niet weggeschreven):")
    for word in sorted(suggestions):
        parent, proposed = suggestions[word]
        print(f"  {word}   (via '{parent}')  ->  {proposed}?")

    if not apply:
        print("\nDry-run, niks weggeschreven. Draai met --apply om de auto-groep te koppelen.")
        return

    for word, cid in to_link.items():
        library.link_concept(word, cid)
    print(f"\n{len(to_link)} auto-koppeling(en) weggeschreven. Suggesties ongemoeid gelaten.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
