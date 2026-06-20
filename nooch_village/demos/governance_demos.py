"""Governance-gerelateerde demo-functies."""
from __future__ import annotations
import os, time, json
from nooch_village.event_bus import Event
from nooch_village.village import Village
from nooch_village.models import Proposal, GovernanceChange, ChangeKind
from nooch_village.governance import proposal_to_dict


def governance_demo():
    """Drie voorstellen: onschuldig (aangenomen), duplicaat-accountability (escaleert G2),
    en plastic-goedkeurend (escaleert G4). Bewijst de adopt-by-default poort."""
    v = Village(heartbeat_seconds=86400)
    results: dict = {}

    def _record(outcome):
        def _handler(e):
            pid = e.data.get("proposal_id", e.data.get("id", "?"))
            results[pid] = {"outcome": outcome,
                            "gate": e.data.get("gate", "-"),
                            "reason": e.data.get("reason", "")}
        return _handler

    v.bus.subscribe("governance_changed",          _record("aangenomen"))
    v.bus.subscribe("governance_review_requested", _record("geëscaleerd"))
    v.bus.subscribe("proposal_invalid",            _record("ongeldig"))

    v.start()

    p1 = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="website_watcher",
                                add_accountabilities=["maandrapportage opstellen voor stakeholders"]),
        tension="Analyst mist formele verantwoordelijkheid voor periodieke rapportage",
        trigger_example="field_note_2026-06-13: geen structurele terugkoppeling vastgelegd",
        rationale="Transparantie-waarde vraagt om periodieke verslaglegging",
    )
    p2 = Proposal(
        proposer_role="trends",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="trends",
                                add_accountabilities=["dagelijkse Field Note schrijven"]),
        tension="Scout wil ook Field Notes schrijven vanuit GSC-perspectief",
        trigger_example="dag_begint: geen Field Note vanuit GSC-data",
        rationale="GSC-data verdient eigen duiding in een Field Note",
    )
    p3 = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="website_watcher",
                                add_accountabilities=[
                                    "plastic-vriendelijke producten goedkeuren voor promotie"]),
        tension="Analyst wil plastic alternatieven promoten voor groter bereik",
        trigger_example="field_note_2026-06-13: lage interesse in plastic-free keywords",
        rationale="Bredere markt via plastic producten kan bereik verhogen",
    )

    print("\n================ DEMO: async governance-poort ================\n")
    for p in (p1, p2, p3):
        v.bus.publish(Event("proposal_raised", {"proposal": proposal_to_dict(p)}, "demo"))

    for _ in range(100):
        if len(results) >= 3:
            break
        time.sleep(0.05)

    v.stop()
    time.sleep(0.1)

    print(f"\n{'Voorstel (rol → change)':<42} {'Uitkomst':<14} {'Poort':<6} Reden")
    print("-" * 100)
    proposals = [
        (p1.id, "website_watcher → maandrapportage opstellen"),
        (p2.id, "trends → Field Note schrijven (dup)"),
        (p3.id, "website_watcher → plastic goedkeuren (G4)"),
    ]
    for pid, label in proposals:
        r = results.get(pid, {})
        print(f"{label:<42} {r.get('outcome','?'):<14} {r.get('gate','-'):<6} "
              f"{r.get('reason','')[:45]}")

    rec = v.records.get("website_watcher")
    if rec:
        new_acc = "maandrapportage opstellen voor stakeholders"
        heeft = new_acc in rec.definition.accountabilities
        print(f"\n✔ website_watcher-record bevat nieuwe accountability: {heeft} (v{rec.version})")
        if heeft:
            print(f"  → {new_acc}")

    print("\n================ einde governance demo ================")


