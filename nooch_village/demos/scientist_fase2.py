"""Fase 2 van de Scientist-ombouw: loodst drie governance-mutaties door het echte proces.

Volgorde:
  1. ADD_ROLE harry_hemp   → passeert G0-G4 → direct aangenomen (Secretary)
  2. REMOVE_ROLE tijdgeest_wachter → faalt G3 → human inbox (jij keurt goed)
  3. REMOVE_ROLE kennis_scout      → faalt G3 → human inbox (jij keurt goed)

Na afloop toont het script de inbox-IDs voor de twee escalaties zodat jij ze kunt goedkeuren:
  python -m nooch_village.inbox approve <id> "<reden>"
"""
from __future__ import annotations
import time
import logging
from nooch_village.village import Village
from nooch_village.event_bus import Event
from nooch_village.models import Proposal, GovernanceChange, ChangeKind


_TIMEOUT = 10   # seconden per voorstel


def scientist_fase2() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(name)s %(message)s")
    log = logging.getLogger("fase2")

    v = Village(heartbeat_seconds=86400)

    # ── event-collectors ────────────────────────────────────────────────────
    adopted:   list[dict] = []
    escalated: list[dict] = []
    invalid:   list[dict] = []

    v.bus.subscribe("governance_changed",          lambda e: adopted.append(dict(e.data)))
    v.bus.subscribe("governance_review_requested", lambda e: escalated.append(dict(e.data)))
    v.bus.subscribe("proposal_invalid",            lambda e: invalid.append(dict(e.data)))

    v.start()
    time.sleep(0.2)

    print("\n══════════════════════════════════════════════════════════════════")
    print(" Scientist fase 2 — drie governance-mutaties")
    print("══════════════════════════════════════════════════════════════════\n")

    # ── 1. ADD_ROLE harry_hemp ───────────────────────────────────────────────
    print("① ADD_ROLE harry_hemp ...")
    snap_adopted   = len(adopted)
    snap_escalated = len(escalated)
    snap_invalid   = len(invalid)

    p_add = Proposal(
        proposer_role="human",
        change=GovernanceChange(
            kind=ChangeKind.ADD_ROLE,
            role_id="harry_hemp",
            purpose=(
                "Observeert de lange culturele taalverschuiving (ngram) en grondt "
                "kandidaat-termen in wetenschappelijke literatuur"
            ),
            add_accountabilities=[
                "wekelijks de ngram-frequentie van missie-termen meten en stijgende "
                "termen voorstellen als keyword_proposed",
                "keyword_proposed-events gronden in wetenschappelijk bewijs via "
                "OpenAlex en Semantic Scholar en het resultaat publiceren als keyword_evidence",
                "tijdgeest-signalen publiceren bij ≥2 termen die structureel dezelfde "
                "richting op bewegen",
            ],
            add_skills=["ngram_culture", "openalex_evidence", "semscholar_tldr",
                        "openlibrary_search_inside"],
            new_role_parent="noochville",
        ),
        tension=(
            "TijdgeestWachter en KennisScout zijn twee losse rollen die structureel "
            "wekelijks van elkaars output afhankelijk zijn. HarryHemp consolideert "
            "beide verantwoordelijkheden in één inwoner met één DNA en één grens."
        ),
        trigger_example=(
            "De wekelijkse ngram-puls en de academische grounding zijn doorlopend "
            "gekoppeld: elke stijgende term uit ngram-data vraagt structureel grounding. "
            "Meermaals gecombineerd in tests en dagelijkse ochtendcyclus."
        ),
        rationale=(
            "Consolidatie verlaagt overhead en maakt de koppeling expliciet in één rol. "
            "HarryHemp erft de accountabilities van beide bronrollen structureel en "
            "doorlopend — identiek aan wat tijdgeest_wachter en kennis_scout nu doen."
        ),
        source="sensed",
    )

    v.submit_proposal(p_add)
    deadline = time.time() + _TIMEOUT
    while time.time() < deadline:
        if len(adopted) > snap_adopted or len(escalated) > snap_escalated or len(invalid) > snap_invalid:
            break
        time.sleep(0.1)

    add_result = _classify(adopted, escalated, invalid, snap_adopted, snap_escalated, snap_invalid)
    _print_result("ADD_ROLE harry_hemp", add_result, adopted, escalated, invalid,
                  snap_adopted, snap_escalated)

    # ── 2. REMOVE_ROLE tijdgeest_wachter ────────────────────────────────────
    print("\n② REMOVE_ROLE tijdgeest_wachter ...")
    snap_adopted   = len(adopted)
    snap_escalated = len(escalated)
    snap_invalid   = len(invalid)

    p_rm_tw = Proposal(
        proposer_role="human",
        change=GovernanceChange(
            kind=ChangeKind.REMOVE_ROLE,
            role_id="tijdgeest_wachter",
        ),
        tension=(
            "TijdgeestWachter's accountabilities zijn volledig overgenomen door HarryHemp. "
            "De rol blijft anders als lege structuur bestaan naast zijn opvolger."
        ),
        trigger_example=(
            "Na ADD_ROLE harry_hemp structureel overbodig: ngram-puls en tijdgeest-signalen "
            "draaien doorlopend via HarryHemp."
        ),
        rationale=(
            "Consolidatie: één inwoner met één DNA beheert de tijdgeest-observatie voortaan "
            "structureel en doorlopend. TijdgeestWachter heeft geen resterende unieke accountability."
        ),
        source="sensed",
    )

    v.submit_proposal(p_rm_tw)
    deadline = time.time() + _TIMEOUT
    while time.time() < deadline:
        if len(adopted) > snap_adopted or len(escalated) > snap_escalated or len(invalid) > snap_invalid:
            break
        time.sleep(0.1)

    rm_tw_result = _classify(adopted, escalated, invalid, snap_adopted, snap_escalated, snap_invalid)
    _print_result("REMOVE_ROLE tijdgeest_wachter", rm_tw_result, adopted, escalated, invalid,
                  snap_adopted, snap_escalated)

    # ── 3. REMOVE_ROLE kennis_scout ─────────────────────────────────────────
    print("\n③ REMOVE_ROLE kennis_scout ...")
    snap_adopted   = len(adopted)
    snap_escalated = len(escalated)
    snap_invalid   = len(invalid)

    p_rm_ks = Proposal(
        proposer_role="human",
        change=GovernanceChange(
            kind=ChangeKind.REMOVE_ROLE,
            role_id="kennis_scout",
        ),
        tension=(
            "KennisScout's accountabilities zijn volledig overgenomen door HarryHemp. "
            "De rol blijft anders als lege structuur bestaan naast zijn opvolger."
        ),
        trigger_example=(
            "Na ADD_ROLE harry_hemp structureel overbodig: academische grounding via "
            "OpenAlex en Semantic Scholar draaien doorlopend via HarryHemp."
        ),
        rationale=(
            "Consolidatie: HarryHemp beheert de grounding-tak voortaan structureel en "
            "doorlopend. KennisScout heeft geen resterende unieke accountability."
        ),
        source="sensed",
    )

    v.submit_proposal(p_rm_ks)
    deadline = time.time() + _TIMEOUT
    while time.time() < deadline:
        if len(adopted) > snap_adopted or len(escalated) > snap_escalated or len(invalid) > snap_invalid:
            break
        time.sleep(0.1)

    rm_ks_result = _classify(adopted, escalated, invalid, snap_adopted, snap_escalated, snap_invalid)
    _print_result("REMOVE_ROLE kennis_scout", rm_ks_result, adopted, escalated, invalid,
                  snap_adopted, snap_escalated)

    v.stop()

    # ── samenvatting + volgende stap ────────────────────────────────────────
    print("\n══════════════════════════════════════════════════════════════════")
    print(" Samenvatting")
    print("══════════════════════════════════════════════════════════════════\n")

    pending_inbox = v.human_inbox.pending()
    escalations = [i for i in pending_inbox if i["type"] == "escalation"]
    if escalations:
        print(f"  {len(escalations)} escalatie(s) wachten op jouw goedkeuring:\n")
        for item in escalations:
            ctx   = item["context"]
            kind  = ctx.get("change_kind", "?")
            rid   = ctx.get("proposal_id", item["subject"])[:8]
            gate  = ctx.get("gate", "?")
            subj  = item["subject"]
            print(f"    [{item['id']}]  {kind:<14}  {subj:<28}  poort {gate}")
            print(f"      reden: {ctx.get('gate_reason','')[:80]}")
            print()
        print("  Keur goed met:")
        for item in escalations:
            print(f"    python -m nooch_village.inbox approve {item['id']} \"<reden>\"")
    else:
        print("  Geen pending escalaties.")

    print()


def _classify(adopted, escalated, invalid, sa, se, si) -> str:
    if len(adopted) > sa:
        return "adopted"
    if len(escalated) > se:
        return "escalated"
    if len(invalid) > si:
        return "invalid"
    return "timeout"


def _print_result(label, result, adopted, escalated, invalid, snap_adopted, snap_escalated):
    icons = {"adopted": "✅", "escalated": "🙋", "invalid": "❌", "timeout": "⏱"}
    print(f"  {icons.get(result, '?')} {label}: {result.upper()}")
    if result == "adopted":
        ev = adopted[-1]
        print(f"     governance_changed v={ev.get('kind')} rol={ev.get('role_id')}")
    elif result == "escalated":
        ev = escalated[-1]
        print(f"     poort {ev.get('gate')}: {ev.get('reason','')[:80]}")
    elif result == "invalid":
        ev = invalid[-1]
        print(f"     G0: {ev.get('reason','')[:80]}")
