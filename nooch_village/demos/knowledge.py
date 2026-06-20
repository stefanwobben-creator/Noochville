"""Librarian en Harry Hemp demo-functies."""
from __future__ import annotations
import time
from nooch_village.event_bus import Event
from nooch_village.village import Village


def librarian_demo():
    """Demonstreer de Librarian: beoordeelt kandidaat-woorden live tegen de missie."""
    v = Village(heartbeat_seconds=86400)
    decisions: dict = {}
    escalations: list = []

    v.bus.subscribe("keyword_decided",       lambda e: decisions.update({e.data["word"]: e.data}))
    v.bus.subscribe("human_decision_needed", lambda e: escalations.append(e.data))

    v.start()

    candidates = [
        {"word": "plasticvrije sneakers",    "demand": {"signal": "rising",    "interest": 45}},
        {"word": "vegan schoenen",           "demand": {"signal": "positive",  "interest": 22}},
        {"word": "100% duurzaam",            "demand": {"signal": "rising",    "interest": 30}},
        {"word": "duurzame wandelschoenen",  "demand": {}},
    ]

    print("\n================ DEMO: Librarian beoordeelt kandidaat-woorden ================\n")
    for c in candidates:
        v.bus.publish(Event("keyword_proposed", {**c, "from": "demo"}, "demo"))

    for _ in range(100):
        if len(decisions) + len(escalations) >= len(candidates):
            break
        time.sleep(0.1)
    v.stop()
    time.sleep(0.1)

    all_results = {**{d["word"]: d for d in decisions.values()},
                   **{e["word"]: {**e, "status": "escalated"} for e in escalations}}

    print(f"\n{'Woord':<30} {'Status':<11} Reden")
    print("-" * 80)
    for word in [c["word"] for c in candidates]:
        d = all_results.get(word, {})
        print(f"{word:<30} {d.get('status', '?'):<11} {d.get('reason', '')}")

    lib = v.context.library
    entries = lib.all()
    print(f"\nBibliotheek ({len(entries)} entries opgeslagen in data/library.json):")
    for w, entry in entries.items():
        print(f"  {w}: {entry['status']} — {entry['rationale'][:70]}")

    print("\n================ einde demo ================")


def harry_hemp_grounding_demo():
    """Demo: grond een paar lexicon-termen via OpenAlex, Semantic Scholar en OpenLibrary."""
    from nooch_village.skills_impl.openalex import OpenalexSkill
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
    from nooch_village.skills_impl.openlibrary_search_inside import OpenlibrarySearchInsideSkill

    v   = Village(heartbeat_seconds=86400)
    oa  = OpenalexSkill()
    ss  = SemanticScholarSkill()
    ol  = OpenlibrarySearchInsideSkill()
    lex = v.context.lexicon

    nl_terms = lex.words_for_lang("nl", status_filter="approved")[:3]
    en_terms = lex.words_for_lang("en", status_filter="approved")[:3]
    demo_pairs = [(t, "nl") for t in nl_terms] + [(t, "en") for t in en_terms]

    print("\n================ DEMO: Harry Hemp — lexicon-termen gronden ================")
    print(f"NL termen: {nl_terms}")
    print(f"EN termen: {en_terms}")
    print("(OpenAlex: 0.5s sleep; Semantic Scholar: 1s sleep + backoff bij 429)\n")

    for term, locale in demo_pairs:
        print(f"\n{'─'*60}")
        print(f"  {term}  [{locale}]")
        print(f"{'─'*60}")

        r_oa = oa.run({"term": term, "locale": locale, "limit": 3}, v.context)
        if "error" in r_oa:
            print(f"  OpenAlex  ✘  {r_oa['error']}")
        elif r_oa.get("no_data"):
            print(f"  OpenAlex  ℹ  geen werken gevonden  ({r_oa.get('reason','')})")
        else:
            print(f"  OpenAlex  ✔  {r_oa['total']:,} werken totaal")
            for h in r_oa["hits"]:
                topic = h.get("topic", "") or "—"
                print(f"    [{h['year'] or '?'}] {h['citations']:>6} cit.  "
                      f"{h['title'][:50]:<50}  topic: {topic[:35]}")

        r_ss = ss.run({"term": term, "locale": locale, "limit": 3}, v.context)
        if "error" in r_ss:
            print(f"  SemSchol  ✘  {r_ss['error']}")
        elif r_ss.get("no_data"):
            print(f"  SemSchol  ℹ  geen papers gevonden  ({r_ss.get('reason','')})")
        else:
            print(f"  SemSchol  ✔  {r_ss['total']:,} papers totaal")
            for h in r_ss["hits"]:
                tldr = h.get("tldr", "") or "(geen tldr)"
                print(f"    [{h['year'] or '?'}] {h['citations']:>6} cit.  "
                      f"{h['title'][:45]:<45}")
                print(f"          tldr: {tldr[:90]}")

        r_ol = ol.run({"term": term, "limit": 3}, v.context)
        if "error" in r_ol:
            print(f"  OpenLib   ✘  {r_ol['error']}")
        elif not r_ol.get("hits"):
            print(f"  OpenLib   ℹ  geen boeken gevonden")
        else:
            print(f"  OpenLib   ✔  {r_ol['total']:,} boeken totaal")
            for h in r_ol["hits"]:
                authors = ", ".join(h.get("authors", [])[:2]) or "?"
                print(f"    [{h['year'] or '?'}]  {h['title'][:50]:<50}  — {authors[:30]}")

    print("\n================ einde harry_hemp grounding demo ================")