def proposal_demo():
    """Demonstreert het ADD_ROLE governance-proces met een fictieve sensorrol: VoorbeeldSensor."""
    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    born: dict = {}

    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason"), **e.data}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig",
                                              "gate": "G0",
                                              "reason": e.data.get("reason"), **e.data}))
    v.bus.subscribe("role_born", lambda e: born.update(e.data))

    v.start()

    voorstel = Proposal(
        proposer_role="human",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id="voorbeeld_sensor",
            purpose=(
                "Een fictieve sensorrol ter illustratie van het governance-proces: "
                "volgt periodiek een meetbare omgevingsvariabele en rapporteert signalen."
            ),
            add_accountabilities=[
                "de variabele wekelijks meten via een beschikbare databron",
                "afwijkingen van de verwachte trend signaleren aan relevante inwoners",
                "periodiek de richting van het signaal aan het dorp rapporteren",
            ],
            add_domains=["sensor-observaties"],
            new_role_parent="noochville",
        ),
        tension=(
            "Het dorp heeft geen inwoner die deze specifieke omgevingsvariabele "
            "structureel bijhoudt, waardoor blindheid ontstaat voor tijdige signalen."
        ),
        trigger_example=(
            "Meermaals terugkerend in de wekelijkse puls: de variabele beïnvloedt "
            "structureel de beslissingen van andere inwoners en vraagt een staande rol. "
            "Dit is een doorlopende sensorfunctie, geen eenmalige opzoeking."
        ),
        rationale=(
            "Een staande sensorfunctie dicht het gat structureel en doorlopend. "
            "Geen eenmalige opzoeking maar een terugkerende accountability: "
            "het signaal verandert langzaam en vereist periodiek meten."
        ),
    )

    print("\n================ VOORSTEL: VoorbeeldSensor (fictief) ================\n")
    print(f"Proposer : {voorstel.proposer_role}")
    print(f"Soort    : {voorstel.change.kind.value}")
    print(f"Rol-ID   : {voorstel.change.role_id}")
    print(f"Purpose  : {voorstel.change.purpose[:80]}…")
    print(f"Domein   : {voorstel.change.add_domains}")
    print("Accountabilities:")
    for a in voorstel.change.add_accountabilities:
        print(f"  · {a}")
    print(f"\nTension  : {voorstel.tension[:90]}…")
    print(f"Trigger  : {voorstel.trigger_example[:90]}…")
    print(f"Rationale: {voorstel.rationale[:90]}…")
    print(f"\nVoorstel-ID: {voorstel.id}")

    pid = v.submit_proposal(voorstel)

    print("\n─── Facilitator draait de G0-G4-poort… ───\n")
    for _ in range(100):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.2)

    v.stop()
    time.sleep(0.1)

    status = outcome.get("status", "?")
    gate   = outcome.get("gate", "-")
    reason = outcome.get("reason", "")

    print(f"Uitkomst : {status}")
    if status != "aangenomen":
        print(f"Poort    : {gate}")
        print(f"Reden    : {reason}")
    else:
        rec = v.records.get("voorbeeld_sensor")
        print(f"Record   : voorbeeld_sensor v{rec.version if rec else '?'} opgeslagen")
        unmanned = "voorbeeld_sensor" in v.reconciler.unmanned
        print(f"Status   : {'onbemand (wacht op implementatie)' if unmanned else 'live — onverwacht!'}")
        print(f"Domein   : {rec.definition.domains if rec else '?'}")
        print()
        if "voorbeeld_sensor" in born:
            print("Groeidagboek-entry:")
            print(f"  trigger: {born.get('trigger_example','')[:80]}")
            print(f"  by     : {born.get('by','?')}")
        if rec:
            print("\nAccountabilities in record:")
            for a in rec.definition.accountabilities:
                print(f"  · {a}")

    print("\n================ einde voorstel-demo ================")


