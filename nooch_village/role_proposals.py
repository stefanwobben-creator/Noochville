"""Founder-voorstellen om rollen via het echte governance-proces geboren te laten
worden, niet via seed-hardcoding.

De rol ontstaat door een ADD_ROLE-voorstel dat de G0-G4-poort passeert en door de
Secretary wordt aangenomen: onbemand geboren in de records. Mens-gated activatie
(code + CLASS_MAP + skills) volgt later, conform born-vs-activated. Zo loopt elke
structuurwijziging door de officiële governance-weg.
"""
from __future__ import annotations

import time

from nooch_village.models import Proposal, GovernanceChange, ChangeKind


def _submit_proposal_sync(proposal: Proposal) -> dict:
    """Voer een governance-voorstel synchroon uit: Gate.check + Secretary._adopt direct op de
    on-disk records, ZONDER een volledige Village te starten (geen threads, geen puls, geen
    credits). Schrijft een groeidagboek-entry bij een geboorte. Geeft {status, gate?, reason?,
    records?}."""
    import os
    import json
    import time as _t
    from nooch_village.config import load_context
    from nooch_village.governance import Records, Gate, Secretary
    from nooch_village.event_bus import EventBus
    from nooch_village.seeds import seed_records, migrate_records
    from nooch_village.village import BASE_DIR

    ctx = load_context(BASE_DIR)
    records = Records(os.path.join(ctx.data_dir, "governance_records.json"))
    seed_records(records)
    migrate_records(records)
    passed, gate, reason = Gate().check(proposal, records, ctx)
    if not passed:
        return {"status": "ongeldig" if gate == "G0" else "geëscaleerd",
                "gate": gate, "reason": reason}
    bus = EventBus(name="cli-governance")
    born: list = []
    bus.subscribe("role_born", lambda e: born.append(e.data))
    Secretary(records, bus)._adopt(proposal)
    if born:
        try:
            with open(os.path.join(ctx.data_dir, "groeidagboek.jsonl"), "a") as f:
                for d in born:
                    f.write(json.dumps({"ts": _t.time(), **d}, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass
    return {"status": "aangenomen", "records": records}


def build_content_strategist_proposal() -> Proposal:
    """Het ADD_ROLE-voorstel voor de Content Strategist: publieke website-content in
    de merkstem, gevoed door de kennisgraaf, gegated door de claim-keuring.

    Bevat het herhalingsbewijs dat G0 vereist, een uniek domein (G1) en
    accountabilities die niet botsen met bestaande rollen (G2)."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id="content_strategist",
            purpose=(
                "Vertaalt de kennisgraaf naar publieke website-content in de merkstem, "
                "zodat de missie van Nooch naar buiten komt en aligned bezoekers de "
                "website vinden en verder lezen."
            ),
            add_accountabilities=[
                "uit de kennisgraaf clusters kiezen die publieke website-content verdienen",
                "publieke website-content opstellen in de merkstem van Nooch",
                "elke publicatie door de claim-keuring halen voordat ze live gaat",
            ],
            add_domains=["publieke content"],
            new_role_parent="noochville",
        ),
        tension=(
            "Het dorp heeft geen inwoner die structureel publieke website-content maakt; "
            "de website blijft daardoor achter terwijl daar de meeste groei te winnen is."
        ),
        trigger_example=(
            "Meermaals terugkerend en wekelijks: de website-content blijft structureel "
            "achter en er is geen staande eigenaar voor publieke contentcreatie."
        ),
        rationale=(
            "Een staande contentrol dicht dit gat structureel en doorlopend: geen "
            "eenmalige tekst maar een terugkerende accountability die elke week publieke "
            "content levert. De rol wordt onbemand geboren; activatie blijft mens-gated."
        ),
    )


def build_content_strategist_skills_proposal() -> Proposal:
    """amend_role: ken de Content Strategist zijn schrijf- en check-skills toe, via de gate.

    Born-vs-activated: de rol bestaat al (geboren via governance); dit voorstel geeft hem
    de capaciteit. Samen met de CLASS_MAP-entry (code) maakt dat hem een levende inwoner.
    De skills bestaan al in de registry."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id="content_strategist",
            add_skills=["content_schrijven", "content_check"],
        ),
        tension=("De Content Strategist is geboren maar onbemand; hij mist de skills om "
                 "publieke content te schrijven en te checken."),
        trigger_example="the_source: activatie van de geboren content_strategist-rol",
        rationale=("De rol bestaat al via governance; nu krijgt hij zijn capaciteit "
                   "(content_schrijven, content_check) toegekend via amend_role, zodat hij "
                   "na de CLASS_MAP-activatie publieke content kan draften en checken."),
    )


