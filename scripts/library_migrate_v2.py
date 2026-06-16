#!/usr/bin/env python3
"""library_migrate_v2 — voeg nullable velden toe aan library.json entries.

Voegt locale, concept_id, gemet_id toe aan elke entry die ze nog mist.
Idempotent: entries die de velden al hebben worden overgeslagen.

Gebruik:
  python scripts/library_migrate_v2.py          # dry-run
  python scripts/library_migrate_v2.py --apply  # schrijft naar disk
"""
from __future__ import annotations
import argparse, json, os, sys

NEW_FIELDS = ("locale", "concept_id", "gemet_id")


def migrate(data: dict, dry_run: bool = True) -> tuple[int, int]:
    """Muteert data in-place (tenzij dry_run). Geeft (updated, already_complete)."""
    updated = 0
    already_complete = 0
    for word, entry in data.items():
        needs_update = any(f not in entry for f in NEW_FIELDS)
        if not needs_update:
            already_complete += 1
            continue
        if not dry_run:
            for field in NEW_FIELDS:
                entry.setdefault(field, None)
        updated += 1
    return updated, already_complete


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Voeg locale/concept_id/gemet_id toe aan library.json entries"
    )
    parser.add_argument("--apply", action="store_true",
                        help="Schrijf wijzigingen naar disk")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    library_path = os.path.join(root, "data", "library.json")

    if not os.path.exists(library_path):
        print(f"⛔  library.json niet gevonden: {library_path}")
        sys.exit(1)

    with open(library_path, encoding="utf-8") as f:
        data = json.load(f)

    dry_run = not args.apply
    updated, already_complete = migrate(data, dry_run=dry_run)

    if dry_run:
        print(f"DRY-RUN | bij te werken: {updated}, al compleet: {already_complete}")
    else:
        with open(library_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Bijgewerkt: {updated}, al compleet: {already_complete}")


if __name__ == "__main__":
    main()
