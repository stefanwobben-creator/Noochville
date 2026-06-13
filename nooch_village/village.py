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
from nooch_village.roles import TimeKeeper, GrowthAnalyst, Librarian, PerformanceScout, Facilitator
from nooch_village.library import Library
from nooch_village.models import Proposal, GovernanceChange, ChangeKind
from nooch_village.governance import proposal_to_dict
from nooch_village.skills_impl.site_health import SiteHealthSkill
from nooch_village.skills_impl.budget import BudgetSkill
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.skills_impl.library_skills import LibraryLookupSkill, KeywordReviewSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CLASS_MAP = {"timekeeper": TimeKeeper, "analyst": GrowthAnalyst,
             "librarian": Librarian, "scout": PerformanceScout,
             "facilitator": Facilitator}


_ANCHOR_POLICIES = [
    "Geen enkele rol mag een accountability hebben die plastic-gebaseerd of "
    "dierlijk-leer materiaal als on-mission goedkeurt.",
    "De missie-toetsing (KeywordReview, G4-poort) mag nooit als accountability "
    "worden verwijderd zonder een gelijkwaardig alternatief in hetzelfde voorstel.",
]

_ANCHOR_PURPOSE = (
    "Nooch.earth bewijst dat ethisch en duurzaam ondernemen winstgevend is. "
    "Kernwaarden: geen plastic, geen leer, in Europa geproduceerd, op bestelling, "
    "eerlijke prijs, transparantie. Doel: organische groei richting 1000 klanten "
    "per jaar via missie-gedreven keywords."
)


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
    # Zorg dat anchor-policies aanwezig zijn
    if not root.definition.policies:
        root.definition.policies = list(_ANCHOR_POLICIES)
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
        self.registry = SkillRegistry()
        for skill in (SiteHealthSkill(), BudgetSkill(), PlausibleSkill(), TrendsSkill(),
                      FieldNoteSkill(), LibraryLookupSkill(), KeywordReviewSkill(),
                      GscPerformanceSkill()):
            self.registry.register(skill)
        self.records = Records(os.path.join(self.context.data_dir, "governance_records.json"))
        seed_records(self.records)
        migrate_records(self.records)
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
        self.bus.subscribe("proposal_invalid", self._observe)
        self.bus.subscribe("governance_rejected", self._observe)
        self.bus.subscribe("tension_triaged", self._observe)
        self.bus.subscribe("human_intervention_needed", self._observe)
        self.root = self.reconciler.build()

    def _observe(self, e: Event) -> None:
        with open(os.path.join(self.context.data_dir, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": e.name, **e.data}, ensure_ascii=False, default=str) + "\n")

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
    else:
        demo()