def grant_content_strategist_skills() -> None:
    """Dien het amend_role-voorstel voor de Content Strategist-skills in via de gate."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    v.submit_proposal(build_content_strategist_skills_proposal())
    print("\n===== amend_role: Content Strategist-skills via governance =====\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("content_strategist")
        live = "content_strategist" in v.reconciler.live
        print(f"Skills nu: {rec.definition.skills if rec else '?'}")
        print(f"Status   : {'LEVEND (geactiveerd)' if live else 'onbemand (herstart village om te activeren)'}")
    else:
        print(f"Poort   : {outcome.get('gate', '-')}  Reden: {outcome.get('reason', '')}")
    print("\n===== einde =====")


def build_grant_skill_proposal(role_id: str, skill: str, reason: str = "") -> Proposal:
    """Een AMEND_ROLE-voorstel dat een bestaande, in de registry geregistreerde skill aan
    een rol toekent via de gate. Herbruikbaar voor elke skill→rol-toekenning."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=role_id,
                                add_skills=[skill]),
        tension=(reason or f"Rol '{role_id}' gebruikt skill '{skill}' al in code, maar de "
                 f"governance-definitie loopt achter; de skill staat niet in de DNA."),
        trigger_example=f"the_source: skill '{skill}' toekennen aan rol '{role_id}'",
        rationale=(f"De skill '{skill}' bestaat al in de registry en wordt aangeroepen; via "
                   f"amend_role krijgt '{role_id}' de capaciteit ook formeel, zodat use_skill "
                   f"niet langer fail-closed gaat."),
    )


def grant_skill_via_governance(role_id: str, skill: str, reason: str = "") -> None:
    """Dien een AMEND_ROLE-voorstel in dat een skill aan een rol toekent, via de gate (synchroon)."""
    res = _submit_proposal_sync(build_grant_skill_proposal(role_id, skill, reason))
    print(f"\n===== AMEND_ROLE: skill '{skill}' → rol '{role_id}' via governance =====\n")
    print(f"Uitkomst: {res['status']}")
    if res["status"] == "aangenomen":
        rec = res["records"].get(role_id)
        print(f"Skills nu: {rec.definition.skills if rec else '?'}")
        print("Herstart de village (of draai 'once') om de skill actief te maken.")
    else:
        print(f"Poort {res.get('gate', '-')}: {res.get('reason', '')}")
    print("\n===== einde =====")


def build_grant_accountability_proposal(role_id: str, accountability: str, reason: str = "") -> Proposal:
    """AMEND_ROLE: ken een rol formeel een accountability toe via de gate. Voor wanneer een rol
    iets al uitvoert (capaciteit aanwezig) maar de definitie achterloopt."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=role_id,
                                add_accountabilities=[accountability]),
        tension=(reason or f"Rol '{role_id}' voert '{accountability}' inmiddels uit, maar de "
                 f"governance-definitie kent die accountability nog niet."),
        trigger_example=f"the_source: accountability '{accountability}' formeel toekennen aan '{role_id}'",
        rationale=(f"De rol vervult deze accountability nu (capaciteit aanwezig en ontsloten); via "
                   f"amend_role klopt de definitie weer met wat de rol werkelijk doet."),
    )


def grant_accountability_via_governance(role_id: str, accountability: str, reason: str = "") -> None:
    """Dien een AMEND_ROLE-voorstel in dat een accountability aan een rol toekent (synchroon)."""
    res = _submit_proposal_sync(build_grant_accountability_proposal(role_id, accountability, reason))
    print(f"\n===== AMEND_ROLE: accountability '{accountability}' → '{role_id}' via governance =====\n")
    print(f"Uitkomst: {res['status']}")
    if res["status"] == "aangenomen":
        rec = res["records"].get(role_id)
        print(f"Accountabilities nu: {rec.definition.accountabilities if rec else '?'}")
    else:
        print(f"Poort {res.get('gate', '-')}: {res.get('reason', '')}")
    print("\n===== einde =====")


def build_revoke_skill_proposal(role_id: str, skill: str, reason: str = "") -> Proposal:
    """Een AMEND_ROLE-voorstel dat een skill uit de DNA van een rol haalt via de gate.
    Voor opruiming: een skill die de code niet meer aanroept hoort niet in de definitie."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=role_id,
                                remove_skills=[skill]),
        tension=(reason or f"Skill '{skill}' staat nog in de DNA van '{role_id}' maar wordt "
                 f"niet meer aangeroepen; de definitie loopt achter op de code."),
        trigger_example=f"the_source: skill '{skill}' intrekken bij rol '{role_id}'",
        rationale=(f"Opruiming: '{skill}' is dormant (niet meer via use_skill aangeroepen). "
                   f"Via amend_role verlaat de skill de DNA, zodat definitie en code kloppen."),
    )


