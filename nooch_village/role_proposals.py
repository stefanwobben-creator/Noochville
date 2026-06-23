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
