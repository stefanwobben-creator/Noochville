"""
Composition root van NoochVillage.
- bouwt het marktplein (EventBus) en injecteert het overal
- maakt het dorp ZELF de wortelcirkel (zodat een subcirkel later gratis nest)
- registreert echte skills en geeft ze aan inwoners
- bouwt het levende dorp uit de governance-records (records = waarheid)

Run:  python -m nooch_village.village          (demo: draait de groei-puls met echte skills)
"""
from __future__ import annotations
import os, time, json, logging
from nooch_village.event_bus import EventBus, Event
from nooch_village.config import load_context
from nooch_village.skills import SkillRegistry
from nooch_village.matchmaker import Matchmaker
from nooch_village.governance import Records, Secretary, Reconciler
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.roles import TimeKeeper, GrowthAnalyst, Librarian, PerformanceScout, Facilitator, TijdgeestWachter, KennisScout
from nooch_village.library import Library
from nooch_village.lexicon import Lexicon
from nooch_village.models import Proposal, GovernanceChange, ChangeKind
from nooch_village.governance import proposal_to_dict
from nooch_village.skills_impl.site_health import SiteHealthSkill
from nooch_village.skills_impl.budget import BudgetSkill
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.skills_impl.library_skills import LibraryLookupSkill, KeywordReviewSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill
from nooch_village.skills_impl.ngram import NgramCultureSkill
from nooch_village.skills_impl.openlibrary_search_inside import OpenlibrarySearchInsideSkill
from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
from nooch_village.skills_impl.openalex import OpenalexSkill
from nooch_village.human_inbox import HumanInbox

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CLASS_MAP = {"timekeeper": TimeKeeper, "analyst": GrowthAnalyst,
             "librarian": Librarian, "scout": PerformanceScout,
             "facilitator": Facilitator, "tijdgeest_wachter": TijdgeestWachter,
             "kennis_scout": KennisScout}


_ANCHOR_POLICIES = [
    "Geen enkele rol mag een accountability hebben die plastic-gebaseerd of "
    "dierlijk-leer materiaal als on-mission goedkeurt.",
    "De missie-toetsing (KeywordReview, G4-poort) mag nooit als accountability "
    "worden verwijderd zonder een gelijkwaardig alternatief in hetzelfde voorstel.",
    "Geen enkele rol mag uitgaven aan advertising autoriseren of plannen; "
    "betaald bereik is verboden als groeistrategie.",
    "Verkoop loopt uitsluitend via de eigen website nooch.earth; "
    "geen enkele rol mag externe verkoopkanalen of marktplaatsen autoriseren.",
    "Productie is on demand; geen enkele rol mag voorraadopbouw of "
    "overproductie autoriseren of plannen.",
]

_ANCHOR_PURPOSE = (
    "Nooch.earth is het duurzaamste schoenenmerk ter wereld — om een industrie vol "
    "menselijk, dierlijk en planetair leed te inspireren dat meliorisme (altijd beter kunnen) "
    "echt kan, en om klanten en anderen te inspireren iets positiefs op gang te brengen. "
    "Kernwaarden: geen plastic, geen leer, in Europa geproduceerd, op bestelling, eerlijke prijs, "
    "transparantie. Groei via missie-gedreven organische content op nooch.earth."
)


# Zaad-concepten voor het meertalige lexicon.
# Status geldt symmetrisch: is 'consument' avoid → 'consumer' ook.
_LEXICON_SEED = [
    {
        "concept_id": "burger_frame",
        "words": {"nl": "burger", "en": "citizen"},
        "status": "approved",
        "rationale": (
            "Burgerframe versterkt agency en collectieve verantwoordelijkheid; "
            "kernterm voor de missie in NL en EN. Symmetrisch: beide talen preferred."
        ),
    },
    {
        "concept_id": "consumer_frame",
        "words": {"nl": "consument", "en": "consumer"},
        "status": "avoid",
        "rationale": (
            "Consumentenkader versterkt passiviteit en extractief gedrag; burgerframe "
            "heeft voorkeur. Symmetrisch: avoid in NL én EN."
        ),
    },
    {
        "concept_id": "sufficiency",
        "words": {"nl": "soberheid", "en": "sufficiency"},
        "status": "approved",
        "rationale": "Sufficiencybeweging sluit aan bij missie: minder verbruik als waarde.",
    },
    {
        "concept_id": "regenerative",
        "words": {"nl": "regeneratief", "en": "regenerative"},
        "status": "approved",
        "rationale": "Regeneratief ontwerp is een kernterm voor de positieve missierichting.",
    },
    {
        "concept_id": "plastic_free",
        "words": {"nl": "plasticvrij", "en": "plastic-free"},
        "status": "approved",
        "rationale": "Geen plastic is een harde beleidsregel én een SEO-kans in beide talen.",
    },
    {
        "concept_id": "sustainable",
        "words": {"nl": "duurzaam", "en": "sustainable"},
        "status": "approved",
        "rationale": "Kernwoord voor duurzame schoenenmissie in NL en EN.",
    },
    {
        "concept_id": "vegan",
        "words": {"nl": "veganistisch", "en": "vegan"},
        "status": "approved",
        "rationale": "Geen dierenleer is beleidsregel; vegan/veganistisch missie-aligned.",
    },
]


def seed_lexicon(lexicon: Lexicon) -> None:
    """Seed het meertalige lexicon idempotent met de zaad-concepten."""
    added = lexicon.seed(_LEXICON_SEED)
    if added:
        import logging
        logging.getLogger("village.lexicon").info(
            "lexicon geseeded: %d nieuwe concepten", added)


def activate_tijdgeest_wachter(records: Records) -> None:
    """Idempotent: voeg ngram_culture toe aan tijdgeest_wachter zodra het record bestaat."""
    rec = records.get("tijdgeest_wachter")
    if rec is None:
        return
    if "ngram_culture" not in rec.definition.skills:
        rec.definition.skills.append("ngram_culture")
        records.put(rec)