def revoke_skill_via_governance(role_id: str, skill: str, reason: str = "") -> None:
    """Dien een AMEND_ROLE-voorstel in dat een skill uit een rol haalt, via de gate."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    v.submit_proposal(build_revoke_skill_proposal(role_id, skill, reason))
    print(f"\n===== AMEND_ROLE: skill '{skill}' uit rol '{role_id}' via governance =====\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get(role_id)
        print(f"Skills nu: {rec.definition.skills if rec else '?'}")
    else:
        print(f"Poort {outcome.get('gate', '-')}: {outcome.get('reason', '')}")
    print("\n===== einde =====")


def build_harry_role_upgrade_proposal() -> Proposal:
    """amend_role: scherp harry_hemp's purpose + accountabilities aan na de bouw van
    correlatie-analyse en de gekalibreerde voortzetting. De code loopt voor op de definitie."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id="harry_hemp",
            purpose=(
                "Detecteert structurele taalverschuiving over decennia — co-beweging en "
                "substitutie tussen missietermen — en zet die boog gekalibreerd voort voorbij "
                "de ngram-cutoff via een academische-aandacht-proxy; grondt kandidaat-termen "
                "in wetenschappelijke literatuur."
            ),
            add_accountabilities=[
                "structurele co-beweging en substitutie tussen missietermen detecteren over de lange boog",
                "de culturele boog voorbij de ngram-cutoff voortzetten via een gekalibreerde "
                "academische-aandacht-proxy, transparant gelabeld met de gemeten betrouwbaarheid",
            ],
        ),
        tension=("Harry's mandaat stond op 'richting observeren'; zijn werkelijke waarde is "
                 "structurele verschuiving plus een gekalibreerde voortzetting voorbij 2019. De "
                 "definitie liep achter op de gebouwde capaciteit."),
        trigger_example="the_source: roldefinitie harry_hemp aanscherpen na bouw correlatie + voortzetting",
        rationale=("De capaciteit is gebouwd (co-beweging/substitutie + gekalibreerde OpenAlex-"
                   "voortzetting); via amend_role kloppen purpose en accountabilities weer met de code."),
    )


def upgrade_harry_role() -> None:
    """Dien het amend_role-voorstel voor Harry's aangescherpte roldefinitie in via de gate."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    v.submit_proposal(build_harry_role_upgrade_proposal())
    print("\n===== amend_role: harry_hemp roldefinitie via governance =====\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("harry_hemp")
        print(f"Purpose nu: {rec.definition.purpose if rec else '?'}")
        print(f"Accountabilities: {len(rec.definition.accountabilities) if rec else '?'}")
    else:
        print(f"Poort {outcome.get('gate', '-')}: {outcome.get('reason', '')}")
    print("\n===== einde =====")


def build_remove_role_proposal(role_id: str, reason: str = "") -> Proposal:
    """Een REMOVE_ROLE-voorstel via governance: archiveert een rol.

    De gate (G3) laat een rol zonder accountabilities door (auto-adopt); een rol mét
    accountabilities escaleert naar de mens, zodat verweesd werk nooit stilletjes verdwijnt.
    Removal is omkeerbaar: de Secretary archiveert, verwijdert niet hard."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id=role_id),
        tension=(reason or f"Rol '{role_id}' is overbodig/rommel en hoort opgeruimd te worden."),
        trigger_example=f"the_source: governance-opschoning, verwijder rol '{role_id}'",
        rationale=("Opruiming van een rol die niet (meer) bijdraagt. Bij accountabilities "
                   "escaleert de gate naar de mens; anders wordt de rol gearchiveerd."),
    )


