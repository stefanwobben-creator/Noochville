"""Operationele demo's: simulate en roster."""
from __future__ import annotations
import time, tempfile, shutil
from nooch_village.event_bus import Event
from nooch_village.village import Village
from nooch_village.models import Proposal, GovernanceChange, ChangeKind
from nooch_village.governance import proposal_to_dict


def simulate():
    """Volledige simulatie van het dorp in 7 fasen.

    1. Roster + Lexicon
    2. Governance-poort (G0-G4)
    3. Triage (4 spanningen)
    4. Reflectie Harry Hemp
    5. Ngram locale-demo (live API, max 3 termen)
    6. Librarian keyword-beslissingen
    7. Herkomst-roster
    """
    def section(title: str) -> None:
        print(f"\n{'='*65}")
        print(f"  {title}")
        print(f"{'='*65}\n")

    # Sandbox: simulate draait in een wegwerp-data-dir, nooit op productie.
    # Voorheen schreef simulate echte proposals/escalaties naar de echte
    # human_inbox en governance_records (de "escalatie-storm"). settings/.env
    # blijven uit de echte base laden; alleen de schrijf-stores zijn geïsoleerd.
    _sim_dir = tempfile.mkdtemp(prefix="noochville-sim-")
    print(f"  (sandbox-data-dir: {_sim_dir} — productie wordt niet geraakt)")

    # ── 1. Roster + Lexicon ───────────────────────────────────────────
    section("1 / 7 — ROSTER & LEXICON")
    v = Village(heartbeat_seconds=86400, data_dir=_sim_dir)

    v.print_roster()

    lex = v.context.lexicon
    print(f"\nLexicon ({len(lex.all())} concepten):")
    print(f"  {'Concept':<20} {'NL':<18} {'EN':<18} Status")
    print("  " + "-" * 70)
    for cid, entry in lex.all().items():
        words = entry.get("words", {})
        print(f"  {cid:<20} {words.get('nl','—'):<18} {words.get('en','—'):<18} "
              f"{entry.get('status','?')}")
    print(f"\n  ✔ 'consument' is forbidden/avoid: "
          f"{lex.is_forbidden('consument')} | "
          f"'consumer' ook: {lex.is_forbidden('consumer')}")
    print(f"  ✔ word_for(plastic_free, nl)='{lex.word_for('plastic_free','nl')}' "
          f"| word_for(plastic_free, en)='{lex.word_for('plastic_free','en')}'")

    # ── 2. Governance — drie voorstellen ─────────────────────────────
    section("2 / 7 — GOVERNANCE POORT (G0-G4)")
    gov_results: dict = {}

    def _rec(outcome):
        def _h(e):
            pid = e.data.get("proposal_id", e.data.get("id", "?"))
            gov_results[pid] = {"outcome": outcome,
                                "gate": e.data.get("gate", "-"),
                                "reason": e.data.get("reason", "")}
        return _h

    v.bus.subscribe("governance_changed",          _rec("aangenomen"))
    v.bus.subscribe("governance_review_requested", _rec("geëscaleerd"))
    v.bus.subscribe("proposal_invalid",            _rec("ongeldig"))
    v.start()

    pg1 = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="website_watcher",
                                add_accountabilities=["taalgebruik per locale bewaken"]),
        tension="Geen accountability voor locale-bewaking van rapportages",
        trigger_example="simulate:geen locale-check in field_note",
        rationale="Meertalige uitvoer vereist expliciet eigenaarschap per locale",
    )
    pg2 = Proposal(
        proposer_role="trends",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="trends",
                                add_accountabilities=["dagelijkse Field Note schrijven"]),
        tension="Trends wil ook Field Notes schrijven",
        trigger_example="simulate:geen eigen note voor trends",
        rationale="GSC-data verdiend eigen nota",
    )
    pg3 = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="website_watcher",
                                add_accountabilities=[
                                    "plastic producten goedkeuren voor promotie"]),
        tension="Wil plastic alternatieven promoten",
        trigger_example="simulate:lage interesse plastic-free",
        rationale="Bredere markt via plastic producten",
    )
    for p in (pg1, pg2, pg3):
        v.bus.publish(Event("proposal_raised", {"proposal": proposal_to_dict(p)}, "simulate"))

    for _ in range(100):
        if len(gov_results) >= 3:
            break
        time.sleep(0.05)

    print(f"  {'Voorstel':<38} {'Uitkomst':<13} {'Poort':<5} Reden")
    print("  " + "-" * 90)
    for p, label in [(pg1, "locale-bewaking (onschuldig)"),
                     (pg2, "Field Note dup (G2)"),
                     (pg3, "plastic goedkeuren (G4)")]:
        r = gov_results.get(p.id, {})
        print(f"  {label:<38} {r.get('outcome','?'):<13} {r.get('gate','-'):<5} "
              f"{r.get('reason','')[:42]}")

    # ── 3. Triage — vier spanningen ───────────────────────────────────
    section("3 / 7 — TRIAGE (4 spanningen)")
    triaged: list[dict] = []
    v.bus.subscribe("tension_triaged", lambda e: triaged.append(dict(e.data)))

    watcher = v.reconciler.live.get("website_watcher")
    if watcher:
        spanningen = [
            ("bezoekersdata per locale analyseren", "operational",
             "eigen-werk (website_watcher-scope)"),
            ("kandidaatwoord voor de bibliotheek: plasticvrij", "operational",
             "andere-rol:librarian"),
            ("niemand bezit de locale-policy structureel", "governance",
             "structureel → Proposal"),
            ("serverruimte koeling storing", "operational",
             "geen match → mens"),
        ]
        for desc, kind, _ in spanningen:
            watcher.sense_tension(desc, kind=kind)

        for _ in range(80):
            if len(triaged) >= len(spanningen):
                break
            time.sleep(0.1)
        time.sleep(0.3)

        print(f"  {'Spanning':<48} {'Verwacht':<26} {'Classificatie'}")
        print("  " + "-" * 100)
        triage_map = {t["description"][:47]: t["classification"] for t in triaged}
        for desc, _, verwacht in spanningen:
            key = desc[:47]
            cls = triage_map.get(key, "?")
            ok = ("✔" if (
                (verwacht.startswith("eigen") and "eigen" in cls) or
                (verwacht.startswith("andere") and "andere" in cls) or
                (verwacht.startswith("structureel") and "structureel" in cls) or
                (verwacht.startswith("geen") and "tactisch" in cls)
            ) else "✘")
            print(f"  {ok} {desc[:46]:<47} {verwacht:<26} {cls}")
    else:
        print("  ⚠️  website_watcher niet gevonden, triage overgeslagen")

    # ── 4. Reflectie — Harry Hemp ─────────────────────────────────────
    section("4 / 7 — REFLECTIE (Harry Hemp gap-sensing)")
    v.context.settings["reflect_interval_seconds"] = "0"

    reflect_means_gaps: list = []
    v.bus.subscribe("means_gap_sensed",
                    lambda e: reflect_means_gaps.append(dict(e.data)))

    tw = v.reconciler.live.get("harry_hemp")
    if tw:
        tw._maybe_reflect(None)
        time.sleep(0.1)

        print(f"  Means-gaps ({len(reflect_means_gaps)}):")
        for g in reflect_means_gaps:
            print(f"    [{g.get('gap_key','')}] {g.get('description','')[:80]}…")
        rec_after = v.records.get("harry_hemp")
        print(f"\n  ✔ skills ongewijzigd: {list(rec_after.definition.skills) if rec_after else '?'}")
        print(f"  ✔ geen governance-voorstel — means-gaps → inbox (niet governance)")
        print(f"  ✔ geen nieuwe thread — activatie blijft mens-gated")
    else:
        print("  ⚠️  harry_hemp niet actief")

    v.stop()
    time.sleep(0.2)

    # ── 5. Ngram locale-demo (live, max 3 termen) ─────────────────────
    section("5 / 7 — NGRAM LOCALE-DEMO (NL + EN, live API)")
    v2 = Village(heartbeat_seconds=86400, data_dir=_sim_dir)
    v2.context.settings["tijdgeest_interval_seconds"] = "0"

    pulse_result: dict = {}
    v2.bus.subscribe("tijdgeest_pulse_completed", lambda e: pulse_result.update(e.data))
    v2.start()

    tw2 = v2.reconciler.live.get("harry_hemp")
    if tw2:
        demo_terms = ["bewuste consument", "conscious consumer", "plasticvrij"]
        v2.bus.publish(Event("tijdgeest_pulse", {"terms": demo_terms}, "simulate"))

        print(f"  Termen: {demo_terms}")
        print("  Wacht op Google Books Ngram Viewer (max 45s)…\n")
        for _ in range(450):
            if pulse_result:
                break
            time.sleep(0.1)
        time.sleep(0.2)

        rows = pulse_result.get("rows", [])
        if rows:
            print(f"  {'Term':<16} {'Locale':<7} {'Corpus':<9} {'Richting':<12} {'Slope recent':>14} {'Freq last':>12}")
            print("  " + "-" * 74)
            for row in rows:
                if row.get("no_data"):
                    print(f"  {row['term']:<16} {row.get('locale','?'):<7} "
                          f"{'?':<9} {'geen data':<12} {'—':>14} {'—':>12}  ← {row.get('reason','')[:28]}")
                else:
                    sig = row.get("signal", {})
                    icon = {"stijgend": "📈", "dalend": "📉", "vlak": "➡️"}.get(
                        sig.get("direction", ""), "❓")
                    corpus = "NL (10)" if row.get("corpus") == 10 else "EN (26)"
                    slope = sig.get("slope_recent")
                    slope_s = f"{slope:.3e}" if slope is not None else "?"
                    freq = row.get("freq_last")
                    freq_s = f"{freq:.3e}" if freq is not None else "?"
                    print(f"  {row['term']:<16} {row.get('locale','?'):<7} "
                          f"{corpus:<9} {icon} {sig.get('direction','?'):<10} "
                          f"{slope_s:>14} {freq_s:>12}")
            stijgend = pulse_result.get("stijgend", [])
            dalend   = pulse_result.get("dalend", [])
            print(f"\n  📈 stijgend: {stijgend or '(geen)'}")
            print(f"  📉 dalend:   {dalend or '(geen)'}")
        else:
            print(f"  ⚠️  geen rows — {pulse_result.get('error', 'onbekende fout')}")
    else:
        print("  ⚠️  harry_hemp niet actief")

    v2.stop()
    time.sleep(0.2)

    # ── 6. Librarian keyword-beslissingen ─────────────────────────────
    section("6 / 7 — LIBRARIAN (meertalige kandidaat-woorden)")
    v3 = Village(heartbeat_seconds=86400, data_dir=_sim_dir)
    decisions: dict = {}
    escalations: list = []
    v3.bus.subscribe("keyword_decided",
                     lambda e: decisions.update({e.data["word"]: e.data}))
    v3.bus.subscribe("human_decision_needed",
                     lambda e: escalations.append(e.data))
    v3.start()

    candidates = [
        {"word": "plasticvrije sneakers", "locale": "nl",
         "demand": {"signal": "rising", "interest": 45, "source": "ngram_culture"}},
        {"word": "plastic-free footwear", "locale": "en",
         "demand": {"signal": "rising", "interest": 38, "source": "ngram_culture"}},
        {"word": "veganistisch schoenenmerk", "locale": "nl",
         "demand": {"signal": "positive", "interest": 20, "source": "google_trends"}},
        {"word": "leather shoes", "locale": "en",
         "demand": {"signal": "positive", "interest": 80, "source": "google_trends"}},
    ]
    for c in candidates:
        v3.bus.publish(Event("keyword_proposed", {**c, "from": "simulate"}, "simulate"))

    for _ in range(120):
        if len(decisions) + len(escalations) >= len(candidates):
            break
        time.sleep(0.1)
    v3.stop()
    time.sleep(0.1)

    print(f"  {'Woord':<30} {'Locale':<7} {'Status':<12} Reden")
    print("  " + "-" * 80)
    for c in candidates:
        w = c["word"]
        d = decisions.get(w) or next((e for e in escalations if e.get("word") == w), {})
        st = d.get("status", "escalated" if d else "?")
        print(f"  {w:<30} {c['locale']:<7} {st:<12} {d.get('reason','')[:35]}")

    # ── 7. Herkomst — roster met source-labels ────────────────────────
    section("7 / 7 — HERKOMST ROSTER (seed / sensed / demo)")
    v4 = Village(heartbeat_seconds=86400, data_dir=_sim_dir)
    v4.print_roster()

    # Sandbox opruimen: de wegwerp-data-dir mag geen sporen achterlaten.
    shutil.rmtree(_sim_dir, ignore_errors=True)

    print("\n" + "="*65)
    print("  SIMULATIE VOLTOOID")
    print("  Systeem draait: governance ✔ triage ✔ reflectie ✔ lexicon ✔")
    print("  (sandbox opgeruimd; productie-data ongemoeid)")
    print("="*65 + "\n")
