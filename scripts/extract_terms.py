#!/usr/bin/env python3
"""extract_terms — extraheert kandidaat-termen uit een tekstbestand via LLM.

Vergelijkt de geëxtraheerde termen met data/library.json en toont alleen
de onbekende termen. Schrijft een review-bestand voor --apply.

Gebruik:
  python scripts/extract_terms.py <pad-naar-tekstbestand>   # dry-run
  python scripts/extract_terms.py --apply                   # verwerk review-bestand
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nooch_village.llm import reason
from nooch_village.library import Library

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

_VALID_DECISIONS = {"escalated", "forbidden", "ignore", "PENDING"}


def _review_path(data_dir: str) -> str:
    return os.path.join(data_dir, f"extract_review_{date.today().isoformat()}.json")


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


def run_dry_run(text_path: str, library_path: str, data_dir: str) -> None:
    with open(text_path, encoding="utf-8") as f:
        text = f.read()

    with open(library_path, encoding="utf-8") as f:
        library = json.load(f)

    unknown, all_terms = extract(text, library)

    known_count = len(all_terms) - len(unknown)
    print(f"Geëxtraheerd: {len(all_terms)}, bekend: {known_count}, nieuw: {len(unknown)}\n")

    for term in unknown:
        print(f"  {term}")

    review = {
        term: {"source": text_path, "decision": "PENDING"}
        for term in unknown
    }
    os.makedirs(data_dir, exist_ok=True)
    path = _review_path(data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2, ensure_ascii=False)

    print(f"\nReview-bestand: {path}")
    print("Vul PENDING-items in (escalated / forbidden / ignore), draai daarna --apply.")


def run_apply(library_path: str, data_dir: str) -> None:
    review_path = _review_path(data_dir)
    if not os.path.exists(review_path):
        print(f"⛔  Geen review-bestand gevonden voor vandaag: {review_path}", file=sys.stderr)
        print("Draai eerst een dry-run.", file=sys.stderr)
        sys.exit(1)

    with open(review_path, encoding="utf-8") as f:
        review = json.load(f)

    # Valideer beslissingen
    for term, row in review.items():
        decision = row.get("decision", "")
        if decision not in _VALID_DECISIONS:
            print(f"⛔  Ongeldige decision '{decision}' voor term '{term}'.", file=sys.stderr)
            sys.exit(1)

    # Blokkeer bij PENDING
    pending = [t for t, v in review.items() if v["decision"] == "PENDING"]
    if pending:
        print(f"⛔  {len(pending)} items nog PENDING. Vul het review-bestand in:", file=sys.stderr)
        for t in pending:
            print(f"   - {t}", file=sys.stderr)
        sys.exit(1)

    lib = Library(library_path)
    escalated = forbidden = ignored = 0
    for term, row in review.items():
        decision = row["decision"]
        source = row.get("source", "extract_terms")
        if decision == "escalated":
            lib.curate(term, status="escalated",
                       rationale=f"extracted from {source}")
            escalated += 1
        elif decision == "forbidden":
            lib.curate(term, status="forbidden",
                       rationale=f"extracted from {source}")
            forbidden += 1
        elif decision == "ignore":
            ignored += 1

    print(f"✓  {escalated} escalated, {forbidden} forbidden, {ignored} ignored.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extraheer termen uit een tekstbestand en beheer de review."
    )
    parser.add_argument("pad", nargs="?", help="Pad naar het tekstbestand (dry-run)")
    parser.add_argument("--apply", action="store_true",
                        help="Verwerk het review-bestand van vandaag")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    library_path = os.path.join(root, "data", "library.json")
    data_dir = os.path.join(root, "data")

    if args.apply:
        run_apply(library_path, data_dir)
        return

    if not args.pad:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.pad):
        print(f"⛔  Bestand niet gevonden: {args.pad}", file=sys.stderr)
        sys.exit(1)

    try:
        run_dry_run(args.pad, library_path, data_dir)
    except ValueError as exc:
        print(f"⛔  {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"⛔  {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