def remove_role_via_governance(role_id: str, reason: str = "") -> None:
    """Dien een REMOVE_ROLE-voorstel in via de gate en rapporteer de uitkomst."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    v.submit_proposal(build_remove_role_proposal(role_id, reason))
    print(f"\n===== REMOVE_ROLE: '{role_id}' via governance =====\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get(role_id)
        print(f"Rol '{role_id}' gearchiveerd: {getattr(rec, 'archived', '?')}")
    elif status == "geëscaleerd":
        print(f"Poort {outcome.get('gate')}: {outcome.get('reason')}")
        print("→ De rol heeft accountabilities; keur de verwijdering goed in de human inbox.")
    else:
        print(f"Reden: {outcome.get('reason', '')}")
    print("\n===== einde =====")


def build_website_watcher_serpapi_proposal() -> Proposal:
    """amend_role: ken website_watcher de serpapi_trends-skill toe, via de gate.

    pytrends wordt door Google geblokkeerd; SerpApi is de betrouwbare vervanger. De rol
    bestaat al; dit voorstel geeft hem de nieuwe databron-capaciteit. google_trends blijft
    in de DNA staan (ongebruikt) tot de governance-opschoning."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id="website_watcher",
            add_skills=["serpapi_trends"],
        ),
        tension=("Google Trends via pytrends wordt structureel geblokkeerd (429); de "
                 "website_watcher mist een betrouwbare trends-bron voor zijn groei-puls."),
        trigger_example="the_source: betrouwbare trends-bron (SerpApi) voor website_watcher",
        rationale=("pytrends faalt herhaaldelijk; serpapi_trends levert dezelfde data "
                   "betrouwbaar. De skill bestaat al in de registry; via amend_role krijgt "
                   "website_watcher de capaciteit, zodat de wekelijkse trends-puls werkt."),
    )


def grant_website_watcher_serpapi() -> None:
    """Dien het amend_role-voorstel voor de SerpApi-trends-skill in via de gate."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    v.submit_proposal(build_website_watcher_serpapi_proposal())
    print("\n===== amend_role: serpapi_trends → website_watcher via governance =====\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("website_watcher")
        print(f"Skills nu: {rec.definition.skills if rec else '?'}")
        print("Herstart de village (of draai 'once') om de nieuwe skill te gebruiken.")
    else:
        print(f"Poort   : {outcome.get('gate', '-')}  Reden: {outcome.get('reason', '')}")
    print("\n===== einde =====")


def build_concurrent_scout_proposal() -> Proposal:
    """ADD_ROLE: de Concurrent-scout formeel via de gate geboren laten worden.

    De rol is deze sessie via seed/migratie toegevoegd (een afwijking van de regel dat
    rolwijzigingen via governance gaan); dit voorstel brengt de provenance in lijn. Het
    herbouwt het record getrouw (zelfde 4 skills) maar nu met source=sensed en een
    audittrail. Bevat herhalingsbewijs (G0), een uniek domein (G1) en niet-botsende
    accountabilities (G2)."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id="concurrent_scout",
            purpose=("Observeert de duurzame-sneakermarkt: signaleert strategische bewegingen "
                     "van directe concurrenten, ontdekt nieuwe spelers en linkbuilding-kansen, "
                     "en meet hun marktinteresse."),
            add_accountabilities=[
                "strategisch concurrentienieuws monitoren (funding, lanceringen, B-Corp, materiaalinnovatie)",
                "wekelijks een concurrentie-veldrapport opstellen",
                "nieuwe concurrenten en linkbuilding-doelwitten spotten en aan de mens voorleggen",
                "missie-relevante concurrent-zetten als spanning signaleren",
            ],
            add_domains=["concurrentie-observatie"],
            add_skills=["competitor_news", "competitor_discover",
                        "linkbuilding_targets", "keywords_everywhere"],
            new_role_parent="noochville",
        ),
        tension=("Het dorp observeerde de markt niet; concurrent-bewegingen, nieuwe spelers en "
                 "linkbuilding-kansen bleven onzichtbaar terwijl daar groei en positionering ligt."),
        trigger_example=("Wekelijks terugkerend en structureel: concurrenten doen doorlopend "
                         "strategische zetten en er duiken steeds nieuwe duurzame sneakermerken "
                         "en gids-artikelen op, zonder staande waarnemer."),
        rationale=("Een staande marktobservator dicht dit gat doorlopend: een wekelijkse, "
                   "terugkerende accountability die concurrentienieuws, nieuwe spelers en "
                   "linkbuilding-doelwitten levert. De rol is al bemenst (code + CLASS_MAP); dit "
                   "voorstel brengt de governance-provenance in lijn (geboren via de gate)."),
    )


