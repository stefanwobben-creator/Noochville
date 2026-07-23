#!/usr/bin/env python3
"""projectverzoek uitdelen — de handoff-skill aan elke bemande rol koppelen (founder, 23 jul).

projectverzoek is cross-cutting: elke rol moet werk dat bij een andere rol hoort kunnen doorgeven
i.p.v. dood te lopen op 'geen skill'. Dit script koppelt de skill via governance (grant_skill_via_
governance → synchroon door de G0-G4-poort) aan alle bemande rollen. Idempotent.

Draaien op de server ALS DE APP-GEBRUIKER (rechten!):
    cd /opt/noochville && sudo -u nooch ./venv/bin/python projectverzoek_uitdelen.py
"""
import sys

from nooch_village.role_proposals import grant_skill_via_governance

REDEN = ("projectverzoek is cross-cutting: een deel-item dat bij een andere rol hoort geef je door "
         "als queued project op haar bord, zodat een project niet doodloopt op 'geen skill'.")

ROLLEN = [
    "librarian",
    "harry_hemp",
    "compliance",
    "concurrent_scout",
    "website_watcher",
    "noochie",
    "mother_earth__nooch__noochville__copywriter",
]

if __name__ == "__main__":
    ok = 0
    for rol in ROLLEN:
        try:
            grant_skill_via_governance(rol, "projectverzoek", REDEN)
            ok += 1
        except Exception as e:
            print(f"⚠ {rol}: {e}", file=sys.stderr)
    print(f"\nKlaar. {ok}/{len(ROLLEN)} rollen verwerkt.")