def lifecycle_demo():
    """Bewijst het add_role-addendum: G0 zónder vs mét herhalingsbewijs."""
    v = Village(heartbeat_seconds=86400)
    results: dict = {}
    born: dict = {}

    def _record(outcome):
        def _h(e):
            pid = e.data.get("proposal_id", e.data.get("id", "?"))
            results[pid] = {"outcome": outcome,
                            "gate": e.data.get("gate", "-"),
                            "reason": e.data.get("reason", "")}
        return _h

    v.bus.subscribe("governance_changed",          _record("aangenomen"))
    v.bus.subscribe("governance_review_requested", _record("geëscaleerd"))
    v.bus.subscribe("proposal_invalid",            _record("ongeldig"))
    v.bus.subscribe("role_born", lambda e: born.update({e.data["role_id"]: e.data}))

    v.start()

    p1 = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="content_writer",
                                purpose="Schrijft SEO-artikelen voor nooch.earth",
                                add_accountabilities=["SEO-artikelen schrijven"],
                                new_role_parent="noochville"),
        tension="Er is één keer een contentverzoek binnengekomen",
        trigger_example="website_watcher:2026-06-13 één contentverzoek",
        rationale="Content schrijven kost veel tijd",
        source="demo",
    )
    p2 = Proposal(
        proposer_role="website_watcher",
        change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="content_strategist",
                                purpose="Vertaalt missie-inzichten structureel naar content-kalender",
                                add_accountabilities=["content-kalender bijhouden",
                                                      "missie-keywords omzetten naar artikel-briefs"],
                                new_role_parent="noochville"),
        tension="Elke week hetzelfde gat: geen eigenaar voor content-planning",
        trigger_example="website_watcher:meermaals terugkerend wekelijks — elke week geen contentplanning",
        rationale="Structureel elke week hetzelfde probleem. Meermaals gesignaleerd.",
        source="demo",
    )

    print("\n================ DEMO: rol-lifecycle (add_role addendum) ================\n")
    for p in (p1, p2):
        v.bus.publish(Event("proposal_raised", {"proposal": proposal_to_dict(p)}, "demo"))

    for _ in range(100):
        if len(results) >= 2:
            break
        time.sleep(0.05)
    time.sleep(0.2)

    v.stop()
    time.sleep(0.1)

    print(f"\n{'Voorstel':<42} {'Uitkomst':<12} {'Poort':<6} Reden")
    print("-" * 100)
    for pid, label in [(p1.id, "add_role zónder herhalingsbewijs"),
                       (p2.id, "add_role mét herhalingsbewijs")]:
        r = results.get(pid, {})
        print(f"{label:<42} {r.get('outcome','?'):<12} {r.get('gate','-'):<6} "
              f"{r.get('reason','')[:48]}")

    print(f"\nGeboren rollen (role_born event):    {list(born.keys()) or '(geen)'}")
    unmanned = list(v.reconciler.unmanned.keys())
    print(f"Onbemand in Reconciler:              {unmanned or '(geen)'}")

    checks = [
        ("G0 blokkeert zonder herhalingsbewijs",
         results.get(p1.id, {}).get("outcome") == "ongeldig"),
        ("G0 passeert met herhalingsbewijs",
         results.get(p2.id, {}).get("outcome") == "aangenomen"),
        ("role_born event ontvangen",
         "content_strategist" in born),
        ("rol onbemand in reconciler",
         "content_strategist" in v.reconciler.unmanned),
    ]
    print()
    for label, ok in checks:
        print(f"  {'✔' if ok else '✘'} {label}")

    dagboek = os.path.join(v.context.data_dir, "groeidagboek.jsonl")
    if os.path.exists(dagboek):
        entries = [json.loads(line) for line in open(dagboek)]
        cs_entries = [e for e in entries if e.get("role_id") == "content_strategist"]
        print(f"\nGroeidagboek: {dagboek}")
        for entry in cs_entries[-2:]:
            print(f"  [{entry['role_id']}] trigger: {entry.get('trigger_example','')[:65]}")

    print("\n================ einde lifecycle demo ================")


def purge_demo():
    """Verwijdert alle records met source='demo' uit de governance. Idempotent."""
    v = Village(heartbeat_seconds=86400)

    print("\n================ ROSTER VOOR PURGE ================")
    v.print_roster()

    demo_recs = [r for r in v.records.all() if r.source == "demo" and not r.archived]
    if not demo_recs:
        print("\n✔ Geen demo-records gevonden — niets te doen.")
        print("\n================ einde purge ================")
        return

    print(f"\n⚙  Gevonden demo-records om te archiveren: {[r.id for r in demo_recs]}")
    for rec in demo_recs:
        rec.archived = True
        rec.version += 1
        v.records.put(rec)
        if rec.parent:
            parent = v.records.get(rec.parent)
            if parent and rec.id in parent.members:
                parent.members.remove(rec.id)
                v.records.put(parent)
        print(f"  ✔ '{rec.id}' gearchiveerd (v{rec.version})")

    print("\n================ ROSTER NA PURGE ================")
    v2 = Village(heartbeat_seconds=86400)
    v2.print_roster()
    print("\n================ einde purge ================")
