"""
migrate_poc_to_live.py — eenmalige migratie van data/poc/ naar data/

Doet:
  1. Mensen uit data/poc/people.json → data/people.json  (dedup op id)
  2. Toewijzingen uit data/poc/assignments.json → data/assignments.json  (dedup op role_id)
  3. Governance-records uit data/poc/governance_records.json → data/governance_records.json
     (skip: mother_earth__nooch__marketing, mother_earth__test)
     (skip als id al bestaat in live — geen overschrijven)

Idempotent: meerdere keren draaien is veilig.
Geen wijzigingen aan cockpit2.py.
"""
import json, shutil, os
from datetime import datetime

SKIP_RECORDS = {"mother_earth__nooch__marketing", "mother_earth__test"}

POC_DIR  = "data/poc"
LIVE_DIR = "data"

def load(path):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return {}

def backup(path):
    if os.path.exists(path):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = f"{path}.bak.{ts}"
        shutil.copy2(path, dst)
        print(f"  backup → {dst}")

def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def migrate_people():
    src = load(f"{POC_DIR}/people.json")
    dst_path = f"{LIVE_DIR}/people.json"
    dst = load(dst_path)

    added = []
    for pid, person in src.items():
        if pid not in dst:
            dst[pid] = person
            added.append(person["name"])
        else:
            print(f"  skip (bestaat al): {person['name']}")

    backup(dst_path)
    save(dst_path, dst)
    print(f"  mensen toegevoegd: {added}")

def migrate_assignments():
    src = load(f"{POC_DIR}/assignments.json")
    dst_path = f"{LIVE_DIR}/assignments.json"
    dst = load(dst_path)

    added = []
    skipped = []
    for role_id, fillers in src.items():
        if role_id not in dst:
            dst[role_id] = fillers
            added.append(role_id)
        else:
            skipped.append(role_id)

    if skipped:
        print(f"  skip (bestaat al): {skipped}")
    backup(dst_path)
    save(dst_path, dst)
    print(f"  toewijzingen toegevoegd: {len(added)} rollen")

def migrate_governance():
    src = load(f"{POC_DIR}/governance_records.json")
    dst_path = f"{LIVE_DIR}/governance_records.json"
    dst = load(dst_path)

    added = []
    skipped_test = []
    skipped_exists = []

    for rid, rec in src.items():
        if rid in SKIP_RECORDS:
            skipped_test.append(rid)
            continue
        if rid in dst:
            skipped_exists.append(rid)
            continue
        dst[rid] = rec
        added.append(rid)

    print(f"  testdata geskipt:    {skipped_test}")
    print(f"  al aanwezig (skip):  {skipped_exists}")
    backup(dst_path)
    save(dst_path, dst)
    print(f"  records toegevoegd:  {len(added)}")
    for r in added:
        rtype = dst[r].get("type", "?")
        name  = dst[r].get("definition", {}).get("name") or r
        print(f"    [{rtype}] {r} — {name}")

if __name__ == "__main__":
    print("\n=== Stap 1: mensen ===")
    migrate_people()
    print("\n=== Stap 2: toewijzingen ===")
    migrate_assignments()
    print("\n=== Stap 3: governance-records ===")
    migrate_governance()
    print("\nKlaar. Controleer data/ en draai cockpit2 daarna met --data-dir data/")
