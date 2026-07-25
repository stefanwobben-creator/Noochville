"""Eenmalige migratie: til bestaande, ongecommitte curatie uit de getrackte seed naar de
runtime-overlay, en zet de seed daarna terug op de git-versie.

Achtergrond: vóór de seed/overlay-splitsing schreef de app curatie (termen, werklijst-statussen)
rechtstreeks in `config/claims_database.json`. Op de server staat die dus als ongecommitte
wijziging in de working tree — wat het ff-only-deploymodel blokkeert. Deze migratie:

  1. TILT eerst de extra curatie in `data/claims_runtime.json` (de overlay), door de working-copy
     te vergelijken met de git-versie (`git show HEAD:config/claims_database.json`).
  2. RESET pas daarna de seed (`git checkout -- config/claims_database.json`), zodat de tree schoon
     wordt. De volgorde is hard: eerst tillen, anders gooit de reset de curatie weg.

Idempotent: bestaat de overlay al, dan doet de migratie niets. Draai dit ééns op de server, als de
service-gebruiker (nooch):

    sudo -u nooch /opt/noochville/venv/bin/python -m nooch_village.claims_migrate
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from nooch_village import claims_db


def bereken_delta(committed: dict, working: dict) -> dict:
    """De overlay-delta = wat de working-copy méér/anders heeft dan de git-versie.

    - toegevoegd: termen in de working-copy die niet in de git-versie staan (op patroon).
    - werklijst: statussen die afwijken van de git-versie (per nr).
    - meta_versie: de versie uit de working-copy.
    Bewust GEEN `ingetrokken`: een term die in git staat maar in de working-copy ontbreekt wordt
    niet automatisch ingetrokken — aanwezigheid wint, precies zoals de conflictregel in load()."""
    commit_patronen = {claims_db._term_key(t) for t in committed.get("termen", [])}
    toegevoegd = [t for t in working.get("termen", [])
                  if claims_db._term_key(t) and claims_db._term_key(t) not in commit_patronen]

    commit_status = {str(i.get("nr")): i.get("status") for i in committed.get("werklijst", [])}
    werklijst = {str(i.get("nr")): i.get("status")
                 for i in working.get("werklijst", [])
                 if str(i.get("nr")) in commit_status and i.get("status") != commit_status[str(i.get("nr"))]}

    delta = claims_db._leeg_overlay()
    delta["toegevoegd"] = toegevoegd
    delta["werklijst"] = werklijst
    delta["meta_versie"] = str((working.get("meta") or {}).get("versie") or "")
    return delta


def _git_committed_seed() -> dict:
    """De seed zoals hij in HEAD staat (git), los van de working-copy."""
    rel = os.path.relpath(claims_db.DB_PATH, claims_db.BASE_DIR)
    uit = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=claims_db.BASE_DIR,
                         capture_output=True, text=True)
    if uit.returncode != 0:
        raise RuntimeError(f"git show faalde: {uit.stderr.strip()}")
    return json.loads(uit.stdout)


def _leeg(delta: dict) -> bool:
    return not delta["toegevoegd"] and not delta["werklijst"]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    data_dir = argv[0] if argv else os.path.join(claims_db.BASE_DIR, "data")
    overlay = claims_db._overlay_pad(data_dir)

    if os.path.exists(overlay):
        print(f"✓ overlay bestaat al ({overlay}) — niets te migreren (idempotent).")
        return 0

    working = claims_db.load_seed()                      # de working-copy van de seed
    try:
        committed = _git_committed_seed()
    except (RuntimeError, json.JSONDecodeError) as e:
        print(f"✗ kan de git-versie van de seed niet lezen: {e}", file=sys.stderr)
        return 1

    delta = bereken_delta(committed, working)
    if _leeg(delta):
        print("✓ working-copy gelijk aan git — geen curatie om te tillen, geen reset nodig.")
        return 0

    # 1. TILLEN (eerst!) — schrijf de overlay met de extra curatie.
    claims_db._schrijf_overlay(data_dir, delta)
    print(f"✓ getild naar {overlay}: {len(delta['toegevoegd'])} extra term(en), "
          f"{len(delta['werklijst'])} status-override(s).")

    # 2. RESET (pas daarna) — de seed terug op de git-versie, tree wordt schoon.
    rel = os.path.relpath(claims_db.DB_PATH, claims_db.BASE_DIR)
    uit = subprocess.run(["git", "checkout", "--", rel], cwd=claims_db.BASE_DIR,
                         capture_output=True, text=True)
    if uit.returncode != 0:
        print(f"✗ overlay geschreven, maar seed-reset faalde: {uit.stderr.strip()}\n"
              f"  Reset handmatig: git checkout -- {rel}", file=sys.stderr)
        return 2
    print(f"✓ seed teruggezet op de git-versie ({rel}); working tree is schoon.")
    print("  De claims-curatie leeft nu in de overlay; deploys blokkeren niet meer op dit bestand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
