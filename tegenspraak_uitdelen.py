#!/usr/bin/env python3
"""tegenspraak uitdelen — de algemene kwaliteitsskill aan elke bemande rol koppelen (founder, 22 jul).

tegenspraak is cross-cutting: elke inwoner hoort z'n eigen deliverable te kunnen tegenspreken vóór
'done'. Dit script koppelt de skill via governance (grant_skill_via_governance → synchroon door de
G0-G4-poort) aan alle bemande rollen. Idempotent: een rol die 'm al heeft, wordt overgeslagen.

Draaien op de server ALS DE APP-GEBRUIKER (rechten!):
    cd /opt/noochville && sudo -u nooch ./venv/bin/python tegenspraak_uitdelen.py
"""
import sys

from nooch_village.role_proposals import grant_skill_via_governance

REDEN = ("tegenspraak is cross-cutting: elke rol moet z'n eigen output kritisch kunnen tegenspreken "
         "(zwakste claim, ongegrond, tegenargument, revisie) vóór 'done'.")

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
            grant_skill_via_governance(rol, "tegenspraak", REDEN)
            ok += 1
        except Exception as e:
            print(f"⚠ {rol}: {e}", file=sys.stderr)
    print(f"\nKlaar. {ok}/{len(ROLLEN)} rollen verwerkt.")
