#!/usr/bin/env python3
"""kennis_onderhoud — de wekelijkse nachtelijke kennis-onderhoudsrun (founder 23 jul).

Bundelt drie klussen die de kennisbank schoon en compact houden, op basis van de 23-juli-analyse:
  1. EMBEDDINGS-BACKFILL  — (her)indexeer nieuwe/gewijzigde kaartjes voor de semantische poort.
                            Altijd toegepast: puur additief en omkeerbaar, getemporiseerd onder de
                            gratis-tier-limiet (wacht+herprobeer bij 429).
  2. TAG-OPSCHONING       — los de hint:*-schuld op: map naar een bestaand onderwerp, stel terugkerende
                            nieuwe concepten voor aan de human inbox, gooi zeldzame ruis weg.
  3. MERGE-LUS            — voeg de al bestaande dubbele kaartjes samen (LLM-bevestigd), omkeerbaar via
                            merge_into.

DRY BY DEFAULT: zonder 'apply' rapporteert hij alleen wat fase 2 en 3 ZOUDEN doen (de backfill draait
wel, want veilig). Zo zie je eerst het resultaat; daarna draai je 'apply' en zet je de cron.

Draaien op de server ALS DE APP-GEBRUIKER, met de .env geladen (sleutel + modelnaam):
    cd /opt/noochville
    # zien wat het zou doen:
    sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_onderhoud.py'
    # echt uitvoeren:
    sudo -u nooch bash -c 'set -a; . ./.env; set +a; ./venv/bin/python kennis_onderhoud.py apply'
"""
import os
import sys

from nooch_village.notes_store import NotesStore
from nooch_village.kennis_embeddings import EmbeddingStore, index_backfill
from nooch_village import kennis_tags, kennis_merge

DATA = os.getenv("NOOCH_DATA_DIR", "data")


def main(argv) -> int:
    apply = "apply" in argv
    alleen = next((a.split("=", 1)[1] for a in argv if a.startswith("only=")), "")
    fases = set(alleen.split(",")) if alleen else {"backfill", "tags", "merge"}
    modus = "TOEPASSEN" if apply else "DROOG (rapport, niets gewijzigd)"
    print(f"=== kennis-onderhoud [{modus}] — data={DATA} ===\n")

    notes = NotesStore(f"{DATA}/notes.json")

    # ── 1. Embeddings-backfill (altijd; additief) ────────────────────────────────
    if "backfill" in fases:
        print("[1] EMBEDDINGS-BACKFILL")
        store = EmbeddingStore(f"{DATA}/kennis_embeddings.json")
        stats = index_backfill(notes, store, log=lambda m: print("   " + m))
        print(f"   → geïndexeerd {stats['geindexeerd']}, mislukt {stats['mislukt']}, "
              f"index-omvang {stats['index_omvang']}\n")

    # ── 2. Tag-opschoning (hint:*) ───────────────────────────────────────────────
    if "tags" in fases:
        print("[2] TAG-OPSCHONING (hint:*)")
        plan = kennis_tags.plan_hints(notes)
        print(f"   map → onderwerp : {len(plan['map'])}")
        for c, s in list(plan["map"].items())[:12]:
            print(f"      hint:{c}  →  {s}")
        if plan["voorstel"]:
            print(f"   kandidaat-nieuw-onderwerp (naar jou): {len(plan['voorstel'])}")
            for v in plan["voorstel"]:
                print(f"      '{v['concept']}' ({v['aantal']}x)")
        if plan["drop"]:
            print(f"   weggooien (ruis): {len(plan['drop'])} → {', '.join(plan['drop'][:10])}")
        if plan["onaangeroerd"]:
            print(f"   onaangeroerd (geen LLM): {len(plan['onaangeroerd'])}")
        if apply:
            from nooch_village.human_inbox import HumanInbox
            hi = HumanInbox(f"{DATA}/human_inbox.json")
            r = kennis_tags.pas_hints_toe(notes, plan, human_inbox=hi)
            print(f"   → gemapt {r['gemapt']}, gedropt {r['gedropt']}, voorgesteld {r['voorgesteld']}")
        print()

    # ── 3. Merge-lus ─────────────────────────────────────────────────────────────
    if "merge" in fases:
        print("[3] MERGE-LUS (bestaande dubbelingen)")
        res = kennis_merge.vind_clusters(notes, data_dir=DATA)
        cl = res["clusters"]
        print(f"   kandidaat-paren {res['kandidaat_paren']} | beoordeeld {res['beoordeeld']}"
              + (f" | afgekapt {res['afgekapt']}" if res["afgekapt"] else ""))
        print(f"   bevestigde merge-clusters: {len(cl)}")
        for c in cl[:12]:
            print(f"      ⇒ {c['target_claim'][:70]}")
            for s in c["sources"]:
                print(f"          + {s['claim'][:66]}")
        if apply:
            r = kennis_merge.pas_merge_toe(notes, cl)
            print(f"   → clusters gemerged {r['clusters_gemerged']}, kaarten opgeruimd "
                  f"{r['kaarten_opgeruimd']}")
        print()

    print("=== klaar ===" + ("" if apply else "  (droog — draai met 'apply' om door te voeren)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
