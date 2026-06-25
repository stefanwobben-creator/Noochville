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

    elif mode == "ground":
        # Demo/utility: voer Harry een paar termen en laat ze in ÉÉN gebundelde
        # LLM-call gronden. Toont de batching-hefboom + de grounds-op-kaartjes live.
        import time
        from nooch_village.event_bus import Event
        from nooch_village.village import Village
        words = sys.argv[2:]
        if not words:
            print("Gebruik: python -m nooch_village.village ground <woord> [woord ...]",
                  file=sys.stderr)
            sys.exit(1)
        v = Village(heartbeat_seconds=86400)
        seen: list[str] = []
        v.bus.subscribe("keyword_evidence", lambda e: seen.append(e.data["word"]))
        v.start()
        harry = v.reconciler.live.get("harry_hemp")
        if harry is None:
            print("HarryHemp niet actief in het dorp.", file=sys.stderr)
            v.stop(); sys.exit(1)
        # Forceer bundeling: flush precies wanneer alle termen binnen zijn (één call).
        harry._batch_size = len(words)
        print(f"\nHarry grondt {len(words)} term(en) in één gebundelde call: "
              f"{', '.join(words)}")
        print("Wacht op OpenAlex/Semantic Scholar + de LLM (kan ~30-90s)…\n")
        for w in words:
            v.bus.publish(Event("keyword_proposed",
                                {"word": w, "demand": {"locale": "en"}}, "the_source"))
        deadline = time.time() + 180
        while time.time() < deadline and len(set(seen)) < len(words):
            time.sleep(0.3)
        time.sleep(2.0)   # geef de Librarian even om de kaarten te schrijven
        v.stop()
        notes = v.context.notes
        print("\n── grounding-kaartjes (claim + grounds) ──")
        for w in words:
            card = next((n for n in notes.all() if n.word == w), None)
            if card:
                print(f"  ✔ {w}  (id={card.id}, grounding_count={card.grounding_count})")
                print(f"      claim:   {card.claim[:90]}")
                print(f"      grounds: {(card.grounds or '(leeg!)')[:90]}")
            else:
                print(f"  ✗ {w}: geen kaartje geschreven (LLM weg of niets gevonden)")

    elif mode == "harry_run":
        # Eenmalige opdracht aan Harry op eigen termen: ngram-richting + lange-boog-verbanden
        # (co-beweging/substitutie) + gekalibreerde OpenAlex-voortzetting voorbij de cutoff.
        import time
        from nooch_village.event_bus import Event
        from nooch_village.village import Village
        terms = sys.argv[2:] or ["consumer", "citizen"]
        v = Village(heartbeat_seconds=86400)
        v.context.settings["tijdgeest_interval_seconds"] = "0"
        pulse, cors, conts = {}, [], []
        v.bus.subscribe("tijdgeest_pulse_completed", lambda e: pulse.update(e.data))
        v.bus.subscribe("tijdgeest_correlatie",      lambda e: cors.extend(e.data.get("bevindingen", [])))
        v.bus.subscribe("tijdgeest_voortzetting",    lambda e: conts.extend(e.data.get("reports", [])))
        v.start()
        if "harry_hemp" not in v.reconciler.live:
            print("HarryHemp niet actief in het dorp.", file=sys.stderr); v.stop(); sys.exit(1)
        print(f"\nHarry draait ngram + verbanden + OpenAlex-voortzetting voor: {', '.join(terms)}")
        print("Wacht op Google Books Ngram + OpenAlex (kan ~30-60s duren)…\n")
        # De mens vraagt als houder van the_source (spelregel 5).
        v.bus.publish(Event("tijdgeest_pulse", {"terms": terms}, "the_source"))
        for _ in range(1200):
            if pulse:
                break
            time.sleep(0.1)
        time.sleep(0.5)
        v.stop()
        if not pulse.get("ok"):
            print(f"Puls mislukt: {pulse.get('error', 'onbekend')}"); sys.exit(1)
        print("── ngram-richting ──")
        for r in pulse.get("rows", []):
            if r.get("no_data"):
                print(f"  {r['term']:<22} geen data ({r.get('reason', '')})")
            else:
                s = r.get("signal", {})
                print(f"  {r['term']:<22} {s.get('direction', '?'):<10} (recente helling {s.get('slope_recent')})")
        print("\n── lange-boog-verbanden ──")
        for c in cors or []:
            print(f"  {c['label']}: '{c['a']}' ~ '{c['b']}' (r={c['r']}, {c['n']} jaar)")
        if not cors:
            print("  (geen sterk verband gevonden)")
        print("\n── voortzetting voorbij de cutoff (OpenAlex-proxy) ──")
        for ct in conts or []:
            cal = ct["calibration"]; jaren = sorted(ct["arc"])
            print(f"  {ct['term']:<22} kalibratie r={cal.get('r')} ({cal.get('n')} jaar overlap); "
                  f"boog t/m {jaren[-1] if jaren else '?'}")
        if not conts:
            print("  (geen vertrouwde voortzetting; OpenAlex correleerde onvoldoende met ngram)")

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

    elif mode == "ask_accountability":
        import time
        from nooch_village.event_bus import Event
        from nooch_village.village import Village
        if len(sys.argv) < 4:
            print("Gebruik: python -m nooch_village.village ask_accountability <rol> <accountability>",
                  file=sys.stderr)
            sys.exit(1)
        target, key = sys.argv[2], sys.argv[3]
        v = Village(heartbeat_seconds=86400)
        done = {}
        v.bus.subscribe("nl_corpus_check_completed", lambda e: done.update(e.data))
        v.bus.subscribe("accountability_check_completed", lambda e: done.update(e.data))
        v.start()
        time.sleep(0.3)
        # de mens vraagt als houder van the_source (spelregel 5)
        v.bus.publish(Event("accountability_requested",
            {"target": target, "accountability": key, "payload": {}, "from": "the_source"}, "the_source"))
        for _ in range(600):              # max ~60s (verse fetch kan even duren)
            if done:
                break
            time.sleep(0.1)
        v.stop()
        if done:
            print(f"Antwoord van '{target}' op '{key}': {done}")
        else:
            print(f"Geen antwoord binnen de tijd (rol biedt '{key}' misschien niet aan, "
                  f"of de check duurde te lang).")

    elif mode == "seat_human":
        import os
        from nooch_village.config import load_context
        from nooch_village.governance import Records
        from nooch_village.village import BASE_DIR
        if len(sys.argv) < 4:
            print("Gebruik: python -m nooch_village.village seat_human <role_id> <naam>",
                  file=sys.stderr)
            sys.exit(1)
        role_id, naam = sys.argv[2], " ".join(sys.argv[3:])
        ctx = load_context(BASE_DIR)
        records = Records(os.path.join(ctx.data_dir, "governance_records.json"))
        if records.set_holder(role_id, naam):
            rec = records.get(role_id)
            print(f"Zetel vastgelegd: '{role_id}' wordt bezet door {rec.held_by} (mens).")
            print(f"  purpose: {rec.definition.purpose[:70]}")
        else:
            print(f"Rol '{role_id}' bestaat niet.", file=sys.stderr)
            sys.exit(1)

    elif mode == "upgrade_harry_role":
        from nooch_village.role_proposals import upgrade_harry_role
        upgrade_harry_role()

    elif mode == "formalize":
        from nooch_village.role_proposals import formalize_session_governance
        formalize_session_governance()

    elif mode == "grant_skill":
        from nooch_village.role_proposals import grant_skill_via_governance
        if len(sys.argv) < 4:
            print("Gebruik: python -m nooch_village.village grant_skill <role_id> <skill>",
                  file=sys.stderr)
            sys.exit(1)
        grant_skill_via_governance(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))

    elif mode == "grant_accountability":
        from nooch_village.role_proposals import grant_accountability_via_governance
        if len(sys.argv) < 4:
            print("Gebruik: python -m nooch_village.village grant_accountability <role_id> <accountability>",
                  file=sys.stderr)
            sys.exit(1)
        grant_accountability_via_governance(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))

    elif mode == "revoke_skill":
        from nooch_village.role_proposals import revoke_skill_via_governance
        if len(sys.argv) < 4:
            print("Gebruik: python -m nooch_village.village revoke_skill <role_id> <skill>",
                  file=sys.stderr)
            sys.exit(1)
        revoke_skill_via_governance(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]))

    elif mode == "remove_role":
        from nooch_village.role_proposals import remove_role_via_governance
        if len(sys.argv) < 3:
            print("Gebruik: python -m nooch_village.village remove_role <role_id> [reden]",
                  file=sys.stderr)
            sys.exit(1)
        remove_role_via_governance(sys.argv[2], " ".join(sys.argv[3:]))

    elif mode == "enrich_volumes":
        import os
        from nooch_village.config import load_context
        from nooch_village.library import Library
        from nooch_village.library_enrich import enrich_library
        from nooch_village.village import BASE_DIR
        dry = "dry" in sys.argv[2:]
        use_gsc = "nogsc" not in sys.argv[2:]
        ctx = load_context(BASE_DIR)
        ctx.library = Library(os.path.join(ctx.data_dir, "library.json"))
        out = enrich_library(ctx.library, ctx, apply=not dry, gsc=use_gsc)
        if out["gsc_error"]:
            print(f"⚠️ GSC niet beschikbaar ({out['gsc_error']}) — alleen volume/concurrentie/kans.")
        rows = sorted(out["results"],
                      key=lambda r: -(r.get("opportunity") if r.get("opportunity") is not None else -1))
        print(f"{'DROOGDRAAI (niets weggeschreven)' if dry else 'Verrijkt'} — "
              f"{len(rows)} goedgekeurde woorden (op kans):")
        for r in rows:
            vol = "" if r.get("volume") is None else f'{r["volume"]}/mnd'
            comp = "" if r.get("competition") is None else f'{round(float(r["competition"])*100)}%'
            opp = "" if r.get("opportunity") is None else str(r["opportunity"])
            if r.get("gsc_seen") is True:
                stand = f'positie {r.get("gsc_position")} ({r.get("gsc_clicks") or 0} klik)'
            elif r.get("gsc_seen") is False:
                stand = "nog niet in Google"
            else:
                stand = "—"
            print(f'  {r["word"][:38]:38} vol {vol:>10}  kans {opp:>8}  '
                  f'ad-conc {comp:>5}  {stand}')
        if dry:
            print("\nDraai zonder 'dry' om dit echt weg te schrijven.")

    elif mode == "synthesize":
        import os
        from nooch_village.config import load_context
        from nooch_village.notes_store import NotesStore
        from nooch_village.synthesist import synthesize_round, density
        from nooch_village.village import BASE_DIR
        n = next((int(a) for a in sys.argv[2:] if a.isdigit()), 3)
        ctx = load_context(BASE_DIR)
        notes = NotesStore(os.path.join(ctx.data_dir, "notes.json"))
        ctx.notes = notes
        d0 = density(notes)
        print(f"Kennisgraaf vóór: {d0['cards']} kaartjes, {d0['links']} links, "
              f"gem. gelijkenis {d0['avg_similarity']}")
        made = synthesize_round(notes, ctx, n)
        if not made:
            print("Geen nieuwe creatieve links (geen bridge-paar of geen LLM).")
        for m in made:
            print(f"  🔗 {m['synthese'][:80]}  (uit {m['parents'][0]} + {m['parents'][1]})")
        d1 = density(notes)
        print(f"Kennisgraaf ná: {d1['cards']} kaartjes, {d1['links']} links, "
              f"gem. gelijkenis {d1['avg_similarity']}")

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

    elif mode == "notes_remove":
        import os
        from nooch_village.config import load_context
        from nooch_village.notes_store import NotesStore
        from nooch_village.village import BASE_DIR
        if len(sys.argv) < 3:
            print("Gebruik: python -m nooch_village.village notes_remove <id> [id ...]",
                  file=sys.stderr)
            sys.exit(1)
        ctx = load_context(BASE_DIR)
        notes = NotesStore(os.path.join(ctx.data_dir, "notes.json"))
        for nid in sys.argv[2:]:
            print(("  − verwijderd: " if notes.remove(nid) else "  = niet gevonden: ") + nid)

    elif mode == "recurate":
        import os
        from nooch_village.config import load_context
        from nooch_village.notes_store import NotesStore
        from nooch_village.curate_migrate import recurate_cards
        from nooch_village.village import BASE_DIR
        if len(sys.argv) < 3:
            print("Gebruik: python -m nooch_village.village recurate <card_id> [card_id ...]",
                  file=sys.stderr)
            print("Haalt elk kaartje opnieuw door de curator (Engels + atomair) via de LLM.",
                  file=sys.stderr)
            sys.exit(1)
        ctx = load_context(BASE_DIR)
        notes = NotesStore(os.path.join(ctx.data_dir, "notes.json"))
        print("Her-curatie via de curator (LLM):")
        for r in recurate_cards(notes, sys.argv[2:]):
            if r["replaced"]:
                print(f"  ✔ {r['card_id']} → {r['new_ids']}")
            else:
                print(f"  ✗ {r['card_id']}: {r['reason']}")

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

    elif mode == "keys":
        from nooch_village.village import Village
        v = Village(heartbeat_seconds=86400)
        print(v.report_keys())

    elif mode == "competitor":
        import os
        from nooch_village.config import load_context
        from nooch_village.competitor_brands import CompetitorBrands
        from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill
        from nooch_village.skills_impl.competitor_discover import CompetitorDiscoverSkill
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        store = CompetitorBrands(os.path.join(ctx.data_dir, "competitor_brands.json"))
        raw = (ctx.settings.get("competitor_brands", "") or "")
        monitored = list(dict.fromkeys(
            [b.strip() for b in raw.split(",") if b.strip()] + store.confirmed()))
        print("🔭 Concurrent-scan draait (Google News RSS per merk)…")
        res = CompetitorNewsSkill().run({"brands": monitored} if monitored else {}, ctx)
        if not res.get("ok"):
            print(f"Scan mislukt: {res.get('error', 'onbekend')}", file=sys.stderr)
            sys.exit(1)
        print(f"✅ Rapport: {res['path']}")
        print(f"   {res['total']} updates over {len(res['brands'])} merken: {', '.join(res['brands'])}")
        if res.get("errors"):
            print(f"   ⚠️ merken met fouten: {list(res['errors'])}")
        # Ontdekking: spot nieuwe merken en zet ze (deduped) klaar voor jouw oordeel
        print("🔮 Scannen op nieuwe/aanverwante merken…")
        disc = CompetitorDiscoverSkill().run({"brands": monitored}, ctx)
        if disc.get("ok"):
            added = [c["brand"] for c in disc.get("candidates", [])
                     if store.add_candidate(c.get("brand", ""), c.get("article", ""), c.get("link", ""))]
            if added:
                print(f"   {len(added)} nieuw gespot (wacht op je oordeel in de cockpit): {', '.join(added)}")
            else:
                print("   geen nieuwe merken gespot")
        else:
            print(f"   ontdekking overgeslagen: {disc.get('error', 'onbekend')}")
        # Linkbuilding: gidsen/lijstjes waar Nooch in vermeld wil worden
        from nooch_village.link_targets import LinkTargets
        from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
        print("🔗 Scannen op linkbuilding-doelwitten…")
        lt = LinkbuildingTargetsSkill().run({"brands": monitored}, ctx)
        if lt.get("ok"):
            lstore = LinkTargets(os.path.join(ctx.data_dir, "linkbuilding_targets.json"))
            new = [t for t in lt.get("targets", [])
                   if lstore.add_candidate(t.get("link", ""), t.get("title", ""),
                                           t.get("source", ""), t.get("priority", "onbekend"))]
            hoog = sum(1 for t in new if t.get("priority") == "hoog")
            print(f"   {len(new)} nieuw doelwit(ten), waarvan {hoog} hoge prioriteit (zie cockpit)")
        else:
            print(f"   linkbuilding overgeslagen: {lt.get('error', 'onbekend')}")

    else:
        print(f"Onbekende mode '{mode}'. Geldige modes: "
              "once | run | demo | librarian | governance | proposal | lifecycle | "
              "purge | intent | triage | ngram | reflect | simulate | harry_hemp | "
              "content_strategist | grant_serpapi_trends | grant_skill | revoke_skill | "
              "remove_role | seat_human | upgrade_harry_role | ask_accountability | "
              "measure_propose | rereview | ingest | notes_remove | recurate | "
              "ground | harry_run | roster | keys | competitor | formalize",
              file=sys.stderr)
        sys.exit(1)