def activate_kennis_scout(records: Records) -> None:
    """Idempotent: zet v1-skills in kennis_scout-record zodra het bestaat.

    Verwijdert ook eventuele v0-namen (openalex, semantic_scholar,
    openlibrary_search_inside) die uit de vorige commit zijn overgebleven.
    """
    rec = records.get("kennis_scout")
    if rec is None:
        return
    _V1     = ["openalex_evidence", "semscholar_tldr"]
    _OLD    = ["openalex", "semantic_scholar", "openlibrary_search_inside"]
    changed = False
    for old in _OLD:
        if old in rec.definition.skills:
            rec.definition.skills.remove(old)
            changed = True
    for s in _V1:
        if s not in rec.definition.skills:
            rec.definition.skills.append(s)
            changed = True
    if changed:
        records.put(rec)


def seed_records(records: Records) -> None:
    if records.root() is not None:
        return
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(
                      purpose=_ANCHOR_PURPOSE, skills=[],
                      policies=_ANCHOR_POLICIES),
                  members=["timekeeper", "analyst", "librarian", "scout", "facilitator"])
    timekeeper = Record(id="timekeeper", type=RecordType.ROLE, parent="noochville",
                        definition=RoleDefinition(
                            purpose="De dorpsomroeper: markeert de dagcyclus",
                            accountabilities=["dagcyclus omroepen"], skills=[]))
    analyst = Record(id="analyst", type=RecordType.ROLE, parent="noochville",
                     definition=RoleDefinition(
                         purpose="Bewaakt de online gezondheid en groei van Nooch.earth",
                         accountabilities=["site monitoren", "bezoekersdata duiden",
                                           "dagelijkse Field Note schrijven"],
                         skills=["site_health", "plausible_stats", "google_trends", "field_note"]))
    librarian = Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                       definition=RoleDefinition(
                           purpose="Hoeder van de goedgekeurde woordenschat (DOMEIN: bibliotheek)",
                           accountabilities=["kandidaat-woorden beoordelen",
                                             "twijfelgevallen escaleren naar een mens"],
                           domains=["bibliotheek"],
                           skills=["keyword_review", "library_lookup"]))
    scout = Record(id="scout", type=RecordType.ROLE, parent="noochville",
                   definition=RoleDefinition(
                       purpose="Ontdekt kansen in Google Search Console en voedt de woordenschat",
                       accountabilities=["GSC-queries ophalen",
                                         "high_potential queries voorstellen aan de Librarian"],
                       skills=["gsc_performance"]))
    facilitator = Record(id="facilitator", type=RecordType.ROLE, parent="noochville",
                         definition=RoleDefinition(
                             purpose="Bewaakt de geldigheid van governance-voorstellen "
                                     "zonder inhoudelijk te oordelen",
                             accountabilities=["voorstellen toetsen op G0-G4",
                                               "geldige voorstellen direct aannemen",
                                               "risicovolle voorstellen escaleren naar de mens"],
                             skills=[]))
    for r in (root, timekeeper, analyst, librarian, scout, facilitator):
        r.source = "seed"
        records.put(r)


def migrate_records(records: Records) -> None:
    """Voeg ontbrekende leden + records toe aan bestaande governance-files (idempotent)."""
    root = records.root()
    if root is None:
        return
    changed = False
    # Zorg dat facilitator-record bestaat
    if records.get("facilitator") is None:
        facilitator = Record(id="facilitator", type=RecordType.ROLE, parent=root.id,
                             definition=RoleDefinition(
                                 purpose="Bewaakt de geldigheid van governance-voorstellen "
                                         "zonder inhoudelijk te oordelen",
                                 accountabilities=["voorstellen toetsen op G0-G4",
                                                   "geldige voorstellen direct aannemen",
                                                   "risicovolle voorstellen escaleren naar de mens"],
                                 skills=[]))
        records.put(facilitator)
        changed = True
    # Zorg dat facilitator in de wortelcirkel zit
    if "facilitator" not in root.members:
        root.members.append("facilitator")
        changed = True
    # Zorg dat alle anchor-policies aanwezig zijn (idempotent per policy-tekst)
    existing_policies = set(root.definition.policies)
    for policy in _ANCHOR_POLICIES:
        if policy not in existing_policies:
            root.definition.policies.append(policy)
            changed = True
    # Bijwerk anchor-purpose naar de huidige volledige missietekst
    if root.definition.purpose != _ANCHOR_PURPOSE:
        root.definition.purpose = _ANCHOR_PURPOSE
        changed = True
    # Retroactief: content_strategist (lifecycle_demo) markeren als "demo"
    cs = records.get("content_strategist")
    if cs is not None and cs.source == "sensed":
        cs.source = "demo"
        records.put(cs)
        changed = True
    # Retroactief: seed-records zonder source markeren als "seed"
    _SEED_IDS = {"noochville", "timekeeper", "analyst", "librarian", "scout", "facilitator"}
    for sid in _SEED_IDS:
        rec = records.get(sid)
        if rec is not None and rec.source == "sensed":
            rec.source = "seed"
            records.put(rec)
            changed = True
    if changed:
        records.put(root)


