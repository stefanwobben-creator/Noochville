"""CLI-dispatcher voor `python -m nooch_village.village <mode>`."""
from __future__ import annotations
import sys


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if mode == "once":
        from nooch_village.village import once
        once()

    elif mode == "once-sandbox":
        from nooch_village.village import once_sandbox
        once_sandbox(keep="--keep" in sys.argv)

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

    elif mode == "discovery":
        from nooch_village.demos.ops import discovery_demo
        discovery_demo()

    elif mode == "kennis_migrate":
        # Geef de 196 bestaande kaartjes hun SOORT (signaal/bevinding/kader/standpunt).
        # Default = dry-run (toont het plan, verandert niets). 'apply' voert het door.
        # Conservatief: al-gezet blijft, definities → Lexicon, twijfel → mens-review.
        import os
        from nooch_village.config import load_context
        from nooch_village.notes_store import NotesStore
        from nooch_village.kennis_migrate import plan_migration, apply_plan
        from nooch_village.claim_classify import classify_kind
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        store = NotesStore(os.path.join(ctx.data_dir, "notes.json"))
        do_apply = "apply" in sys.argv[2:]
        use_llm = "nollm" not in sys.argv[2:]

        # Classifier: heuristiek, met LLM als rijkere terugval op de twijfelgevallen (mens-machine).
        # 'nollm' = puur heuristiek (snel, geen Gemini-calls; handig bij quota/overbelasting).
        def classify(claim, et, source):
            k = classify_kind(claim, et, source)
            if k is not None or not use_llm:
                return k
            try:
                from nooch_village.llm import reason
                prompt = ("Classificeer deze bewering in één woord: signaal (trend/mening), "
                          "bevinding (empirie), kader (norm/regel), standpunt (eigen claim), "
                          "of onbeslist. Antwoord met enkel dat woord.\n\nBewering: " + (claim or ""))
                ans = (reason(prompt) or "").strip().lower()
                from nooch_village.insight import ClaimKind
                for kk in ClaimKind:
                    if kk.value in ans:
                        return kk
            except Exception:
                pass
            return None

        plan = plan_migration(store.all(), classify=classify)
        s = plan["summary"]
        print(f"📚 Kennis-migratie ({'APPLY' if do_apply else 'DRY-RUN'}) over {s['totaal']} kaartjes")
        print(f"   al gezet (overslaan): {s['al_gezet']}")
        print(f"   toe te kennen: {s['toe_te_kennen']}")
        print(f"   definitie → Lexicon: {s['definitie_lexicon']}")
        print(f"   onbeslist → mens-review: {s['onbeslist_review']}")
        print()
        # toon een paar voorbeelden per categorie
        shown = 0
        for r in plan["rows"]:
            if r["proposed"] and shown < 12:
                print(f"   [{r['proposed']:<10}] {r['claim']}")
                shown += 1
        if s["onbeslist_review"]:
            print("\n   ⚠ onbeslist (blijven op jou wachten):")
            for r in plan["rows"]:
                if r["note"] == "onbeslist → mens-review":
                    print(f"      {r['claim']}")
        if do_apply:
            n = apply_plan(store, plan)
            print(f"\n✅ {n} kaartjes kregen hun soort. De rest (definitie/onbeslist) is met rust gelaten.")
        else:
            print("\n(DRY-RUN — niets gewijzigd. Draai 'kennis_migrate apply' om door te voeren.)")

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

    elif mode == "add_seed":
        import os
        from nooch_village.config import load_context
        from nooch_village.library import Library
        from nooch_village.village import BASE_DIR
        words = [a.strip() for a in sys.argv[2:] if a.strip()]
        if not words:
            print('Gebruik: python -m nooch_village.village add_seed "footwear" "fashion"',
                  file=sys.stderr)
            sys.exit(1)
        ctx = load_context(BASE_DIR)
        lib = Library(os.path.join(ctx.data_dir, "library.json"))
        for w in words:
            lib.curate(w, "approved", rationale="seed toegevoegd door de mens (volg-woord)",
                       by="founder")
            lib.set_function(w, "volg")                   # expliciet seed, ongeacht woordenaantal
            print(f"🌱 volg-woord toegevoegd: {w}")
        print("Draai 'enrich_volumes' om volume + 5-jaars trend op te halen voor de nieuwe seeds.")

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

    elif mode == "answer_questions":
        # Gebundelde beantwoording: alle openstaande mens-vragen aan rollen in één LLM-call
        # (het bovenliggende principe: geen realtime per-vraag-call, maar één puls-call).
        import os
        from nooch_village.config import load_context
        from nooch_village.human_inbox import HumanInbox
        from nooch_village.governance import Records
        from nooch_village.inbox_actions import answer_pending_questions
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        inbox = HumanInbox(os.path.join(ctx.data_dir, "human_inbox.json"))
        records = Records(os.path.join(ctx.data_dir, "governance_records.json"))
        pend = inbox.pending_questions()
        if not pend:
            print("Geen openstaande vragen.")
        else:
            print(f"💬 {len(pend)} openstaande vraag(en) — gebundeld beantwoorden…")
            res = answer_pending_questions(inbox, records=records)
            print(f"   {res['answered']} beantwoord, {res['pending']} blijft wachten "
                  f"(geen LLM of geen antwoord).")

    elif mode == "ingest_governance":
        # Parse een (vertrouwelijke) governance-export naar de lokale referentiebank.
        #   python -m nooch_village.village ingest_governance "<archetype>" pad/naar.pdf
        # Accumuleert over meerdere aanroepen (dedup). Blijft lokaal in data/ (gitignored).
        import os
        from nooch_village.config import load_context
        from nooch_village.governance_examples import GovernanceExamples, parse_governance_pdf
        from nooch_village.village import BASE_DIR
        args = sys.argv[2:]
        if len(args) < 2:
            print('Gebruik: ingest_governance "<archetype>" <pad.pdf> [pad2.pdf ...]',
                  file=sys.stderr)
            sys.exit(1)
        archetype, paths = args[0], args[1:]
        ctx = load_context(BASE_DIR)
        store = GovernanceExamples(os.path.join(ctx.data_dir, "governance_examples.json"))
        merged = store.all()
        seen = {(r["role"].lower(), r["purpose"].lower()) for r in merged}
        added = 0
        for p in paths:
            if not os.path.exists(p):
                print(f"  ⚠️ niet gevonden: {p}", file=sys.stderr)
                continue
            roles = parse_governance_pdf(p, archetype)
            for r in roles:
                k = (r["role"].lower(), r["purpose"].lower())
                if k not in seen:
                    seen.add(k); merged.append(r); added += 1
            print(f"  • {os.path.basename(p)} → {len(roles)} rollen geparsed")
        store.replace(merged)
        print(f"✅ Referentiebank: {added} nieuw, totaal {store.count()} rollen "
              f"(vertrouwelijk, lokaal in data/governance_examples.json).")

    elif mode == "sources":
        # Beheer de actief/inactief-status van databronnen (mens-gated activatie). De puls haalt
        # alleen ACTIEVE bronnen op. Gebruik: sources [list] | sources activate <bron> | sources deactivate <bron>
        import os
        from nooch_village.config import load_context
        from nooch_village.source_status import SourceStatusStore
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        store = SourceStatusStore(os.path.join(ctx.data_dir, "sources.json"))
        sub = sys.argv[2] if len(sys.argv) > 2 else "list"
        if sub in ("activate", "deactivate") and len(sys.argv) > 3:
            store.set_active(sys.argv[3], sub == "activate")
            print(f"{'✅ actief' if sub == 'activate' else '⏸️  inactief'}: {sys.argv[3]}")
        d = store.all()
        print("Databronnen (actief = puls haalt op):")
        for src in sorted(d):
            st = d[src]
            cfg = st.get("configured")
            cfg_s = "" if cfg is None else (" · creds ok" if cfg else " · GEEN creds")
            print(f"  {'●' if st.get('active') else '○'} {src}{cfg_s}")

    elif mode == "backfill":
        # Handmatige historische inhaal: haal per periode de historische dagwaarde op en schrijf 'm
        # idempotent weg (zelfde canonieke sleutel + record_daily als de collector → geen duplicaten,
        # botst niet met live-punten). Fase 1: alleen Plausible.
        # botst niet met live-punten). Fase 1: alleen daily-bronnen (plausible, gsc).
        # python -m nooch_village.village backfill <bron> <startdatum-YYYY-MM-DD>
        import os
        from nooch_village.config import load_context
        from nooch_village.observations import ObservationStore
        from nooch_village.backfill import backfill, BACKFILL_SOURCES, BackfillError
        from nooch_village.village import BASE_DIR
        args = sys.argv[2:]
        if len(args) < 2:
            print("Gebruik: python -m nooch_village.village backfill <bron> <startdatum-YYYY-MM-DD>",
                  file=sys.stderr)
            print("Bronnen: " + ", ".join(sorted(BACKFILL_SOURCES))
                  + "  (snapshot-bronnen zoals openalex/semanticscholar vallen buiten scope)",
                  file=sys.stderr)
            sys.exit(1)
        source, start = args[0], args[1]
        ctx = load_context(BASE_DIR)
        obs = ObservationStore(os.path.join(ctx.data_dir, "observations.jsonl"))
        factory = BACKFILL_SOURCES.get(source)
        if factory and not factory().is_configured(ctx):
            print(f"⚠️  '{source}' heeft geen (volledige) creds in .env — de historische calls leveren "
                  f"leeg op. Zet de creds en probeer opnieuw.", file=sys.stderr)

        def _progress(datum, w, s, leeg, n):
            if n % 30 == 0:
                print(f"   … {datum}  ({w} geschreven, {s} al aanwezig, {leeg} leeg)")
        try:
            print(f"⏪ Backfill {source} vanaf {start} t/m de laatste volledige dag …")
            res = backfill(source, start, obs, ctx, on_progress=_progress)
        except BackfillError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)
        if res.get("clamped"):
            print(f"ℹ️  Startdatum afgeklemd naar {res['start']} — '{source}' bewaart geen oudere historie.")
        print(f"✅ Backfill {source} {res['start']}..{res['end']} klaar: {res['written']} nieuw geschreven, "
              f"{res['skipped']} waren er al (idempotent), {res['lege_dagen']}/{res['dagen']} dagen leeg "
              f"(geen data/creds). Herdraaien is veilig.")

    elif mode == "shopify":
        # Haal verkoopindicatoren op uit Shopify en schrijf ze weg voor het cockpit-dashboard.
        import os, json
        from nooch_village.config import load_context
        from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
        from nooch_village.util import atomic_write_json
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        # Standaard: drie vensters in één fetch (7d / 30d / hele historie) voor de dashboard-toggle.
        # Eén getal meegeven → alleen dat venster (oud gedrag, handig in campagnetijd).
        one = next((int(a) for a in sys.argv[2:] if a.isdigit()), None)
        payload = {"window_days": one} if one is not None else {"windows": [0, 7, 30]}
        print("🛍️  Shopify-verkoop ophalen "
              f"({'7d/maand/hele historie' if one is None else (f'laatste {one} dagen' if one else 'hele historie')})…")
        res = ShopifySalesSkill().run(payload, ctx)
        if not res.get("ok"):
            print(f"   {res.get('error', 'onbekend')}", file=sys.stderr)
            sys.exit(1)
        atomic_write_json(os.path.join(ctx.data_dir, "shopify_metrics.json"), res)
        # De dag-observaties (pairs_sold/orders/revenue/aov) lopen nu via de generieke collector in de
        # puls (activeer met `sources activate shopify`), niet meer hier hardcoded.
        print(f"✅ {res['pairs_sold']} paar verkocht · {res['orders']} orders · "
              f"{res['revenue']} {res['currency']} omzet (AOV {res['aov']}"
              f", gem. {res.get('avg_pairs_month', 0)} paar/maand). Dashboard staat in de cockpit.")

    elif mode == "montecarlo":
        # Stresstest de governance-kern: honderden gerandomiseerde rolvoorstellen door Gate+Secretary.
        from nooch_village.montecarlo import run, format_report
        nums = [int(a) for a in sys.argv[2:] if a.isdigit()]
        n = nums[0] if nums else 500
        seed = nums[1] if len(nums) > 1 else 0
        print(format_report(run(n, seed=seed)))

    elif mode == "work_projects":
        # Rollen werken (omkeerbaar, met eigen skills) aan hun queued projecten.
        import os
        from nooch_village.config import load_context
        from nooch_village.projects import ProjectLedger
        from nooch_village.governance import Records
        from nooch_village.project_worker import work_projects
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        limit = next((int(a) for a in sys.argv[2:] if a.isdigit()), 5)
        ledger = ProjectLedger(os.path.join(ctx.data_dir, "projects.json"))
        recs = Records(os.path.join(ctx.data_dir, "governance_records.json"))
        from nooch_village.personas import PersonaStore
        personas = PersonaStore(os.path.join(ctx.data_dir, "personas.json"))
        print(f"🛠️  Rollen werken aan hun omkeerbare projecten (max {limit})…")
        res = work_projects(ledger, recs, limit=limit, personas=personas)
        print(f"✅ {res['worked']} uitgevoerd, {res['blocked']} geblokkeerd (vragen jouw oordeel), "
              f"{res['skipped']} wachten op een volgende ronde. Zie het projectbord in de cockpit.")

    elif mode in ("inwoner_new", "inwoner_list", "inwoner_assign"):
        # Inwoners (persona's): The Source maakt karakters aan en koppelt ze aan rollen.
        # Skills/rugzak blijven van de rol; de inwoner kleurt alleen de toon.
        import os
        from nooch_village.config import load_context
        from nooch_village.personas import PersonaStore
        from nooch_village.governance import Records
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        personas = PersonaStore(os.path.join(ctx.data_dir, "personas.json"))
        if mode == "inwoner_new":
            # village inwoner_new <naam> <MBTI> <instructies...>
            if len(sys.argv) < 3:
                print("Gebruik: village inwoner_new <naam> [MBTI] [instructies...]", file=sys.stderr)
                sys.exit(1)
            naam = sys.argv[2]
            mbti = sys.argv[3] if len(sys.argv) > 3 else ""
            instr = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
            p = personas.add(naam, mbti=mbti, instructions=instr)
            print(f"🧑 Inwoner aangemaakt: {p.name} ({p.mbti or 'geen MBTI'}) — id={p.id}")
            if instr:
                print(f"   instructies: {p.instructions}")
            print("   Koppel aan een rol: village inwoner_assign <role_id> " + p.id)
        elif mode == "inwoner_list":
            recs = Records(os.path.join(ctx.data_dir, "governance_records.json"))
            seated = {}
            for r in recs.all():
                if getattr(r, "persona_id", None):
                    seated.setdefault(r.persona_id, []).append(r.id)
            items = personas.all()
            if not items:
                print("Nog geen inwoners. Maak er een: village inwoner_new <naam> <MBTI> <instructies>")
            for p in items:
                rollen = ", ".join(seated.get(p.id, [])) or "— (niet gekoppeld)"
                print(f"  {p.name:<16} {p.mbti or '----':<6} id={p.id}  → rol: {rollen}")
                if p.instructions:
                    print(f"      {p.instructions[:80]}")
        else:  # inwoner_assign
            # village inwoner_assign <role_id> <persona_id|->   ('-' = ontkoppelen)
            if len(sys.argv) < 4:
                print("Gebruik: village inwoner_assign <role_id> <persona_id|->", file=sys.stderr)
                sys.exit(1)
            role_id, pid = sys.argv[2], sys.argv[3]
            recs = Records(os.path.join(ctx.data_dir, "governance_records.json"))
            if recs.get(role_id) is None:
                print(f"Rol '{role_id}' bestaat niet.", file=sys.stderr); sys.exit(1)
            if pid == "-":
                recs.set_persona(role_id, None)
                print(f"🔌 Rol '{role_id}' ontkoppeld van zijn inwoner.")
            elif personas.get(pid) is None:
                print(f"Inwoner '{pid}' bestaat niet (zie: village inwoner_list).", file=sys.stderr)
                sys.exit(1)
            else:
                recs.set_persona(role_id, pid)
                p = personas.get(pid)
                print(f"🪑 {p.name} ({p.mbti or 'geen MBTI'}) zit nu in de rol '{role_id}'. "
                      f"De rugzak (skills) blijft van de rol; {p.name} kleurt de toon.")

    elif mode == "review_roles":
        # Facilitator-project: review alle dorp-rollen tegen de Holacracy-regels + referentiebank,
        # en zet per rol één verbetervoorstel als kans in de inbox (mens-gated, niks auto-toegepast).
        import os
        from nooch_village.config import load_context
        from nooch_village.governance import Records
        from nooch_village.governance_examples import GovernanceExamples
        from nooch_village.governance_review import review_all_roles
        from nooch_village.human_inbox import HumanInbox
        from nooch_village.village import BASE_DIR
        ctx = load_context(BASE_DIR)
        recs = Records(os.path.join(ctx.data_dir, "governance_records.json"))
        ge = GovernanceExamples(os.path.join(ctx.data_dir, "governance_examples.json"))
        inbox = HumanInbox(os.path.join(ctx.data_dir, "human_inbox.json"))
        print(f"🏛️ Facilitator reviewt alle rollen (referentiebank: {ge.count()} voorbeeldrollen)…")
        res = review_all_roles(recs, ge, inbox)
        print(f"✅ {res['reviewed']} rollen gereviewd, {res['proposed']} verbetervoorstel(len) "
              f"als kans in je inbox (verwerk ze in de focus-triage). {res['skipped']} overgeslagen "
              f"(kernrollen/cirkels).")
        if ge.count() == 0:
            print("   ⚠️ Referentiebank leeg — draai eerst 'ingest_governance' voor grounding.")

    else:
        print(f"Onbekende mode '{mode}'. Geldige modes: "
              "once | run | demo | librarian | governance | proposal | lifecycle | "
              "purge | intent | triage | ngram | reflect | simulate | harry_hemp | "
              "content_strategist | grant_serpapi_trends | grant_skill | revoke_skill | "
              "remove_role | seat_human | upgrade_harry_role | ask_accountability | "
              "measure_propose | rereview | ingest | notes_remove | recurate | "
              "ground | harry_run | roster | keys | competitor | formalize | answer_questions | "
              "ingest_governance | review_roles | shopify | work_projects | "
              "inwoner_new | inwoner_list | inwoner_assign | kennis_migrate | sources | shopify | backfill",
              file=sys.stderr)
        sys.exit(1)