def formalize_session_governance() -> None:
    """Formaliseer achteraf de structuurwijzigingen die deze sessie via seed/migratie zijn
    toegevoegd: de Concurrent-scout (add_role) en de KeywordsEverywhere-grant aan de Librarian
    (amend_role). Beide lopen nu alsnog door de G0-G4-poort + Secretary, met audittrail."""
    proposals = [
        ("ADD_ROLE concurrent_scout", build_concurrent_scout_proposal()),
        ("AMEND_ROLE librarian ← keywords_everywhere",
         build_grant_skill_proposal(
             "librarian", "keywords_everywhere",
             "De Librarian verrijkt elke kandidaat met KE-volume; deze sessie geseed, nu formeel.")),
    ]
    print("\n===== Formaliseren via governance (achteraf, synchroon — geen puls) =====\n")
    last: dict = {}
    for label, p in proposals:
        res = _submit_proposal_sync(p)
        last = res
        line = f"{label}: {res['status']}"
        if res["status"] != "aangenomen":
            line += f"  (poort {res.get('gate', '-')}: {res.get('reason', '')})"
        print(line)

    recs = last.get("records")
    if recs is not None:
        scout = recs.get("concurrent_scout")
        lib = recs.get("librarian")
        print(f"\nconcurrent_scout: source={getattr(scout, 'source', '?')} "
              f"skills={scout.definition.skills if scout else '?'}")
        print(f"librarian skills: {lib.definition.skills if lib else '?'}")
    print("\n===== einde =====")


def birth_content_strategist() -> None:
    """Dien het Content Strategist-voorstel in via het live governance-proces en
    rapporteer de uitkomst. De rol wordt onbemand geboren als de poort 'm aanneemt."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    born: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("role_born", lambda e: born.update(e.data))

    v.start()
    voorstel = build_content_strategist_proposal()
    print("\n========== VOORSTEL: Content Strategist (via governance) ==========\n")
    print(f"Proposer: {voorstel.proposer_role}  |  Rol-ID: {voorstel.change.role_id}")
    print(f"Domein  : {voorstel.change.add_domains}")
    print("Accountabilities:")
    for a in voorstel.change.add_accountabilities:
        print(f"  · {a}")
    v.submit_proposal(voorstel)

    print("\n─── Facilitator draait de G0-G4-poort… ───\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()

    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("content_strategist")
        unmanned = "content_strategist" in v.reconciler.unmanned
        print(f"Record  : content_strategist v{rec.version if rec else '?'} "
              f"[source={rec.source if rec else '?'}]")
        print(f"Status  : {'onbemand (wacht op mens-gated implementatie)' if unmanned else 'live — onverwacht!'}")
    else:
        print(f"Poort   : {outcome.get('gate', '-')}")
        print(f"Reden   : {outcome.get('reason', '')}")
    print("\n========== einde ==========")


# ── Compliance-rol: bewaker van de claim-keuring (merk-claims nu, eigen teksten later) ──────────

# De operationele cirkel waar de AI-rollen (concurrent_scout, harry_hemp, …) wonen. Deployment-
# structuur, GEEN inhoud: overschrijfbaar via het CLI-argument, zodat de tree-id niet brittle in de
# code vastzit. Default = de huidige live-boom.
_COMPLIANCE_PARENT = "mother_earth__nooch__noochville"


def build_compliance_proposal(parent: str = _COMPLIANCE_PARENT) -> Proposal:
    """ADD_ROLE-voorstel voor de Compliance-rol: bezit de claim-keuring en verifieert
    afbreekbaarheids-/duurzaamheidsclaims van externe merken tegen bewijs.

    `parent` = de id van de cirkel waar de rol in komt te hangen (deployment-structuur). Wijst die naar
    een bestaande cirkel, dan hangt de adopt de rol in `members` en wordt hij zichtbaar én
    gematerialiseerd; wijst hij naar een niet-bestaande id, dan blijft de rol buiten de boom (onzichtbaar).

    G0-herhalingsbewijs in de trigger, uniek domein 'claim-keuring' (G1) en een accountability
    die niet botst met bestaande rollen (G2). Onbemand geboren; de eigen-teksten-accountability
    volgt later via amend_role zodra daar een skill voor bestaat."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id="compliance",
            purpose=(
                "Bewaakt de gegrondheid van duurzaamheids- en afbreekbaarheidsclaims: "
                "verifieert claims van externe merken tegen bewijs en legt de status vast, "
                "zodat het dorp op onderbouwde feiten stuurt in plaats van op marketing."
            ),
            add_accountabilities=[
                "afbreekbaarheids- en duurzaamheidsclaims van externe merken verifiëren "
                "tegen bewijs (certificering, norm, labresultaat) en de status vastleggen",
            ],
            add_domains=["claim-keuring"],
            new_role_parent=parent,
        ),
        tension=(
            "Het dorp identificeert wel merken met afbreekbaarheidsclaims, maar niemand "
            "controleert die claims tegen bewijs; de claim-keuring waar content_strategist "
            "al naar verwijst heeft geen eigenaar."
        ),
        trigger_example=(
            "Structureel en terugkerend: taken om merkclaims op bewijs te controleren blijven "
            "op 'geen skill' staan, en content_strategist verwijst naar een claim-keuring die "
            "geen enkele rol bezit."
        ),
        rationale=(
            "Een staande Compliance-rol bezit de claim-keuring doorlopend: hij verifieert claims "
            "structureel tegen bewijs in plaats van eenmalig. De rol wordt onbemand geboren; "
            "activatie (persona) blijft mens-gated."
        ),
    )