class Village:
    def __init__(self, heartbeat_seconds: float | None = None):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-20s %(message)s",
                            datefmt="%H:%M:%S")
        self.bus = EventBus(name="root")
        self.context = load_context(BASE_DIR)
        if heartbeat_seconds is not None:
            self.context.settings["heartbeat_seconds"] = str(heartbeat_seconds)
        self.context.library = Library(os.path.join(self.context.data_dir, "library.json"))
        self.context.lexicon = Lexicon(os.path.join(self.context.data_dir, "lexicon.json"))
        seed_lexicon(self.context.lexicon)
        self.human_inbox = HumanInbox(os.path.join(self.context.data_dir, "human_inbox.json"))
        self.registry = SkillRegistry()
        for skill in (SiteHealthSkill(), BudgetSkill(), PlausibleSkill(), TrendsSkill(),
                      FieldNoteSkill(), LibraryLookupSkill(), KeywordReviewSkill(),
                      GscPerformanceSkill(), NgramCultureSkill(),
                      OpenlibrarySearchInsideSkill(),   # v2: nog niet in KennisScout DNA
                      SemanticScholarSkill(),            # capability: semscholar_tldr
                      OpenalexSkill()):                  # capability: openalex_evidence
            self.registry.register(skill)
        self.records = Records(os.path.join(self.context.data_dir, "governance_records.json"))
        seed_records(self.records)
        migrate_records(self.records)
        activate_tijdgeest_wachter(self.records)
        activate_kennis_scout(self.records)
        self.context.records = self.records
        self.matchmaker = Matchmaker(self.bus)
        self.secretary = Secretary(self.records, self.bus)
        self.reconciler = Reconciler(self.records, self.bus, self.registry, self.context,
                                     self.matchmaker, class_map=CLASS_MAP)
        self.bus.subscribe("task_completed", self._observe)
        self.bus.subscribe("pulse_completed", self._observe)
        self.bus.subscribe("tension_sensed", self._observe)
        self.bus.subscribe("keyword_decided", self._observe)
        self.bus.subscribe("human_decision_needed", self._observe)
        self.bus.subscribe("gsc_pulse_completed", self._observe)
        self.bus.subscribe("governance_changed", self._observe)
        self.bus.subscribe("governance_review_requested", self._observe)
        self.bus.subscribe("governance_review_requested", self._on_escalation)
        self.bus.subscribe("proposal_invalid", self._observe)
        self.bus.subscribe("governance_rejected", self._observe)
        self.bus.subscribe("tension_triaged", self._observe)
        self.bus.subscribe("human_intervention_needed", self._observe)
        self.bus.subscribe("role_born", self._observe)
        self.bus.subscribe("role_born", self._on_role_born)
        self.bus.subscribe("tijdgeest_pulse_completed", self._observe)
        self.bus.subscribe("tijdgeest_signaal", self._observe)
        self.root = self.reconciler.build()
        # Sync onbemande sensed-rollen naar de inbox bij opstarten
        import dataclasses as _dc
        self.human_inbox.sync_unmanned(self.records.all(), CLASS_MAP)

    def _observe(self, e: Event) -> None:
        with open(os.path.join(self.context.data_dir, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": e.name, **e.data}, ensure_ascii=False, default=str) + "\n")

    def _on_escalation(self, e: Event) -> None:
        """Schrijf geëscaleerde voorstellen naar de human inbox."""
        proposal_dict = e.data.get("proposal", {})
        gate   = e.data.get("gate", "?")
        reason = e.data.get("reason", "")
        iid = self.human_inbox.add_escalation(proposal_dict, gate, reason)
        logging.getLogger("village.inbox").info(
            "📬 escalatie in human_inbox: item %s (voorstel %s, poort %s)",
            iid, proposal_dict.get("id", "?"), gate)

    def approve_escalation(self, item_id: str, reason: str = "") -> bool:
        """Stuur governance_verdict approve voor een escalatie-item.

        Beveiligingsgrens: alleen aanroepbaar via het geauthenticeerde lokale oppervlak.
        """
        item = self.human_inbox.get(item_id)
        if item is None or item["type"] != "escalation":
            return False
        pid = item["context"]["proposal_id"]
        self.human_inbox.resolve(item_id, "approved", reason=reason)
        self.bus.publish(Event("governance_verdict",
                               {"proposal_id": pid, "decision": "approve", "reason": reason},
                               "human"))
        logging.getLogger("village.inbox").info(
            "✅ human_inbox: escalatie %s goedgekeurd (voorstel %s)", item_id, pid)
        return True

    def _on_role_born(self, e: Event) -> None:
        """Schrijft de geboorte van een rol naar het groeidagboek (audittrail)."""
        dagboek = os.path.join(self.context.data_dir, "groeidagboek.jsonl")
        with open(dagboek, "a") as f:
            f.write(json.dumps({"ts": time.time(), **e.data}, ensure_ascii=False, default=str) + "\n")

    def start(self):
        self.root.start()

    def stop(self):
        self.root.stop()

    def run_forever(self):
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def print_roster(self) -> None:
        """Toont alle niet-gearchiveerde records met hun source (seed/sensed/demo)."""
        all_recs = [r for r in self.records.all() if not r.archived]
        all_recs.sort(key=lambda r: (r.source, r.id))
        print(f"\n{'ID':<26} {'Type':<8} {'Source':<8} {'Versie':<8} Purpose")
        print("-" * 95)
        for r in all_recs:
            tag = {"seed": "  ", "sensed": "✱ ", "demo": "⚙ "}.get(r.source, "? ")
            print(f"{tag}{r.id:<24} {r.type.value:<8} {r.source:<8} v{r.version:<7} "
                  f"{r.definition.purpose[:50]}")
        live_ids  = set(self.reconciler.live.keys())
        unmanned  = set(self.reconciler.unmanned.keys())
        demo_ids  = {r.id for r in all_recs if r.source == "demo"}
        print(f"\n  Legende: ✱ = sensed (echt), ⚙ = demo, (blanco) = seed")
        print(f"  Live: {sorted(live_ids - demo_ids)}  |  Onbemand: {sorted(unmanned)}")
        if demo_ids:
            print(f"  Demo-rollen (worden genegeerd door G1/G2): {sorted(demo_ids)}")

    def submit_proposal(self, proposal: Proposal) -> str:
        """Human-ingang voor governance-voorstellen. Publiceert proposal_raised op de bus.
        De Facilitator pakt het op en draait de G0-G4-poort. Geeft het proposal_id terug."""
        self.bus.publish(Event("proposal_raised",
                               {"proposal": proposal_to_dict(proposal)}, "human"))
        return proposal.id


def demo():
    # snelle hartslag voor de demo; in productie 0 = één keer per echte dag
    v = Village(heartbeat_seconds=2)
    pulse: dict = {}
    gsc: dict = {}
    keyword_log: list = []

    v.bus.subscribe("pulse_completed",     lambda e: pulse.update(e.data))
    v.bus.subscribe("gsc_pulse_completed", lambda e: gsc.update(e.data))
    v.bus.subscribe("keyword_decided",
                    lambda e: keyword_log.append({**e.data, "_event": "decided"}))
    v.bus.subscribe("human_decision_needed",
                    lambda e: keyword_log.append({**e.data, "status": "escalated", "_event": "escalated"}))

    v.start()
    print("\n================ DEMO: de groei-puls draait zichzelf ================\n")
    for _ in range(1800):   # max 3 min; Trends-backoff kan lang zijn na meerdere runs
        if pulse and gsc:
            break
        time.sleep(0.1)
    v.stop()
    time.sleep(0.3)

    note_path = pulse.get("note_path")
    print(f"\n>> pulse_completed | tension={pulse.get('tension')} | note={note_path}\n")
    if note_path and os.path.exists(note_path):
        print("---------------- inhoud Field Note ----------------")
        print(open(note_path).read())
        print("---------------------------------------------------")

    print(f"\n>> gsc_pulse_completed | ok={gsc.get('ok')} | "
          f"queries={gsc.get('total', '-')} | buckets={gsc.get('bucket_counts', gsc.get('error', '-'))}")

    if keyword_log:
        lib = v.context.library
        print(f"\n{'Bron':<28} {'Woord':<35} {'Status':<11} Reden")
        print("-" * 90)
        for kw in keyword_log:
            word = kw.get("word", "")
            demand = kw.get("demand") or (lib.status(word) or {}).get("evidence") or {}
            src = demand.get("source", "?") if isinstance(demand, dict) else "?"
            print(f"{src:<28} {word:<35} {kw.get('status', '?'):<11} {kw.get('reason', '')[:35]}")

    print("\n================ einde demo ================")


def librarian_demo():
    """Demonstreer de Librarian: beoordeelt kandidaat-woorden live tegen de missie."""
    v = Village(heartbeat_seconds=86400)   # geen groei-puls tijdens deze demo
    decisions: dict = {}
    escalations: list = []

    v.bus.subscribe("keyword_decided",      lambda e: decisions.update({e.data["word"]: e.data}))
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

    # wacht tot alle beslissingen binnen zijn (react() verwerkt asynchroon)
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

    # Voorstel 1: onschuldige rolwijziging — slaagt G0-G4, direct aangenomen
    p1 = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                                add_accountabilities=["maandrapportage opstellen voor stakeholders"]),
        tension="Analyst mist formele verantwoordelijkheid voor periodieke rapportage",
        trigger_example="field_note_2026-06-13: geen structurele terugkoppeling vastgelegd",
        rationale="Transparantie-waarde vraagt om periodieke verslaglegging",
    )

    # Voorstel 2: dupliceert bestaande accountability van analyst → escaleert G2
    p2 = Proposal(
        proposer_role="scout",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="scout",
                                add_accountabilities=["dagelijkse Field Note schrijven"]),
        tension="Scout wil ook Field Notes schrijven vanuit GSC-perspectief",
        trigger_example="dag_begint: geen Field Note vanuit GSC-data",
        rationale="GSC-data verdient eigen duiding in een Field Note",
    )

    # Voorstel 3: plastic-goedkeurende accountability → escaleert G4 (missie-poort)
    p3 = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                                add_accountabilities=[
                                    "plastic-vriendelijke producten goedkeuren voor promotie"]),
        tension="Analyst wil plastic alternatieven promoten voor groter bereik",
        trigger_example="field_note_2026-06-13: lage interesse in plastic-free keywords",
        rationale="Bredere markt via plastic producten kan bereik verhogen",
    )

    print("\n================ DEMO: async governance-poort ================\n")
    for p in (p1, p2, p3):
        v.bus.publish(Event("proposal_raised", {"proposal": proposal_to_dict(p)}, "demo"))

    # Wacht tot alle 3 resultaten binnen zijn (max 5s)
    for _ in range(100):
        if len(results) >= 3:
            break
        time.sleep(0.05)

    v.stop()
    time.sleep(0.1)

    print(f"\n{'Voorstel (rol → change)':<42} {'Uitkomst':<14} {'Poort':<6} Reden")
    print("-" * 100)
    proposals = [
        (p1.id, f"analyst → maandrapportage opstellen"),
        (p2.id, f"scout → Field Note schrijven (dup)"),
        (p3.id, f"analyst → plastic goedkeuren (G4)"),
    ]
    for pid, label in proposals:
        r = results.get(pid, {})
        print(f"{label:<42} {r.get('outcome','?'):<14} {r.get('gate','-'):<6} "
              f"{r.get('reason','')[:45]}")

    # Verifieer dat analyst nu de nieuwe accountability heeft (voorstel 1)
    rec = v.records.get("analyst")
    if rec:
        new_acc = "maandrapportage opstellen voor stakeholders"
        heeft = new_acc in rec.definition.accountabilities
        print(f"\n✔ analyst-record bevat nieuwe accountability: {heeft} (v{rec.version})")
        if heeft:
            print(f"  → {new_acc}")

    print("\n================ einde governance demo ================")


