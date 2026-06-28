"""Begrensd validatie-script: één echte keywords_everywhere-meting.

Gebruik: ./venv/bin/python scripts/live_measure.py [markt] [tier]
  markt  — bijv. nl, en, de  (default: nl)
  tier   — bijv. core, long  (default: core)
Draai vanuit de projectroot (de map die nooch_village/ bevat).
"""
from __future__ import annotations
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from nooch_village.config import load_context          # laadt .env + settings.ini
from nooch_village.keyword_batch import propose_batch
from nooch_village.keyword_measure import measure_batch
from nooch_village.keyword_runner import make_keywords_runner
from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill

markt = sys.argv[1] if len(sys.argv) > 1 else "nl"
tier  = sys.argv[2] if len(sys.argv) > 2 else "core"

context = load_context(str(BASE_DIR))

# --- batch bouwen ---
batch = propose_batch(markt, tier=tier)

n = len(batch["candidates"])
assert n <= 30, (
    f"Vangnet: batch heeft {n} kandidaten — verwacht max 30. "
    "Stop, controleer keyword_matrix."
)

print(f"\nKandidaten ({n} credits op {markt}/{tier}):")
for term in batch["candidates"]:
    print(f"  {term}")

# --- expliciete bevestiging ---
antwoord = input(f"\n{n} credits uitgeven op {markt}/{tier}? [y/N] ").strip()
if antwoord != "y":
    print("Afgebroken.")
    sys.exit(0)

# --- meting uitvoeren ---
approval = {
    "approved":        True,
    "credits_ceiling": n,
    "by":              "stefan",
}
runner = make_keywords_runner(KeywordsEverywhereSkill(), context)
result = measure_batch(batch, approval, runner)

# --- resultaten tonen ---
keywords = sorted(result["results"], key=lambda r: r.get("vol", 0), reverse=True)

print(f"\nResultaten ({result['credits_spent']} credits uitgegeven, "
      f"{len(keywords)} keywords terug):\n")
print(f"{'keyword':<35} {'vol':>7}  {'cpc':>6}  {'comp':>6}")
print("-" * 60)
for kw in keywords:
    print(
        f"{kw['keyword']:<35} "
        f"{kw.get('vol', 0):>7}  "
        f"{kw.get('cpc', 0.0):>6.2f}  "
        f"{kw.get('competition', 0.0):>6.2f}"
    )

print(f"\ncredits_spent : {result['credits_spent']}")
print("Actueel saldo : https://keywordseverywhere.com (Keywords Everywhere dashboard)")
