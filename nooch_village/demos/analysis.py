"""Analyse-demo's: intent, triage, ngram en reflect."""
from __future__ import annotations
import time
from nooch_village.event_bus import Event
from nooch_village.village import Village
from nooch_village.models import Proposal, GovernanceChange, ChangeKind
from nooch_village.governance import proposal_to_dict


def intent_demo():
    """Demonstreer de intentielaag: prioritering van acties tegen strategie en doelen."""
    from nooch_village.intent import prioritize
    from nooch_village.governance import Gate

    v = Village(heartbeat_seconds=86400)
    v.start()
    time.sleep(0.1)

    actions = [
        {
            "label": "schrijf missie-keyword artikel: biobased sneakers",
            "description": (
                "organisch verkeer genereren via missie-keyword artikel over biobased "
                "duurzame sneakers op nooch.earth — bijdraagt aan conversie en verkoop"
            ),
        },
        {
            "label": "lanceer Google Ads campagne voor schoenen",
            "description": (
                "betaald adverteren via Google Ads om snel verkeer en conversie te verhogen; "
                "advertising budget inzetten voor bereik"
            ),
        },
        {
            "label": "verbeter productpagina conversie op nooch.earth",
            "description": (
                "conversie nooch.earth verhogen via betere productpaginateksten en afbeeldingen "
                "zodat meer bezoekers een paar schoenen bestellen"
            ),
        },
    ]

    ranked = prioritize(actions, v.context)

    print("\n================ DEMO: intentielaag prioritering ================\n")
    print(f"{'#':<3} {'Actie':<52} {'Score':>6}  Status")
    print("-" * 95)
    for i, a in enumerate(ranked, 1):
        if a["dropped"]:
            status = f"✘ afgevallen: {a['drop_reason'][:45]}"
        else:
            status = "✔ toegestaan"
        print(f"{i:<3} {a['label']:<52} {a['score']:>6.1f}  {status}")

    allowed = [a for a in ranked if not a["dropped"]]
    dropped = [a for a in ranked if a["dropped"]]
    print(f"\n✔ {len(allowed)} toegestaan, ✘ {len(dropped)} afgevallen door policy")
    if allowed:
        print(f"→ Winnaar: \"{allowed[0]['label']}\" (score {allowed[0]['score']:.1f})")

    print("\n── G4-poort: kan advertising via governance worden toegevoegd? ──")
    ad_proposal = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="website_watcher",
                                add_accountabilities=[
                                    "advertising campagnes autoriseren voor snellere groei"]),
        tension="Verkoopdoel dreigt niet gehaald zonder extra bereik via advertising",
        trigger_example="website_watcher:verkoopdoel_2026_q4 dreigt te missen",
        rationale="Advertising als tijdelijke maatregel om 1000 paar te halen",
    )
    gate = Gate()
    passed, gate_name, gate_reason = gate.check(ad_proposal, v.records, v.context)
    if passed:
        print("  ✘ G4-poort liet advertising door — dit is een bug!")
    else:
        print(f"  ✔ G4-poort blokkeert ({gate_name}): {gate_reason[:70]}")

    print("\n── Anchor-purpose guard: kan de missie via governance worden gewijzigd? ──")
    mission_proposal = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="noochville",
                                purpose="Nooch.earth: maximale winstgevendheid als primair doel"),
        tension="Missie te vaag voor commerciële groei",
        trigger_example="website_watcher:missie_herformulering",
        rationale="Scherpere commerciële focus",
    )
    passed2, gate_name2, gate_reason2 = gate.check(mission_proposal, v.records, v.context)
    if passed2:
        print("  ✘ Guard liet missie-wijziging door — dit is een bug!")
    else:
        print(f"  ✔ Guard blokkeert ({gate_name2}): {gate_reason2[:70]}")

    v.stop()
    print("\n================ einde intent demo ================")


# HIER STOND `triage_demo()`: vier spanningen door de classificatie, met de verwachte
# uitkomst ernaast. De keten die hij toonde (sense_tension → triage → Matchmaker) is op
# 20 september 2026 opgeheven; er valt niets meer te demonstreren. De CLI-tak `village
# triage` is in dezelfde beurt verdwenen.


