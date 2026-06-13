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
from nooch_village.roles import TimeKeeper, GrowthAnalyst, Librarian, PerformanceScout
from nooch_village.library import Library
from nooch_village.skills_impl.site_health import SiteHealthSkill
from nooch_village.skills_impl.budget import BudgetSkill
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.skills_impl.library_skills import LibraryLookupSkill, KeywordReviewSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CLASS_MAP = {"timekeeper": TimeKeeper, "analyst": GrowthAnalyst,
             "librarian": Librarian, "scout": PerformanceScout}


def seed_records(records: Records) -> None:
    if records.root() is not None:
        return
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(purpose="Het dorp Nooch.earth", skills=[]),
                  members=["timekeeper", "analyst", "librarian", "scout"])
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
    for r in (root, timekeeper, analyst, librarian, scout):
        records.put(r)


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
    else:
        demo()