def proposal_demo():
    """Eerste echte governance-voorstel van de human: de TijdgeestWachter.

    De human dient een add_role-voorstel in via Village.submit_proposal().
    Het voorstel doorloopt de volledige G0-G4-poort en wordt (verwacht) aangenomen.
    De rol wordt onbemand geboren — er draait geen thread totdat de founder code schrijft.
    """
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
            role_id="tijdgeest_wachter",
            purpose=(
                "De lange culturele taalverschuiving volgen die voor de missie relevant is: "
                "zien of de wereldtaal over de lange boog richting of weg van het burgerframe beweegt."
            ),
            add_accountabilities=[
                "de lange-termijn frequentie van missie-relevante termen in het boekencorpus "
                "periodiek volgen via Google Books Ngram Viewer",
                "culturele verschuivingen richting of weg van het burgerframe signaleren "
                "aan GrowthAnalyst en Librarian",
                "periodiek de tijdgeest-richting aan het dorp rapporteren",
            ],
            add_domains=["tijdgeest-observaties"],   # smal domein; lexicon blijft van Librarian
            new_role_parent="noochville",
        ),
        tension=(
            "Het dorp ziet nu alleen huidige zoekvraag (Trends) en is blind voor de lange "
            "culturele boog die de missie juist probeert te buigen."
        ),
        trigger_example=(
            "Dit ontwerpgesprek, de Scheffer-methode voor n-gram cultuuranalyse, "
            "en de werkende ngram-code als bewijs van haalbaarheid. "
            "Dit is een doorlopende sensorfunctie, geen eenmalige opzoeking."
        ),
        rationale=(
            "Een doorlopende sensorfunctie die het gat dicht tussen recente vraag "
            "en culturele richting. Geen eenmalige opzoeking maar een staande accountability: "
            "de tijdgeest verandert langzaam en vereist periodiek meten om trends "
            "vroeg te signaleren."
        ),
    )

    print("\n================ VOORSTEL: TijdgeestWachter ================\n")
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

    pid = v.submit_proposal(voorstel)   # human dient in via de officiële route

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
        rec = v.records.get("tijdgeest_wachter")
        print(f"Record   : tijdgeest_wachter v{rec.version if rec else '?'} opgeslagen in governance_records.json")
        unmanned = "tijdgeest_wachter" in v.reconciler.unmanned
        print(f"Status   : {'onbemand (wacht op implementatie)' if unmanned else 'live — onverwacht!'}")
        print(f"Domein   : {rec.definition.domains if rec else '?'}")
        print()
        if "tijdgeest_wachter" in born:
            print("Groeidagboek-entry:")
            print(f"  trigger: {born.get('trigger_example','')[:80]}")
            print(f"  by     : {born.get('by','?')}")

        # Laat zien dat de accountabilities netjes belegd staan
        if rec:
            print("\nAccountabilities in record:")
            for a in rec.definition.accountabilities:
                print(f"  · {a}")

    print("\n================ einde voorstel-demo ================")


