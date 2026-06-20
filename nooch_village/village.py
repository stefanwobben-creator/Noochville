"""Composition root van NoochVillage.

Bouwt het marktplein (EventBus), registreert echte skills, en bouwt het
levende dorp uit de governance-records via de Reconciler.

Run:
    python -m nooch_village.village          # demo: groei-puls
    python -m nooch_village.village once     # één echte puls (cron)
    python -m nooch_village.village run      # blijft draaien
    python -m nooch_village.village <mode>   # zie cli.py voor alle modes
"""
from __future__ import annotations
import os, time, json, logging
from nooch_village.event_bus import EventBus, Event
from nooch_village.config import load_context
from nooch_village.skills import SkillRegistry
from nooch_village.matchmaker import Matchmaker
from nooch_village.governance import Records, Secretary, Reconciler, proposal_to_dict
from nooch_village.models import Proposal
from nooch_village.roles import (
    TimeKeeper, WebsiteWatcherWorker, Librarian, PerformanceScout,
    Facilitator, TijdgeestWachter, KennisScout, Noochie, Ronnie,
)
from nooch_village.library import Library
from nooch_village.lexicon import Lexicon
from nooch_village.observers.coherence_observer import CoherenceObserver
from nooch_village.skills_impl.site_health import SiteHealthSkill
from nooch_village.skills_impl.budget import BudgetSkill
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.field_note import FieldNoteSkill
from nooch_village.skills_impl.library_skills import LibraryLookupSkill, KeywordReviewSkill, LibraryListSkill
from nooch_village.skills_impl.gsc import GscPerformanceSkill
from nooch_village.skills_impl.gsc_report import GscReportSkill
from nooch_village.skills_impl.ngram import NgramCultureSkill
from nooch_village.skills_impl.openlibrary_search_inside import OpenlibrarySearchInsideSkill
from nooch_village.skills_impl.semantic_scholar import SemanticScholarSkill
from nooch_village.skills_impl.openalex import OpenalexSkill
from nooch_village.skills_impl.bulletin_schrijven import BulletinSchrijvenSkill
from nooch_village.skills_impl.keywords_everywhere import KeywordsEverywhereSkill
from nooch_village.human_inbox import HumanInbox
from nooch_village.gap_classifier import classify_gap
from nooch_village.observations import ObservationStore
from nooch_village.monitoring import MonitoringStore
from nooch_village.projects import ProjectLedger
from nooch_village.seeds import (
    seed_lexicon, seed_records, migrate_records,
    activate_tijdgeest_wachter, activate_kennis_scout, activate_ronnie,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CLASS_MAP = {
    "timekeeper":        TimeKeeper,
    "website_watcher":   WebsiteWatcherWorker,
    "librarian":         Librarian,
    "scout":            PerformanceScout,
    "facilitator":      Facilitator,
    "tijdgeest_wachter": TijdgeestWachter,
    "kennis_scout":     KennisScout,
    "noochie":          Noochie,
    "ronnie":           Ronnie,
}


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
        self.context.observations = ObservationStore(
            os.path.join(self.context.data_dir, "observations.jsonl"))
        self.context.monitoring = MonitoringStore(
            os.path.join(self.context.data_dir, "role_metrics.json"))
        self.context.projects = ProjectLedger(
            os.path.join(self.context.data_dir, "projects.json"))
        self.human_inbox = HumanInbox(os.path.join(self.context.data_dir, "human_inbox.json"))
        self.registry = SkillRegistry()
        for skill in (
            SiteHealthSkill(), BudgetSkill(), PlausibleSkill(), TrendsSkill(),
            FieldNoteSkill(), LibraryLookupSkill(), LibraryListSkill(), KeywordReviewSkill(),
            GscPerformanceSkill(), GscReportSkill(),
            NgramCultureSkill(),
            OpenlibrarySearchInsideSkill(),
            SemanticScholarSkill(),
            OpenalexSkill(),
            BulletinSchrijvenSkill(),
            KeywordsEverywhereSkill(),
        ):
            self.registry.register(skill)
        self.records = Records(os.path.join(self.context.data_dir, "governance_records.json"))
        seed_records(self.records)
        migrate_records(self.records)
        activate_tijdgeest_wachter(self.records)
        activate_kennis_scout(self.records)
        activate_ronnie(self.records)
        self.context.records = self.records
        self.matchmaker = Matchmaker(self.bus)
        self.secretary = Secretary(self.records, self.bus)
        self.reconciler = Reconciler(self.records, self.bus, self.registry, self.context,
                                     self.matchmaker, class_map=CLASS_MAP)
        self.bus.subscribe("task_completed",              self._observe)
        self.bus.subscribe("pulse_completed",             self._observe)
        self.bus.subscribe("tension_sensed",              self._observe)
        self.bus.subscribe("keyword_decided",             self._observe)
        self.bus.subscribe("human_decision_needed",       self._observe)
        self.bus.subscribe("human_decision_needed",       self._on_keyword_escalation)
        self.bus.subscribe("gsc_pulse_completed",         self._observe)
        self.bus.subscribe("governance_changed",          self._observe)
        self.bus.subscribe("governance_changed",          self._on_governance_changed)
        self.bus.subscribe("governance_review_requested", self._observe)
        self.bus.subscribe("governance_review_requested", self._on_escalation)
        self.bus.subscribe("proposal_invalid",            self._observe)
        self.bus.subscribe("governance_rejected",         self._observe)
        self.bus.subscribe("tension_triaged",             self._observe)
        self.bus.subscribe("human_intervention_needed",   self._observe)
        self.bus.subscribe("role_born",                   self._observe)
        self.bus.subscribe("role_born",                   self._on_role_born)
        self.bus.subscribe("tijdgeest_pulse_completed",   self._observe)
        self.bus.subscribe("tijdgeest_signaal",           self._observe)
        self.bus.subscribe("means_gap_sensed",            self._observe)
        self.bus.subscribe("means_gap_sensed",            self._on_means_gap)
        self.bus.subscribe("bulletin_geschreven",         self._observe)
        self.bus.subscribe("noochie_weighed_in",          self._observe)
        self.coherence_observer = CoherenceObserver(self.bus)
        self.root = self.reconciler.build()

    def _observe(self, e: Event) -> None:
        with open(os.path.join(self.context.data_dir, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": e.name, **e.data}, ensure_ascii=False, default=str) + "\n")

    def _on_escalation(self, e: Event) -> None:
        proposal_dict = e.data.get("proposal", {})
        gate   = e.data.get("gate", "?")
        reason = e.data.get("reason", "")
        iid = self.human_inbox.add_escalation(proposal_dict, gate, reason)
        logging.getLogger("village.inbox").info(
            "📬 escalatie in human_inbox: item %s (voorstel %s, poort %s)",
            iid, proposal_dict.get("id", "?"), gate)

    def _on_means_gap(self, e: Event) -> None:
        """Classificeer een gesensed gat en dispatch op uitkomst A / B / C.

        A  operationeel gedekt (mandaat + middelen aanwezig) — log, geen inbox-item.
        B  mandaat aanwezig, middelen ontbreken — means-gap in inbox (zoals voorheen).
        C  geen rol dekt het mandaat — placeholder-suggestie in inbox, geen geboorte.
        """
        gap_key     = e.data.get("gap_key", "?")
        description = e.data.get("description", "")
        log = logging.getLogger("village.inbox")

        outcome, role_id, reason = classify_gap(description, self.records.all())

        if outcome == "A":
            log.info("✅ gap A (operationeel gedekt door '%s'): %s — %s",
                     role_id, gap_key, reason)

        elif outcome == "B":
            iid = self.human_inbox.add_means_gap(gap_key, description, role_id=role_id)
            log.info("📌 gap B → means-gap in human_inbox: item %s (gap %s, rol '%s')",
                     iid, gap_key, role_id)

        elif outcome == "C":
            iid = self.human_inbox.add_suggestion(gap_key, description)
            log.info("💡 gap C → suggestie in human_inbox: item %s (gap %s) — %s",
                     iid, gap_key, reason)

    def _on_keyword_escalation(self, e: Event) -> None:
        """Schrijf keyword-escalaties naar de human inbox."""
        if e.data.get("topic") != "keyword":
            return
        word   = e.data.get("word", "?")
        reason = e.data.get("reason", "")
        demand = e.data.get("demand", {})
        iid = self.human_inbox.add_keyword_escalation(word, reason, demand)
        logging.getLogger("village.inbox").info(
            "📬 keyword-escalatie in human_inbox: item %s ('%s')", iid, word)

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
        dagboek = os.path.join(self.context.data_dir, "groeidagboek.jsonl")
        with open(dagboek, "a") as f:
            f.write(json.dumps({"ts": time.time(), **e.data}, ensure_ascii=False, default=str) + "\n")
        self.human_inbox.sync_unmanned(self.records.all(), CLASS_MAP)

    def _on_governance_changed(self, e: Event) -> None:
        self.human_inbox.sync_unmanned(self.records.all(), CLASS_MAP)

    def start(self):
        self.human_inbox.sync_unmanned(self.records.all(), CLASS_MAP)
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
        all_recs = [r for r in self.records.all() if not r.archived]
        all_recs.sort(key=lambda r: (r.source, r.id))
        print(f"\n{'ID':<26} {'Type':<8} {'Source':<8} {'Versie':<8} Purpose")
        print("-" * 95)
        for r in all_recs:
            tag = {"seed": "  ", "sensed": "✱ ", "demo": "⚙ "}.get(r.source, "? ")
            print(f"{tag}{r.id:<24} {r.type.value:<8} {r.source:<8} v{r.version:<7} "
                  f"{r.definition.purpose[:50]}")
        live_ids = set(self.reconciler.live.keys())
        unmanned = set(self.reconciler.unmanned.keys())
        demo_ids = {r.id for r in all_recs if r.source == "demo"}
        print(f"\n  Legende: ✱ = sensed (echt), ⚙ = demo, (blanco) = seed")
        print(f"  Live: {sorted(live_ids - demo_ids)}  |  Onbemand: {sorted(unmanned)}")
        if demo_ids:
            print(f"  Demo-rollen (worden genegeerd door G1/G2): {sorted(demo_ids)}")

    def submit_proposal(self, proposal: Proposal) -> str:
        """Human-ingang voor governance-voorstellen. Geeft het proposal_id terug."""
        self.bus.publish(Event("proposal_raised",
                               {"proposal": proposal_to_dict(proposal)}, "human"))
        return proposal.id

    def queue_project(self, owner: str, scope, trigger: str = "human") -> str:
        """Maak een project aan in het grootboek en notificeer de eigenaar via de bus."""
        pid = self.context.projects.create(owner, scope, trigger)
        self.bus.publish(Event("project_queued", {"project_id": pid, "owner": owner}, "village"))
        return pid


def once():
    """Eén echte puls en dan stoppen. Ideaal voor een cron-job ('s ochtends)."""
    v = Village(heartbeat_seconds=0)
    done = {}
    noochie = {}
    v.bus.subscribe("pulse_completed",    lambda e: done.update(e.data))
    v.bus.subscribe("noochie_weighed_in", lambda e: noochie.update(e.data))
    v.start()
    has_noochie = "noochie" in v.reconciler.live
    v.bus.publish(Event("dag_begint", {"label": "cron"}, "cron"))
    for _ in range(1800):
        pulse_klaar   = bool(done)
        noochie_klaar = bool(noochie) or not has_noochie
        if pulse_klaar and noochie_klaar:
            break
        time.sleep(0.1)
    v.stop()
    print(f"Field Note: {done.get('note_path')} | tension={done.get('tension')}")
    if noochie:
        print(f"\nNoochie: {noochie.get('oordeel', '-')}")


if __name__ == "__main__":
    from nooch_village.cli import main
    main()