def build_compliance_skills_proposal() -> Proposal:
    """amend_role: ken de Compliance-rol de claim_evidence-skill toe, via de gate.

    Zodra de skill toegekend is, materialiseert de reconciler de rol als generieke Inhabitant
    (geen CLASS_MAP-entry nodig — een geregistreerde skill volstaat). Persona-toewijzing
    (AI-bemanning) volgt daarna mens-gated in de cockpit."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id="compliance",
            add_skills=["claim_evidence"],
        ),
        tension=("De Compliance-rol is geboren maar onbemand; hij mist de skill om merkclaims "
                 "tegen bewijs te verifiëren."),
        trigger_example="the_source: activatie van de geboren compliance-rol",
        rationale=("De rol bestaat al via governance; nu krijgt hij zijn capaciteit "
                   "(claim_evidence) via amend_role, zodat de reconciler hem als generieke "
                   "Inhabitant materialiseert. Persona-toewijzing volgt mens-gated."),
    )


def build_compliance_claims_proposal() -> Proposal:
    """amend_role: geef Compliance het domein over de eigen claims-database plus de
    `claims_check`-capaciteit.

    Bewust een AMEND en geen ADD_ROLE: de Compliance-rol is via governance al geboren
    (domein 'claim-verification', skill claim_evidence) en keurt claims van externe merken.
    Wat ontbreekt is het eigenaarschap over de EIGEN claims — de EmpCo/ACM-toets op nooch.earth.
    Domein 'claims-database' is uniek (G1) en de accountability botst met geen enkele rol (G2)."""
    return Proposal(
        proposer_role="the_source",
        change=GovernanceChange(
            kind=ChangeKind.AMEND_ROLE,
            role_id="compliance",
            add_accountabilities=[
                "de eigen uitingen van Nooch toetsen aan de EU-richtlijn 2024/825 (EmpCo) en de "
                "ACM-leidraad duurzaamheidsclaims, en de termen-, werklijst- en landenregels in "
                "de claims-database actueel houden",
            ],
            add_domains=["claims-database"],
            add_skills=["claims_check"],
        ),
        tension=("Nooch.earth scoorde 28/100 in een externe EmpCo-scan met tien verboden claims, "
                 "en vanaf 27-09-2026 lopen die tot 4% jaaromzet aan boete-exposure op. De "
                 "claims-database en de checker hebben geen eigenaar: iedereen mag toetsen, "
                 "niemand cureert."),
        trigger_example=(
            "Structureel en terugkerend: bij elke nieuwe uiting (homepage, productpagina, FAQ, "
            "social) komen dezelfde verboden termen terug — de externe scan telde er meermaals "
            "tien op drie pagina's, en de ACM handhaaft wekelijks in de schoenensector."),
        rationale=("Het domein 'claims-database' legt het cureren van de termenlijst, de werklijst "
                   "en de landenregels bij één rol; lezen blijft vrij voor het hele dorp. De skill "
                   "claims_check geeft die rol de lokale toets. Activatie/bemensing blijft "
                   "mens-gated."),
    )


def grant_compliance_claims() -> None:
    """Dien het amend_role-voorstel voor het claims-database-domein + de claims_check-skill in
    via de live gate en rapporteer de uitkomst."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    print("\n===== amend_role: Compliance krijgt het claims-database-domein =====\n")
    v.submit_proposal(build_compliance_claims_proposal())
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("compliance")
        print(f"Domeinen: {rec.definition.domains if rec else '?'}")
        print(f"Skills  : {rec.definition.skills if rec else '?'}")
        print(f"Versie  : v{rec.version if rec else '?'}")
    else:
        print(f"Poort   : {outcome.get('gate', '-')}  Reden: {outcome.get('reason', '')}")
    print("\n===== einde =====")


