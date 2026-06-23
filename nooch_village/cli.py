"""CLI-dispatcher voor `python -m nooch_village.village <mode>`."""
from __future__ import annotations
import sys


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if mode == "once":
        from nooch_village.village import once
        once()

    elif mode == "run":
        from nooch_village.village import Village
        Village().run_forever()   # heartbeat uit settings.ini (lokaal: 5s, prod: 0)

    elif mode == "demo":
        from nooch_village.demos.growth import demo
        demo()

    elif mode == "librarian":
        from nooch_village.demos.knowledge import librarian_demo
        librarian_demo()

    elif mode == "governance":
        from nooch_village.demos.governance_demos import governance_demo
        governance_demo()

    elif mode == "proposal":
        from nooch_village.demos.governance_demos import proposal_demo
        proposal_demo()

    elif mode == "lifecycle":
        from nooch_village.demos.governance_demos import lifecycle_demo
        lifecycle_demo()

    elif mode == "purge":
        from nooch_village.demos.governance_demos import purge_demo
        purge_demo()

    elif mode == "intent":
        from nooch_village.demos.analysis import intent_demo
        intent_demo()

    elif mode == "triage":
        from nooch_village.demos.analysis import triage_demo
        triage_demo()

    elif mode == "ngram":
        from nooch_village.demos.analysis import ngram_demo
        ngram_demo()

    elif mode == "reflect":
        from nooch_village.demos.analysis import reflect_demo
        reflect_demo()

    elif mode == "simulate":
        from nooch_village.demos.ops import simulate
        simulate()

    elif mode == "harry_hemp":
        from nooch_village.demos.knowledge import harry_hemp_grounding_demo
        harry_hemp_grounding_demo()

    elif mode == "content_strategist":
        from nooch_village.role_proposals import birth_content_strategist
        birth_content_strategist()

    elif mode == "content_strategist_skills":
        from nooch_village.role_proposals import grant_content_strategist_skills
        grant_content_strategist_skills()

    elif mode == "ingest":
        import json, os
        from nooch_village.config import load_context
        from nooch_village.ingest import ingest_insights
        from nooch_village.notes_store import NotesStore
        from nooch_village.village import BASE_DIR
        if len(sys.argv) < 3:
            print("Gebruik: python -m nooch_village.village ingest <pad-naar-json>",
                  file=sys.stderr)
            sys.exit(1)
        with open(sys.argv[2], encoding="utf-8") as f:
            items = json.load(f)
        ctx = load_context(BASE_DIR)
        notes = NotesStore(os.path.join(ctx.data_dir, "notes.json"))
        res = ingest_insights(notes, items)
        print(f"Ingestie: {len(res['added'])} toegevoegd, "
              f"{len(res['skipped'])} overgeslagen, {res['linked']} link(s) gelegd.")
        for i in res["added"]:
            print(f"  + {i}")
        for i in res["skipped"]:
            print(f"  = {i} (bestond al)")

    elif mode == "roster":
        from nooch_village.village import Village
        v = Village(heartbeat_seconds=86400)
        v.print_roster()

    else:
        print(f"Onbekende mode '{mode}'. Geldige modes: "
              "once | run | demo | librarian | governance | proposal | lifecycle | "
              "purge | intent | triage | ngram | reflect | simulate | harry_hemp | "
              "content_strategist | ingest | roster",
              file=sys.stderr)
        sys.exit(1)