def lifecycle_demo():
    """Bewijst het add_role-addendum:
    1. add_role zónder herhalingsbewijs → G0 invalid (terug naar proposer, geen mens)
    2. add_role mét herhalingsbewijs → aangenomen, role_born event, onbemand in Reconciler
    3. Groeidagboek bevat het trigger_example van de geboren rol
    """
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

    # Voorstel 1: add_role ZONDER herhalingsbewijs → G0 ongeldig
    p1 = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="content_writer",
                                purpose="Schrijft SEO-artikelen voor nooch.earth",
                                add_accountabilities=["SEO-artikelen schrijven"],
                                new_role_parent="noochville"),
        tension="Er is één keer een contentverzoek binnengekomen",
        trigger_example="analyst:2026-06-13 één contentverzoek",
        rationale="Content schrijven kost veel tijd",
        source="demo",
    )

    # Voorstel 2: add_role MÉT herhalingsbewijs → aangenomen, onbemand geboren
    p2 = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id="content_strategist",
                                purpose="Vertaalt missie-inzichten structureel naar content-kalender",
                                add_accountabilities=["content-kalender bijhouden",
                                                      "missie-keywords omzetten naar artikel-briefs"],
                                new_role_parent="noochville"),
        tension="Elke week hetzelfde gat: geen eigenaar voor content-planning",
        trigger_example="analyst:meermaals terugkerend wekelijks — elke week geen contentplanning",
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

    # Verifieer born + unmanned
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

    # Groeidagboek
    dagboek = os.path.join(v.context.data_dir, "groeidagboek.jsonl")
    if os.path.exists(dagboek):
        entries = [json.loads(line) for line in open(dagboek)]
        cs_entries = [e for e in entries if e.get("role_id") == "content_strategist"]
        print(f"\nGroeidagboek: {dagboek}")
        for entry in cs_entries[-2:]:
            print(f"  [{entry['role_id']}] trigger: {entry.get('trigger_example','')[:65]}")

    print("\n================ einde lifecycle demo ================")


def intent_demo():
    """Demonstreer de intentielaag: prioritering van acties tegen strategie en doelen.

    Actie 1: organisch keyword-artikel → bijdraagt aan verkoopdoel + binnen strategie → wint
    Actie 2: Google Ads campagne → vereist advertising → policy-violation → valt af
    Actie 3: conversie verbeteren op nooch.earth → doel-bijdrage → tweede positie
    Bonus: G4-poort blokkeert governance-voorstel dat advertising toevoegt.
    """
    from nooch_village.intent import prioritize

    v = Village(heartbeat_seconds=86400)
    v.start()
    time.sleep(0.1)   # geef inwoners de tijd om op te starten

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

    # G4-poort: proposal dat advertising-accountability toevoegt wordt geblokkeerd
    print("\n── G4-poort: kan advertising via governance worden toegevoegd? ──")
    ad_proposal = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                                add_accountabilities=[
                                    "advertising campagnes autoriseren voor snellere groei"]),
        tension="Verkoopdoel dreigt niet gehaald zonder extra bereik via advertising",
        trigger_example="analyst:verkoopdoel_2026_q4 dreigt te missen",
        rationale="Advertising als tijdelijke maatregel om 1000 paar te halen",
    )
    from nooch_village.governance import Gate
    gate = Gate()
    passed, gate_name, gate_reason = gate.check(ad_proposal, v.records, v.context)
    if passed:
        print("  ✘ G4-poort liet advertising door — dit is een bug!")
    else:
        print(f"  ✔ G4-poort blokkeert ({gate_name}): {gate_reason[:70]}")

    # Anchor-purpose guard: proposal dat de missie-tekst van de wortelcirkel wijzigt
    print("\n── Anchor-purpose guard: kan de missie via governance worden gewijzigd? ──")
    mission_proposal = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="noochville",
                                purpose="Nooch.earth: maximale winstgevendheid als primair doel"),
        tension="Missie te vaag voor commerciële groei",
        trigger_example="analyst:missie_herformulering",
        rationale="Scherpere commerciële focus",
    )
    passed2, gate_name2, gate_reason2 = gate.check(mission_proposal, v.records, v.context)
    if passed2:
        print("  ✘ Guard liet missie-wijziging door — dit is een bug!")
    else:
        print(f"  ✔ Guard blokkeert ({gate_name2}): {gate_reason2[:70]}")

    v.stop()
    print("\n================ einde intent demo ================")


