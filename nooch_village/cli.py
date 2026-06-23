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

    elif mode == "grant_serpapi_trends":
        from nooch_village.role_proposals import grant_website_watcher_serpapi
        grant_website_watcher_serpapi()

    elif mode == "grant_skill":
        from nooch_village.role_proposals import grant_skill_via_governance
        if len(sys.argv) < 4:
            print("Gebruik: python -m nooch_village.village grant_skill <role_id> <skill>",
                  file=sys.stderr)
            sys.exit(1)
        grant_skill_via_governance(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))

    elif mode == "remove_role":
        from nooch_village.role_proposals import remove_role_via_governance
        if len(sys.argv) < 3:
            print("Gebruik: python -m nooch_village.village remove_role <role_id> [reden]",
                  file=sys.stderr)
            sys.exit(1)
        remove_role_via_governance(sys.argv[2], " ".join(sys.argv[3:]))

    elif mode == "rereview":
        import os
        from nooch_village.config import load_context
        from nooch_village.library import Library
        from nooch_village.lexicon import Lexicon
        from nooch_village.seeds import seed_lexicon
        from nooch_village.library_rereview import rereview_escalated
        from nooch_village.village import BASE_DIR
        dry = "dry" in sys.argv[2:]
        ctx = load_context(BASE_DIR)
        ctx.library = Library(os.path.join(ctx.data_dir, "library.json"))
        ctx.lexicon = Lexicon(os.path.join(ctx.data_dir, "lexicon.json"))
        seed_lexicon(ctx.lexicon)                      # zorg dat leather_free aanwezig is
        res = rereview_escalated(ctx.library, ctx, apply=not dry)
        kop = "DROOGDRAAI (niets geschreven)" if dry else "Her-review toegepast"
        print(f"{kop} — {res['total']} escalated termen bekeken:")
        print(f"  → approved : {len(res['approved'])}")
        for w in res["approved"]:
            print(f"      + {w}")
        print(f"  → forbidden: {len(res['forbidden'])}")
        for w in res["forbidden"]:
            print(f"      - {w}")
        print(f"  → blijven escalated: {res['unchanged']}")
        if dry:
            print("\nDraai zonder 'dry' om dit echt door te voeren.")

    elif mode == "measure_propose":
        import os
        from nooch_village.config import load_context
        from nooch_village.human_inbox import HumanInbox
        from nooch_village.keyword_aanjager import propose_locale_batches, DEFAULT_LOCALES
        from nooch_village.village import BASE_DIR
        tier = "core"
        locales: list[str] = []
        for a in sys.argv[2:]:
            if a in ("core", "longtail"):
                tier = a
            else:
                locales.append(a)
        ctx = load_context(BASE_DIR)
        inbox = HumanInbox(os.path.join(ctx.data_dir, "human_inbox.json"))
        queued = propose_locale_batches(inbox, locales or None, tier)
        total = sum(q["candidates"] for q in queued)
        print(f"Meet-batches in de inbox gezet (tier={tier}):")
        for q in queued:
            print(f"  {q['locale']} → geo {q['geo']}: {q['candidates']} kandidaten  [{q['iid']}]")
        print(f"\nMax {total} credits als je ALLE batches goedkeurt (per batch los te keuren).")
        print("Bekijk + keur goed:  python -m nooch_village.inbox")

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
              "content_strategist | grant_serpapi_trends | grant_skill | remove_role | "
              "measure_propose | rereview | ingest | roster",
              file=sys.stderr)
        sys.exit(1)