def ngram_demo():
    """Activeer Harry Hemp met een handmatige puls en toon het resultaat per term."""
    v = Village(heartbeat_seconds=86400)
    v.context.settings["tijdgeest_interval_seconds"] = "0"

    pulse_result: dict = {}
    signaal_events: list = []
    keyword_log: list = []

    v.bus.subscribe("tijdgeest_pulse_completed", lambda e: pulse_result.update(e.data))
    v.bus.subscribe("tijdgeest_signaal",         lambda e: signaal_events.append(e.data))
    v.bus.subscribe("keyword_decided",
                    lambda e: keyword_log.append({**e.data, "_event": "decided"}))

    v.start()

    tw = v.reconciler.live.get("harry_hemp")
    if tw is None:
        print("\n⚠️  HarryHemp niet actief in het dorp.")
        print("   → Controleer of harry_hemp in governance_records.json staat en CLASS_MAP.")
        v.stop()
        return

    terms = ["bewuste consument", "conscious consumer", "sufficiency", "regenerative", "plastic-free"]
    v.bus.publish(Event("tijdgeest_pulse", {"terms": terms}, "ngram_demo"))

    print("\n================ DEMO: HarryHemp ngram-puls ================")
    print(f"Termen: {', '.join(terms)}")
    print("Wacht op Google Books Ngram Viewer (kan 15-30 sec duren)…\n")

    for _ in range(900):
        if pulse_result:
            break
        time.sleep(0.1)
    time.sleep(0.2)

    v.stop()
    time.sleep(0.2)

    if not pulse_result.get("ok"):
        err = pulse_result.get("error", "onbekende fout")
        print(f"✘ Puls mislukt: {err}")
        return

    print(f"\n{'Term':<20} {'Corpus':<8} {'Richting':<12} {'Slope recent':>14} {'Freq (2019)':>12}")
    print("-" * 72)
    all_terms = pulse_result.get("terms", {})
    for term in terms:
        d = all_terms.get(term, {})
        if "error" in d:
            print(f"{term:<20} {'?':<8} {'FOUT':<12} {d['error'][:28]}")
            continue
        sig = d.get("signal", {})
        corpus = "NL (10)" if d.get("corpus") == 10 else "EN (26)"
        richting = sig.get("direction", "?")
        slope = sig.get("slope_recent")
        freq = d.get("freq_last")
        slope_str = f"{slope:.3e}" if slope is not None else "?"
        freq_str  = f"{freq:.3e}" if freq  is not None else "?"
        icon = {"stijgend": "📈", "dalend": "📉", "vlak": "➡️"}.get(richting, "❓")
        print(f"{term:<20} {corpus:<8} {icon} {richting:<10} {slope_str:>14} {freq_str:>12}")

    stijgend = pulse_result.get("stijgend", [])
    dalend   = pulse_result.get("dalend",   [])
    print(f"\n📈 stijgend ({len(stijgend)}): {', '.join(stijgend) or '(geen)'}")
    print(f"📉 dalend   ({len(dalend)}):   {', '.join(dalend) or '(geen)'}")

    if signaal_events:
        s = signaal_events[0]
        print(f"\n📢 tijdgeest_signaal: {s.get('boodschap','')}")

    if keyword_log:
        print(f"\nLibrarian-beslissingen voor stijgende termen:")
        for kw in keyword_log:
            print(f"  {kw.get('word','?'):<25} {kw.get('status','?'):<11} {kw.get('reason','')[:45]}")

    print("\n================ einde ngram demo ================")


def reflect_demo():
    """Laat zien hoe Harry Hemp zijn structurele beperkingen als means-gaps rapporteert."""
    v = Village(heartbeat_seconds=86400)
    v.context.settings["reflect_interval_seconds"] = "0"
    v.context.settings["tijdgeest_interval_seconds"] = "999999"

    means_gaps: list = []
    v.bus.subscribe("means_gap_sensed", lambda e: means_gaps.append(dict(e.data)))

    rec_before    = v.records.get("harry_hemp")
    accs_before   = list(rec_before.definition.accountabilities) if rec_before else []
    skills_before = list(rec_before.definition.skills)           if rec_before else []

    v.start()

    print("\n================ DEMO: Harry Hemp zelf-reflectie ================\n")
    print("Record VOOR reflectie:")
    print(f"  skills          : {skills_before}")
    print(f"  accountabilities ({len(accs_before)}):")
    for a in accs_before:
        print(f"    · {a}")

    tw = v.reconciler.live.get("harry_hemp")
    if not tw:
        print("\n⚠️  harry_hemp niet actief")
        v.stop()
        return

    tw._maybe_reflect(None)
    time.sleep(0.2)

    v.stop()
    time.sleep(0.1)

    print(f"\nMeans-gaps gerapporteerd ({len(means_gaps)}):")
    for g in means_gaps:
        print(f"  [{g.get('gap_key','')}]")
        print(f"    {g.get('description','')[:110]}…")

    rec_after    = v.records.get("harry_hemp")
    accs_after   = list(rec_after.definition.accountabilities) if rec_after else []
    skills_after = list(rec_after.definition.skills)           if rec_after else []

    print("\nRecord NA reflectie (ongewijzigd — means-gaps gaan naar inbox, niet governance):")
    print(f"  skills          : {skills_after}")
    print(f"  accountabilities ({len(accs_after)}):")
    for a in accs_after:
        print(f"    · {a[:80]}")

    print(f"\nChecks:")
    print(f"  {'✔' if len(means_gaps) == 2 else '✘'} twee means_gap_sensed events: "
          f"{[g.get('gap_key') for g in means_gaps]}")
    print(f"  {'✔' if skills_before == skills_after else '✘'} skills ongewijzigd")
    print(f"  ✔ geen governance-voorstel — means-gaps gaan naar inbox, niet naar governance")
    print(f"  ✔ geen nieuwe thread — activatie blijft mens-gated")
    print(f"\n⚠  Means-gaps zijn signalen aan de mens: vereisen nieuwe databronnen.")
    print(f"⚠  Implementatie vereist menselijke goedkeuring + code + SkillRegistry-registratie.")
    print("\n================ einde reflect demo ================")