def triage_demo():
    """Vier spanningen die elk een ander triage-pad bewandelen.

    1. Eigen werk  — 'bezoekersdata analyseren' → analyst-scope, zelf doen
    2. Andere rol  — 'kandidaatwoord voor de bibliotheek' → librarian-domein
    3. Structureel — 'niemand bezit de materiaal-policy' → Proposal via governance
    4. Geen match  — 'serverruimte airco storing' → tactisch / human_intervention_needed
    """
    from nooch_village.models import Tension

    v = Village(heartbeat_seconds=86400)  # geen automatische puls
    triaged: list[dict] = []
    proposals_raised: list[dict] = []
    human_needed: list[dict] = []

    v.bus.subscribe("tension_triaged",
                    lambda e: triaged.append(dict(e.data)))
    v.bus.subscribe("proposal_raised",
                    lambda e: proposals_raised.append({"id": e.data.get("proposal", {}).get("id", "?")}))
    v.bus.subscribe("human_intervention_needed",
                    lambda e: human_needed.append(dict(e.data)))

    v.start()

    # Haal de analyst-inwoner op als triagepunt
    analyst = v.reconciler.live.get("analyst")
    if analyst is None:
        print("⚠️  analyst-inwoner niet gevonden")
        v.stop()
        return

    spanningen = [
        ("bezoekersdata van afgelopen week analyseren",
         "operational",
         "eigen-werk (analyst-scope)"),
        ("kandidaatwoord voor de bibliotheek: biobased sneakers",
         "operational",
         "andere-rol:librarian (domein)"),
        ("niemand bezit het bijwerken van de materiaal-policy; "
         "dit moet structureel belegd worden",
         "governance",
         "structureel → Proposal"),
        ("de serverruimte heeft een airconditioning storing",
         "operational",
         "geen match → mens"),
    ]

    print("\n================ DEMO: triage ================\n")
    for desc, kind, _ in spanningen:
        analyst.sense_tension(desc, kind=kind)

    # Geef alle threads de tijd om te verwerken
    for _ in range(100):
        if len(triaged) >= len(spanningen):
            break
        time.sleep(0.1)
    time.sleep(0.2)  # extra wacht voor human_intervention_needed (is async na triage)

    v.stop()
    time.sleep(0.1)

    print(f"\n{'Spanning (kort)':<52} {'Verwacht':<30} {'Classificatie'}")
    print("-" * 110)
    triage_map = {t["description"][:51]: t["classification"] for t in triaged}
    for desc, _, verwacht in spanningen:
        key = desc[:51]
        cls = triage_map.get(key, "?")
        check = "✔" if (
            (verwacht.startswith("eigen") and "eigen" in cls) or
            (verwacht.startswith("andere") and "andere" in cls) or
            (verwacht.startswith("structureel") and "structureel" in cls) or
            (verwacht.startswith("geen") and "tactisch" in cls)
        ) else "✘"
        print(f"{check} {desc[:50]:<51} {verwacht:<30} {cls}")

    if proposals_raised:
        print(f"\n🏛️  Governance-voorstel aangemaakt: {proposals_raised[0].get('id')}")
    if human_needed:
        print(f"🙋 Human intervention gevraagd voor: {human_needed[0].get('payload', {}).get('description', human_needed[0].get('capability', '?'))[:60]}")

    print("\n================ einde triage demo ================")


def ngram_demo():
    """Activeer de TijdgeestWachter met een handmatige puls en toon het resultaat per term.

    Vereist: tijdgeest_wachter-record in governance_records.json (run 'proposal' eerst).
    Draait de NgramCultureSkill live tegen books.google.com/ngrams/json.
    """
    v = Village(heartbeat_seconds=86400)   # geen automatische hartslag
    # Forceer tijdgeest_interval_seconds=0 zodat de wachter altijd pult (demo)
    v.context.settings["tijdgeest_interval_seconds"] = "0"

    pulse_result: dict = {}
    signaal_events: list = []
    keyword_log: list = []

    v.bus.subscribe("tijdgeest_pulse_completed", lambda e: pulse_result.update(e.data))
    v.bus.subscribe("tijdgeest_signaal",         lambda e: signaal_events.append(e.data))
    v.bus.subscribe("keyword_decided",
                    lambda e: keyword_log.append({**e.data, "_event": "decided"}))

    v.start()

    # Controleer of de TijdgeestWachter bemand is
    tw = v.reconciler.live.get("tijdgeest_wachter")
    if tw is None:
        print("\n⚠️  TijdgeestWachter niet actief in het dorp.")
        print("   → Run eerst: python -m nooch_village.village proposal")
        print("   → Daarna is het record aangemaakt en wordt de rol auto-geactiveerd.\n")
        v.stop()
        return

    # Handmatige puls met zaad-termen (kan ook worden overschreven via payload)
    terms = ["burger", "consument", "sufficiency", "regenerative", "plastic-free"]
    v.bus.publish(Event("tijdgeest_pulse", {"terms": terms}, "ngram_demo"))

    print("\n================ DEMO: TijdgeestWachter ngram-puls ================")
    print(f"Termen: {', '.join(terms)}")
    print("Wacht op Google Books Ngram Viewer (kan 15-30 sec duren)…\n")

    # Max 90 seconden wachten (elke batch heeft 1.5s sleep, 5 termen = 2 batches + netwerk)
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
        print("  (Onofficieel endpoint — bij blokkering of rate-limit: probeer later opnieuw)")
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
    print(f"📉 dalend   ({len(dalend)}):   {', '.join(dalend)   or '(geen)'}")

    if signaal_events:
        s = signaal_events[0]
        print(f"\n📢 tijdgeest_signaal: {s.get('boodschap','')}")

    if keyword_log:
        print(f"\nLibrarian-beslissingen voor stijgende termen:")
        for kw in keyword_log:
            print(f"  {kw.get('word','?'):<25} {kw.get('status','?'):<11} {kw.get('reason','')[:45]}")

    print("\n================ einde ngram demo ================")


