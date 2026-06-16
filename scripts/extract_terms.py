#!/usr/bin/env python3
"""extract_terms — extraheert kandidaat-termen uit een tekstbestand via LLM.

Vergelijkt de geëxtraheerde termen met data/library.json en toont alleen
de onbekende termen. Geen schrijfactie naar disk.

Gebruik:
  python scripts/extract_terms.py <pad-naar-tekstbestand>
"""
from __future__ import annotations
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nooch_village.llm import reason

_SYSTEM_PROMPT = """\
Je bent een term-extractor voor een Nooch sustainability-shoe kennisbank. \
Lees de gegeven tekst en haal alle kandidaat-termen eruit die relevant zijn \
voor een duurzaamheids-, materialen-, of schoenenmerk-bibliotheek.

Dit omvat:
- Materialen (bijv. mycelium, PHA, polyurethaan, EVA)
- Concepten (bijv. closed-loop, biobased, plant-based)
- Merken en industrieën (bijv. Veja, fast fashion)
- Termen rond duurzaamheid, productie, eindgebruikers

Negeer:
- Algemene woorden (de, het, een, schoen, mens)
- Werkwoorden en bijvoeglijke naamwoorden zonder eigen betekenis
- Persoonsnamen tenzij ze relevant zijn als merk
- Geografische namen (Europa, Nederland, Amsterdam)
- Algemene procesbegrippen (productie, verkoop, marketing)
- De merknaam "Nooch" zelf, plus varianten (nooch.earth, nooch shoes)

Output: alleen een JSON-array van strings, lowercase, zonder uitleg of \
inleiding. Voorbeeld: ["mycelium", "polyurethaan", "closed-loop"]\
"""


def extract(text: str, library: dict) -> tuple[list[str], list[str]]:
    """Extraheert kandidaat-termen en filtert bekende eruit.

    Geeft (unknown_terms, all_extracted) terug.
    Gooit ValueError als de LLM geen geldige JSON teruggeeft.
    Gooit RuntimeError als de LLM niet beschikbaar is.
    """
    prompt = f"{_SYSTEM_PROMPT}\n\nTekst:\n{text}"
    raw = reason(prompt)

    if raw is None:
        raise RuntimeError("LLM niet beschikbaar — stel ANTHROPIC_API_KEY of GEMINI_API_KEY in.")

    try:
        terms = json.loads(raw)
        if not isinstance(terms, list):
            raise ValueError("LLM-output is geen array")
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM gaf geen geldige JSON:\n{raw}") from exc

    terms = [t.lower().strip() for t in terms if isinstance(t, str)]
    known = set(library.keys())
    unknown = [t for t in terms if t not in known]
    return unknown, terms


def main() -> None:
    if len(sys.argv) < 2:
        print("Gebruik: python scripts/extract_terms.py <pad-naar-tekstbestand>",
              file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"⛔  Bestand niet gevonden: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        text = f.read()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    library_path = os.path.join(root, "data", "library.json")
    with open(library_path, encoding="utf-8") as f:
        library = json.load(f)

    try:
        unknown, all_terms = extract(text, library)
    except ValueError as exc:
        print(f"⛔  {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"⛔  {exc}", file=sys.stderr)
        sys.exit(1)

    for term in unknown:
        print(term)

    known_count = len(all_terms) - len(unknown)
    print(f"\nGeëxtraheerd: {len(all_terms)}, bekend: {known_count}, nieuw: {len(unknown)}")


if __name__ == "__main__":
    main()
