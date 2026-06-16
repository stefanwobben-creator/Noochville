#!/usr/bin/env python3
"""Library cleanup — dry-run tabel + --apply mechanisme.

Gebruik:
  python scripts/library_cleanup.py          # dry-run: tabel + review-file
  python scripts/library_cleanup.py --apply  # verwerk ingevulde review-file
"""
from __future__ import annotations
import argparse, json, os, re, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nooch_village.library import Library

# ── Clusters ──────────────────────────────────────────────────────────────────

CLUSTERS = {
    "nooch-typo": {
        "pattern": re.compile(
            r"^(nooches|nootch|noech|nokwol|noo shoes|"
            r"no shors|nobox)(\s|$)"
        ),
        "suggestion": "forbidden",
        "reden": "merktypo of spellingvariant, nooit SEO-doel",
    },
    "food-noise": {
        "pattern": re.compile(
            r"(burger king|smash burger|bun burger|"
            r"burger amsterdam|de burger)"
        ),
        "suggestion": "forbidden",
        "reden": "lexicon-seed 'burger' trok voedsel-zoekopdrachten",
    },
    "authority-noise": {
        "pattern": re.compile(
            r"(autoriteit consument|consument en markt|"
            r"consument & markt|wat is (een )?consument)"
        ),
        "suggestion": "forbidden",
        "reden": "lexicon-seed 'consument' trok ACM/juridisch publiek",
    },
    "vegan-risico": {
        "pattern": re.compile(r"vegan|veganistisch"),
        "suggestion": None,
        "reden": "positief signaal maar risico op plastic/PU-associatie",
    },
    "missie-adjacent": {
        "terms": {
            "compostable shoes", "shoes with no plastic",
            "sustainable shoes", "earth sneakers",
            "biologische schoenen", "duurzame wandelschoenen",
            "natural materials shoes",
        },
        "suggestion": None,
        "reden": "sluit aan op kernwaarden, mist merkspecifieke POV",
    },
}

# ── Classificatie ─────────────────────────────────────────────────────────────

def classify_entry(term: str) -> tuple[str, str | None, str]:
    """Geeft (cluster_naam, suggestion, reden) voor een term."""
    w = term.lower()
    for name, cfg in CLUSTERS.items():
        if "pattern" in cfg and cfg["pattern"].search(w):
            return name, cfg["suggestion"], cfg["reden"]
        if "terms" in cfg and w in cfg["terms"]:
            return name, cfg["suggestion"], cfg["reden"]
    return "overig", None, "geen patroon herkend; individuele beoordeling vereist"

# ── Hulpfuncties ──────────────────────────────────────────────────────────────

def _bron(evidence: dict) -> str:
    src = evidence.get("source", "")
    return {
        "google_trends_related": "trends",
        "google_trends": "trends",
        "gsc": "gsc",
        "ngram_culture": "ngram",
    }.get(src, src or "?")


def _interest(evidence: dict) -> str:
    v = evidence.get("interest")
    return str(v) if v is not None else "—"


def _review_path(data_dir: str) -> str:
    return os.path.join(data_dir, f"cleanup_review_{date.today().isoformat()}.json")

# ── Dry-run ───────────────────────────────────────────────────────────────────

def run_dry_run(library_path: str, data_dir: str) -> None:
    with open(library_path, encoding="utf-8") as f:
        lib_data = json.load(f)

    escalated = {t: e for t, e in lib_data.items() if e.get("status") == "escalated"}

    cluster_order = list(CLUSTERS.keys()) + ["overig"]
    by_cluster: dict[str, list[tuple[str, dict]]] = {k: [] for k in cluster_order}
    for term, entry in escalated.items():
        cluster, _, _ = classify_entry(term)
        by_cluster[cluster].append((term, entry))

    review: dict[str, dict] = {}
    auto_count = 0
    pending_count = 0

    W = 64
    print("═" * W)
    print(f" LIBRARY CLEANUP — dry-run | {len(escalated)} escalated items | {date.today()}")
    print("═" * W)

    for cluster_name in cluster_order:
        items = by_cluster[cluster_name]
        if not items:
            continue
        cfg = CLUSTERS.get(cluster_name, {})
        suggestion = cfg.get("suggestion")
        reden = cfg.get("reden", "geen patroon herkend; individuele beoordeling vereist")
        bulk_label = f"bulk-suggestie: {suggestion}" if suggestion else "JOUW BESLISSING"

        print(f"\nCLUSTER: {cluster_name}  ({len(items)} items)  {bulk_label}")
        print(f"  Reden: {reden}")
        print("─" * W)
        print(f"  {'TERM':<32} {'BRON':<8} {'INTEREST':<10} SUGGESTIE")

        for term, entry in items:
            ev = entry.get("evidence", {})
            sug_label = suggestion or "?"
            print(f"  {term:<32} {_bron(ev):<8} {_interest(ev):<10} {sug_label}")

            decision = suggestion if suggestion else "PENDING"
            review[term] = {
                "cluster": cluster_name,
                "suggested": suggestion,
                "decision": decision,
            }
            if decision == "PENDING":
                pending_count += 1
            else:
                auto_count += 1

    print(f"\n{'═' * W}")
    print(" SAMENVATTING")
    print(f"{'═' * W}")
    print(f"  forbidden (automatisch):   {auto_count}")
    print(f"  PENDING (jouw beslissing): {pending_count}")
    if pending_count > 0:
        print(f"  --apply: GEBLOKKEERD — los {pending_count} PENDING-items op in de review-file")
    else:
        print("  --apply: klaar om uit te voeren")
    print("═" * W)

    os.makedirs(data_dir, exist_ok=True)
    path = _review_path(data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2, ensure_ascii=False)
    print(f"\nReview-file: {path}")
    print("Vul PENDING-items in, draai daarna --apply.")

# ── Apply ─────────────────────────────────────────────────────────────────────

def run_apply(library_path: str, data_dir: str) -> None:
    review_path = _review_path(data_dir)
    if not os.path.exists(review_path):
        print(f"⛔  Review-file niet gevonden: {review_path}")
        print("Draai eerst de dry-run om een review-file aan te maken.")
        sys.exit(1)

    with open(review_path, encoding="utf-8") as f:
        review = json.load(f)

    pending = [t for t, v in review.items() if v["decision"] == "PENDING"]
    if pending:
        print(f"⛔  {len(pending)} items nog PENDING. Vul de review-file in:")
        for t in pending:
            print(f"   - {t}")
        sys.exit(1)

    lib = Library(library_path)
    applied = 0
    skipped = 0
    for term, row in review.items():
        if row["decision"] == "ignore":
            skipped += 1
            continue
        lib.curate(
            term,
            status=row["decision"],
            rationale=f"cleanup {date.today()} — cluster: {row['cluster']}",
        )
        applied += 1

    print(f"✓  {applied} entries bijgewerkt in library.json ({skipped} genegeerd).")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Library cleanup — triage van escalated entries"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Verwerk de review-file naar library.json"
    )
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    library_path = os.path.join(root, "data", "library.json")
    data_dir = os.path.join(root, "data")

    if args.apply:
        run_apply(library_path, data_dir)
    else:
        run_dry_run(library_path, data_dir)


if __name__ == "__main__":
    main()