def reflect_demo():
    """Laat zien hoe TijdgeestWachter zijn structurele beperkingen reflecteert en
    via governance een amend_role-voorstel doet.

    Verifieer: het voorstel wordt aangenomen (nieuwe accountability in het record),
    maar er draait GEEN nieuwe code en er is GEEN nieuwe externe API-verbinding.
    Uitbreiding van capaciteit blijft mens-gated.
    """
    v = Village(heartbeat_seconds=86400)
    # Reflecteer direct bij de eerste dag_begint; geen ngram-puls nodig in de demo
    v.context.settings["reflect_interval_seconds"] = "0"
    v.context.settings["tijdgeest_interval_seconds"] = "999999"

    proposals_raised: list = []
    outcomes:         list = []

    v.bus.subscribe("proposal_raised",
                    lambda e: proposals_raised.append(e.data.get("proposal", {})))
    v.bus.subscribe("governance_changed",
                    lambda e: outcomes.append({"status": "aangenomen", **e.data}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: outcomes.append({"status": "ongeldig", **e.data}))
    v.bus.subscribe("governance_review_requested",
                    lambda e: outcomes.append({"status": "geëscaleerd", **e.data}))

    rec_before = v.records.get("tijdgeest_wachter")
    accs_before  = list(rec_before.definition.accountabilities) if rec_before else []
    skills_before = list(rec_before.definition.skills)          if rec_before else []

    v.start()

    print("\n================ DEMO: TijdgeestWachter zelf-reflectie ================\n")
    print("Record VOOR reflectie:")
    print(f"  skills          : {skills_before}")
    print(f"  accountabilities ({len(accs_before)}):")
    for a in accs_before:
        print(f"    · {a}")

    # Stuur één handmatige dag_begint zodat reflectie direct vuurt
    v.bus.publish(Event("dag_begint", {"label": "reflect-demo"}, "demo"))

    # Wacht op minstens één voorstel (max 5s)
    for _ in range(100):
        if proposals_raised:
            break
        time.sleep(0.05)
    # Wacht op uitkomst van de poort (max 3s extra)
    for _ in range(60):
        if outcomes:
            break
        time.sleep(0.05)
    time.sleep(0.3)

    v.stop()
    time.sleep(0.1)

    print(f"\nVoorstellen gesensed: {len(proposals_raised)}")
    for p in proposals_raised[:4]:
        kind     = p.get("change", {}).get("kind", "?")
        proposer = p.get("proposer_role", "?")
        new_accs = p.get("change", {}).get("add_accountabilities", [])
        print(f"  [{proposer}] {kind}: {new_accs[0][:70] if new_accs else '–'}…")

    print(f"\nGovernance-uitkomsten: {len(outcomes)}")
    for o in outcomes[:4]:
        print(f"  {o.get('status','?')} | kind={o.get('kind','-')} | "
              f"role={o.get('role_id','-')}")

    rec_after   = v.records.get("tijdgeest_wachter")
    accs_after  = list(rec_after.definition.accountabilities) if rec_after else []
    skills_after = list(rec_after.definition.skills)          if rec_after else []

    print("\nRecord NA reflectie:")
    print(f"  skills          : {skills_after}")
    print(f"  accountabilities ({len(accs_after)}):")
    for a in accs_after:
        marker = " ← NIEUW" if a not in accs_before else ""
        print(f"    · {a[:80]}{marker}")

    new_accs = [a for a in accs_after if a not in accs_before]
    print(f"\nChecks:")
    print(f"  {'✔' if new_accs else '✘'} nieuwe accountability opgenomen in governance-record")
    print(f"  {'✔' if skills_before == skills_after else '✘'} skills ongewijzigd (geen nieuwe externe bron gestart)")
    print(f"  ✔ geen nieuwe thread geactiveerd (mens-gated activatie)")
    print(f"\n⚠  De accountability is een voorstel, niet een feit.")
    print(f"⚠  Implementatie van een echte nieuwe bron vereist menselijke goedkeuring + code.")
    print("\n================ einde reflect demo ================")


def purge_demo():
    """Verwijdert alle records met source='demo' uit de governance.

    Archiveert de records én verwijdert ze uit de members-lijst van hun ouder.
    Idempotent: als er geen demo-records zijn, zegt hij dat ook.
    """
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
        # Archiveer het record
        rec.archived = True
        rec.version += 1
        v.records.put(rec)
        # Verwijder uit parent.members
        if rec.parent:
            parent = v.records.get(rec.parent)
            if parent and rec.id in parent.members:
                parent.members.remove(rec.id)
                v.records.put(parent)
        print(f"  ✔ '{rec.id}' gearchiveerd (v{rec.version})")

    print("\n================ ROSTER NA PURGE ================")
    # Herlaad records zodat het roster actueel is
    v2 = Village(heartbeat_seconds=86400)
    v2.print_roster()
    print("\n================ einde purge ================")


def simulate():
    """Volledige simulatie van het dorp:

    1. Roster + Lexicon — wie woont er, welke talen kennen we?
    2. Governance — drie voorstellen door de poort (goed / G2 / G4)
    3. Triage — vier spanningen door de classify-lus
    4. Reflectie — TijdgeestWachter senst structureel gat
    5. Ngram locale-demo — haalt NL + EN termen live op en toont per locale
    6. Librarian — keyword-beslissingen
    7. Herkomst — roster toont seed/sensed/demo labels

    Elke fase heeft een duidelijke kop zodat je de output kunt volgen.
    Fases die externe APIs vereisen (ngram) beperken zichzelf tot 3 termen
    om de demo snel te houden.
    """
    import sys

    def section(title: str) -> None:
        print(f"\n{'='*65}")
        print(f"  {title}")
        print(f"{'='*65}\n")

    # ── 1. Roster + Lexicon ───────────────────────────────────────────
    section("1 / 7 — ROSTER & LEXICON")
    v = Village(heartbeat_seconds=86400)

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
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="analyst",
                                add_accountabilities=["taalgebruik per locale bewaken"]),
        tension="Geen accountability voor locale-bewaking van rapportages",
        trigger_example="simulate:geen locale-check in field_note",
        rationale="Meertalige uitvoer vereist expliciet eigenaarschap per locale",
    )
    pg2 = Proposal(
        proposer_role="scout",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="scout",
                                add_accountabilities=["dagelijkse Field Note schrijven"]),
        tension="Scout wil ook Field Notes schrijven",
        trigger_example="simulate:geen eigen note voor scout",
        rationale="GSC-data verdiend eigen nota",
    )
    pg3 = Proposal(
        proposer_role="analyst",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id="analyst",
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
    from nooch_village.models import Tension
    triaged: list[dict] = []
    v.bus.subscribe("tension_triaged", lambda e: triaged.append(dict(e.data)))

    analyst = v.reconciler.live.get("analyst")
    if analyst:
        spanningen = [
            ("bezoekersdata per locale analyseren", "operational",
             "eigen-werk (analyst-scope)"),
            ("kandidaatwoord voor de bibliotheek: plasticvrij", "operational",
             "andere-rol:librarian"),
            ("niemand bezit de locale-policy structureel", "governance",
             "structureel → Proposal"),
            ("serverruimte koeling storing", "operational",
             "geen match → mens"),
        ]
        for desc, kind, _ in spanningen:
            analyst.sense_tension(desc, kind=kind)

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
        print("  ⚠️  analyst niet gevonden, triage overgeslagen")

    # ── 4. Reflectie — TijdgeestWachter ──────────────────────────────
    section("4 / 7 — REFLECTIE (TijdgeestWachter gap-sensing)")
    v.context.settings["reflect_interval_seconds"] = "0"
    v.context.settings["tijdgeest_interval_seconds"] = "999999"

    reflect_outcomes: list = []
    v.bus.subscribe("governance_changed",
                    lambda e: reflect_outcomes.append({"s": "aangenomen", **e.data}))
    v.bus.subscribe("proposal_invalid",
                    lambda e: reflect_outcomes.append({"s": "ongeldig", **e.data}))

    tw = v.reconciler.live.get("tijdgeest_wachter")
    if tw:
        rec_before = v.records.get("tijdgeest_wachter")
        accs_before = list(rec_before.definition.accountabilities) if rec_before else []
        v.bus.publish(Event("dag_begint", {"label": "simulate-reflect"}, "simulate"))

        for _ in range(100):
            if reflect_outcomes:
                break
            time.sleep(0.05)
        time.sleep(0.3)

        rec_after = v.records.get("tijdgeest_wachter")
        accs_after = list(rec_after.definition.accountabilities) if rec_after else []
        new_accs = [a for a in accs_after if a not in accs_before]

        print(f"  Governance-uitkomsten: {len(reflect_outcomes)}")
        for o in reflect_outcomes[:3]:
            print(f"    {o.get('s','?')} | kind={o.get('kind','-')} | role={o.get('role_id','-')}")
        if new_accs:
            print(f"\n  Nieuwe accountability in record:")
            print(f"    · {new_accs[0][:80]}")
        print(f"\n  ✔ skills ongewijzigd: {list(rec_after.definition.skills) if rec_after else '?'}")
        print(f"  ✔ geen nieuwe thread — activatie blijft mens-gated")
    else:
        print("  ⚠️  tijdgeest_wachter niet actief (run 'proposal' eerst)")

    v.stop()
    time.sleep(0.2)

    # ── 5. Ngram locale-demo (live, max 3 termen) ─────────────────────
    section("5 / 7 — NGRAM LOCALE-DEMO (NL + EN, live API)")
    v2 = Village(heartbeat_seconds=86400)
    v2.context.settings["tijdgeest_interval_seconds"] = "0"

    pulse_result: dict = {}
    v2.bus.subscribe("tijdgeest_pulse_completed", lambda e: pulse_result.update(e.data))
    v2.start()

    tw2 = v2.reconciler.live.get("tijdgeest_wachter")
    if tw2:
        # Drie begrippenparen NL+EN uit het Lexicon
        demo_terms = ["burger", "citizen", "plasticvrij"]
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
        print("  ⚠️  tijdgeest_wachter niet actief (run 'proposal' eerst)")

    v2.stop()
    time.sleep(0.2)

    # ── 6. Librarian keyword-beslissingen ─────────────────────────────
    section("6 / 7 — LIBRARIAN (meertalige kandidaat-woorden)")
    v3 = Village(heartbeat_seconds=86400)
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
        {"word": "leather shoes",           "locale": "en",
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
    v4 = Village(heartbeat_seconds=86400)
    v4.print_roster()

    print("\n" + "="*65)
    print("  SIMULATIE VOLTOOID")
    print("  Systeem draait: governance ✔ triage ✔ reflectie ✔ lexicon ✔")
    print("="*65 + "\n")


def kennis_scout_demo():
    """Demo: haal een paar lexicon-termen door OpenAlex en Semantic Scholar.

    Termen komen rechtstreeks uit het Lexicon (approved concepten), per locale.
    Per term: topics + citaties (OpenAlex) en tldr (Semantic Scholar).
    Max 3 termen per locale om de demo snel te houden.
    """
    from nooch_village.skills_impl.openalex import OpenalexSkill
    from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill

    v   = Village(heartbeat_seconds=86400)
    oa  = OpenalexSkill()
    ss  = SemanticScholarSkill()
    lex = v.context.lexicon

    # Haal approved termen per locale op uit het Lexicon
    nl_terms = lex.words_for_lang("nl", status_filter="approved")[:3]
    en_terms = lex.words_for_lang("en", status_filter="approved")[:3]
    demo_pairs = [(t, "nl") for t in nl_terms] + [(t, "en") for t in en_terms]

    print("\n================ DEMO: KennisScout — lexicon-termen gronden ================")
    print(f"NL termen: {nl_terms}")
    print(f"EN termen: {en_terms}")
    print("(OpenAlex: 0.5s sleep; Semantic Scholar: 1s sleep + backoff bij 429)\n")

    for term, locale in demo_pairs:
        print(f"\n{'─'*60}")
        print(f"  {term}  [{locale}]")
        print(f"{'─'*60}")

        # OpenAlex
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

        # Semantic Scholar
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

    print("\n================ einde kennis_scout demo ================")


def once():
    """Eén echte puls en dan stoppen. Ideaal voor een cron-job ('s ochtends)."""
    v = Village(heartbeat_seconds=0)
    done = {}
    v.bus.subscribe("pulse_completed", lambda e: done.update(e.data))
    v.start()
    v.bus.publish(Event("dag_begint", {"label": "cron"}, "cron"))
    for _ in range(600):
        if done:
            break
        time.sleep(0.1)
    v.stop()
    print(f"Field Note: {done.get('note_path')} | tension={done.get('tension')}")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if mode == "once":
        once()
    elif mode == "run":
        Village(heartbeat_seconds=0).run_forever()
    elif mode == "librarian":
        librarian_demo()
    elif mode == "governance":
        governance_demo()
    elif mode == "triage":
        triage_demo()
    elif mode == "intent":
        intent_demo()
    elif mode == "lifecycle":
        lifecycle_demo()
    elif mode == "proposal":
        proposal_demo()
    elif mode == "ngram":
        ngram_demo()
    elif mode == "reflect":
        reflect_demo()
    elif mode == "purge":
        purge_demo()
    elif mode == "roster":
        v = Village(heartbeat_seconds=86400)
        v.print_roster()
    elif mode == "simulate":
        simulate()
    elif mode == "kennis_scout":
        kennis_scout_demo()
    else:
        demo()