def birth_compliance(parent: str | None = None) -> None:
    """Dien het Compliance-ADD_ROLE-voorstel in via het live governance-proces en rapporteer de
    uitkomst. De rol wordt onbemand geboren als de poort 'm aanneemt. `parent` = de cirkel-id waar de
    rol in komt (CLI-override; default = de huidige live operationele cirkel)."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    voorstel = build_compliance_proposal(parent or _COMPLIANCE_PARENT)
    print("\n========== VOORSTEL: Compliance (via governance) ==========\n")
    print(f"Proposer: {voorstel.proposer_role}  |  Rol-ID: {voorstel.change.role_id}")
    print(f"Ouder   : {voorstel.change.new_role_parent}")
    print(f"Domein  : {voorstel.change.add_domains}")
    print("Accountabilities:")
    for a in voorstel.change.add_accountabilities:
        print(f"  · {a}")
    v.submit_proposal(voorstel)
    print("\n─── Facilitator draait de G0-G4-poort… ───\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("compliance")
        par = v.records.get(rec.parent) if rec and rec.parent else None
        in_tree = bool(par and "compliance" in par.members)
        print(f"Record  : compliance v{rec.version if rec else '?'} [source={rec.source if rec else '?'}]")
        print(f"Ouder   : {rec.parent if rec else '?'}  |  in cirkel-members: {in_tree}")
        print("Status  : onbemand (ken de skill toe met: compliance_skills)"
              if in_tree else
              "LET OP  : hangt NIET in de cirkel — controleer de ouder-id")
    else:
        print(f"Poort   : {outcome.get('gate', '-')}")
        print(f"Reden   : {outcome.get('reason', '')}")
    print("\n========== einde ==========")


def grant_compliance_skills() -> None:
    """Dien het amend_role-voorstel voor de claim_evidence-skill van Compliance in via de gate.
    Na toekenning materialiseert de reconciler de rol als generieke Inhabitant (bij herstart)."""
    from nooch_village.village import Village

    v = Village(heartbeat_seconds=86400)
    outcome: dict = {}
    v.bus.subscribe("governance_changed",
                    lambda e: outcome.update({"status": "aangenomen", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcome.update({"status": "geëscaleerd",
                                              "gate": e.data.get("gate"),
                                              "reason": e.data.get("reason")}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcome.update({"status": "ongeldig", "gate": "G0",
                                              "reason": e.data.get("reason")}))
    v.start()
    v.submit_proposal(build_compliance_skills_proposal())
    print("\n===== amend_role: Compliance-skill (claim_evidence) via governance =====\n")
    for _ in range(200):
        if outcome:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    v.stop()
    status = outcome.get("status", "?")
    print(f"Uitkomst: {status}")
    if status == "aangenomen":
        rec = v.records.get("compliance")
        live = "compliance" in v.reconciler.live
        print(f"Skills nu: {rec.definition.skills if rec else '?'}")
        print(f"Status   : {'LEVEND (gematerialiseerd als Inhabitant)' if live else 'onbemand (herstart village om te materialiseren)'}")
    else:
        print(f"Poort   : {outcome.get('gate', '-')}  Reden: {outcome.get('reason', '')}")
    print("\n===== einde =====")
