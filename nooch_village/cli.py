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
        Village(heartbeat_seconds=0).run_forever()

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

    elif mode == "kennis_scout":
        from nooch_village.demos.knowledge import kennis_scout_demo
        kennis_scout_demo()

    elif mode == "roster":
        from nooch_village.village import Village
        v = Village(heartbeat_seconds=86400)
        v.print_roster()

    else:
        print(f"Onbekende mode '{mode}'. Geldige modes: "
              "once | run | demo | librarian | governance | proposal | lifecycle | "
              "purge | intent | triage | ngram | reflect | simulate | kennis_scout | roster",
              file=sys.stderr)
        sys.exit(1)
