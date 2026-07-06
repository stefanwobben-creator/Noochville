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
import os, time, json, logging, shutil, tempfile
from nooch_village.event_bus import EventBus, Event
from nooch_village.config import load_context
from nooch_village.skills import SkillRegistry
from nooch_village.matchmaker import Matchmaker
from nooch_village.governance import Records, Secretary, Reconciler, proposal_to_dict
from nooch_village.models import Proposal, RecordType
from nooch_village.roles import (
    WebsiteWatcherWorker, Librarian, TrendsWorker,
    Facilitator, Noochie, HarryHemp, ContentStrategist, ConcurrentScout,
)
from nooch_village.library import Library
from nooch_village.lexicon import Lexicon
from nooch_village.observers.coherence_observer import CoherenceObserver
from nooch_village.skills_impl.site_health import SiteHealthSkill
from nooch_village.skills_impl.plausible import PlausibleSkill
from nooch_village.skills_impl.trends import TrendsSkill
from nooch_village.skills_impl.serpapi_trends import SerpapiTrendsSkill
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
from nooch_village.skills_impl.serpstat import SerpstatSkill
from nooch_village.skills_impl.stooq import StooqIndexSkill
from nooch_village.skills_impl.trends_categorie import TrendsCategorieSkill
from nooch_village.skills_impl.gdelt_tone import GdeltToneSkill
from nooch_village.skills_impl.competitor_news import CompetitorNewsSkill
from nooch_village.skills_impl.competitor_discover import CompetitorDiscoverSkill
from nooch_village.skills_impl.linkbuilding import LinkbuildingTargetsSkill
from nooch_village.skills_impl.verband_voorstel import VerbandVoorstelSkill
from nooch_village.skills_impl.onderzoeksvraag import OnderzoeksvraagSkill
from nooch_village.skills_impl.content_schrijven import ContentSchrijvenSkill
from nooch_village.skills_impl.content_check import ContentCheckSkill
from nooch_village.skills_impl.curate import CurateSkill
from nooch_village.skills_impl.voorstel import VoorstelSchrijvenSkill
from nooch_village.skills_impl.shopify_sales import ShopifySalesSkill
from nooch_village.human_inbox import HumanInbox
from nooch_village.gap_classifier import classify_gap
from nooch_village.observations import ObservationStore
from nooch_village.monitoring import MonitoringStore
from nooch_village.projects import ProjectLedger
from nooch_village.seeds import (
    seed_lexicon, seed_records, migrate_records,
)
from nooch_village.notes_store import NotesStore
from nooch_village.competitor_brands import CompetitorBrands

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CLASS_MAP = {
    "website_watcher": WebsiteWatcherWorker,
    "librarian":       Librarian,
    "trends":          TrendsWorker,
    # 'facilitator' is de historische seed-id van de governance-motor (G0-G4-poort + dagcadans/dag_begint);
    # de roltekst is bewust Engels (Holacracy-Facilitator), GEEN vreemd NL-duplicaat. Niet hernoemen/verplaatsen.
    "facilitator":     Facilitator,
    "noochie":         Noochie,
    "harry_hemp":      HarryHemp,
    "content_strategist": ContentStrategist,
    "concurrent_scout": ConcurrentScout,
}


class Village:
    def __init__(self, heartbeat_seconds: float | None = None,
                 data_dir: str | None = None):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-20s %(message)s",
                            datefmt="%H:%M:%S")
        self.bus = EventBus(name="root")
        self.context = load_context(BASE_DIR)
        # data_dir-override: settings/.env blijven uit de echte base laden, maar
        # alle SCHRIJF-stores (records, inbox, notes, library, ...) verhuizen naar
        # de opgegeven map. Zo kan simulate() in een wegwerp-map draaien zonder de
        # productie-records of human_inbox te vervuilen (escalatie-storm-bug).
        if data_dir is not None:
            self.context.data_dir = data_dir
            os.makedirs(data_dir, exist_ok=True)
        if heartbeat_seconds is not None:
            self.context.settings["heartbeat_seconds"] = str(heartbeat_seconds)
        self.context.library = Library(os.path.join(self.context.data_dir, "library.json"))
        self.context.lexicon = Lexicon(os.path.join(self.context.data_dir, "lexicon.json"))
        seed_lexicon(self.context.lexicon)
        self.context.notes = NotesStore(os.path.join(self.context.data_dir, "notes.json"))
        # Gedeelde concurrent-store: confirmed merken die de scout heeft laten bevestigen
        # zijn nu leesbaar voor élke rol (voor KE/SerpAPI-analyses).
        self.context.competitors = CompetitorBrands(
            os.path.join(self.context.data_dir, "competitor_brands.json"))
        self.context.observations = ObservationStore(
            os.path.join(self.context.data_dir, "observations.jsonl"))
        from nooch_village.source_status import SourceStatusStore
        from nooch_village.collector import migrate_data_sources
        self.context.sources = SourceStatusStore(
            os.path.join(self.context.data_dir, "sources.json"))
        migrate_data_sources(self.context.data_dir)   # legacy visitors_day + Plausible actief (idempotent)
        self.context.monitoring = MonitoringStore(
            os.path.join(self.context.data_dir, "role_metrics.json"))
        self.context.projects = ProjectLedger(
            os.path.join(self.context.data_dir, "projects.json"))
        from nooch_village.pinboard import Pinboard as _Pinboard
        self.context.pinboard = _Pinboard(
            os.path.join(self.context.data_dir, "pinboard.json"))
        self.human_inbox = HumanInbox(os.path.join(self.context.data_dir, "human_inbox.json"))
        self.registry = SkillRegistry()
        for skill in (
            SiteHealthSkill(), PlausibleSkill(), TrendsSkill(), SerpapiTrendsSkill(),
            FieldNoteSkill(), LibraryLookupSkill(), LibraryListSkill(), KeywordReviewSkill(),
            GscPerformanceSkill(), GscReportSkill(),
            NgramCultureSkill(),
            OpenlibrarySearchInsideSkill(),
            SemanticScholarSkill(),
            OpenalexSkill(),
            BulletinSchrijvenSkill(),
            KeywordsEverywhereSkill(),
            SerpstatSkill(),
            StooqIndexSkill(), TrendsCategorieSkill(), GdeltToneSkill(),   # externe observatie-bronnen (inactief tot activatie + config)
            CompetitorNewsSkill(),
            CompetitorDiscoverSkill(),
            LinkbuildingTargetsSkill(),
            VerbandVoorstelSkill(),
            OnderzoeksvraagSkill(),
            ContentSchrijvenSkill(),
            ContentCheckSkill(),
            CurateSkill(),
            VoorstelSchrijvenSkill(),
            ShopifySalesSkill(),
        ):
            self.registry.register(skill)
        self.records = Records(os.path.join(self.context.data_dir, "governance_records.json"))
        seed_records(self.records)
        migrate_records(self.records)
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
        self.bus.subscribe("human_decision_needed",       self._on_verband_suggestion)
        self.bus.subscribe("content_opportunity",         self._observe)
        self.bus.subscribe("content_opportunity",         self._on_content_opportunity)
        self.bus.subscribe("content_draft_ready",         self._observe)
        self.bus.subscribe("content_draft_ready",         self._on_content_draft_ready)
        self.bus.subscribe("gsc_pulse_completed",         self._observe)
        self.bus.subscribe("governance_changed",          self._observe)
        self.bus.subscribe("governance_changed",          self._on_governance_changed)
        self.bus.subscribe("governance_review_requested", self._observe)
        self.bus.subscribe("governance_review_requested", self._on_escalation)
        self.bus.subscribe("proposal_invalid",            self._observe)
        self.bus.subscribe("governance_rejected",         self._observe)
        self.bus.subscribe("tension_triaged",             self._observe)
        self.bus.subscribe("human_intervention_needed",   self._observe)
        self.bus.subscribe("source_died",                 self._observe)
        self.bus.subscribe("source_died",                 self._on_source_died)
        self.bus.subscribe("role_born",                   self._observe)
        self.bus.subscribe("role_born",                   self._on_role_born)
        self.bus.subscribe("tijdgeest_pulse_completed",   self._observe)
        self.bus.subscribe("tijdgeest_signaal",           self._observe)
        self.bus.subscribe("means_gap_sensed",            self._observe)
        self.bus.subscribe("means_gap_sensed",            self._on_means_gap)
        self.bus.subscribe("individuele_actie",           self._observe)
        self.bus.subscribe("individuele_actie",           self._on_individuele_actie)
        self.bus.subscribe("opportunity_sensed",          self._observe)
        self.bus.subscribe("opportunity_sensed",          self._on_opportunity)
        self.bus.subscribe("resolution_proposed",         self._on_resolution_proposed)
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

    def _on_opportunity(self, e: Event) -> None:
        """Een door een rol gesensde kans (project) wordt een beslissing in de inbox — niet
        autonoom werk. De mens keurt 'm goed (→ project) of negeert 'm. Mens-poort hersteld."""
        d = e.data
        title = (d.get("title") or "").strip()
        if not title:
            return
        self.human_inbox.add_opportunity(
            title, by=d.get("by", ""), kind=d.get("kind", "project"),
            wat=d.get("wat", ""), waarom=d.get("waarom", ""),
            business_case=d.get("business_case"))
        logging.getLogger("village.inbox").info(
            "💡 kans → inbox (wacht op akkoord): %s [%s]", title[:60], d.get("by", ""))

    def _on_source_died(self, e: Event) -> None:
        """Een databron ging van 'recente data' naar 'dood' (fresh→stale). Schrijf er GENERIEK een
        means-gap voor in de human_inbox (role_id=None, geen rol-toewijzing). Per-episode gap_key
        (met het laatste-meetdatum) zodat een herhaling ná opleving tóch een nieuw item wordt."""
        d = e.data
        source, field = d.get("source", "?"), d.get("field", "?")
        last_datum, days_ago, cadans = d.get("last_datum"), d.get("days_ago"), d.get("cadans", "onbekend")
        gap_key = f"deadsource:{source}:{field}@{last_datum}"
        wanneer = (f"laatste data {days_ago} dagen geleden ({last_datum})" if days_ago is not None
                   else (f"laatste data {last_datum}" if last_datum else "geen datum bekend"))
        description = (f"Bron '{source}/{field}' levert niet meer — {wanneer}, verwacht {cadans}. "
                       f"De indicator ging van recente data naar 'dood'.")
        iid = self.human_inbox.add_means_gap(gap_key, description, sensed_by=d.get("by", "website_watcher"))
        logging.getLogger("village.inbox").info(
            "💀 source_died → means-gap in human_inbox: item %s (%s)", iid, gap_key)

    def _on_means_gap(self, e: Event) -> None:
        """Classificeer een gesensed gat en dispatch op uitkomst A / B / C.

        A  operationeel gedekt (mandaat + middelen aanwezig) — log, geen inbox-item.
        B  mandaat aanwezig, middelen ontbreken — means-gap in inbox (zoals voorheen).
        C  geen rol dekt het mandaat — placeholder-suggestie in inbox, geen geboorte.
        """
        gap_key     = e.data.get("gap_key", "?")
        description = e.data.get("description", "")
        sensed_by   = e.data.get("by")
        log = logging.getLogger("village.inbox")

        outcome, role_id, reason = classify_gap(description, self.records.all())

        if outcome == "A":
            log.info("✅ gap A (operationeel gedekt door '%s'): %s — %s",
                     role_id, gap_key, reason)

        elif outcome == "B":
            iid = self.human_inbox.add_means_gap(gap_key, description, role_id=role_id,
                                                 sensed_by=sensed_by)
            log.info("📌 gap B → means-gap in human_inbox: item %s (gap %s, rol '%s')",
                     iid, gap_key, role_id)

        elif outcome == "C":
            iid = self.human_inbox.add_suggestion(gap_key, description)
            log.info("💡 gap C → suggestie in human_inbox: item %s (gap %s) — %s",
                     iid, gap_key, reason)

    def _on_individuele_actie(self, e: Event) -> None:
        """Een eenmalig gat buiten ieders scope (geen herhaling) → individuele actie.
        Holacracy: toegestaan als niet-schadelijk; hier escaleren we naar de mens als
        inspectie-item in de human inbox (geen rol-geboorte, geen auto-actie)."""
        gap_key     = e.data.get("gap_key", "?")
        description = e.data.get("description", "")
        by          = e.data.get("by", "?")
        iid = self.human_inbox.add_suggestion(
            gap_key, f"Individuele actie (eenmalig, buiten ieders scope, door {by}): {description}")
        logging.getLogger("village.inbox").info(
            "🙋 individuele actie → human_inbox: item %s (gap %s)", iid, gap_key)

    def _on_resolution_proposed(self, e: Event) -> None:
        """Een rol stelt voor een inbox-item te sluiten omdat hij de accountability nu dekt.
        We schrijven het voorstel op het item (status blijft pending); de mens bevestigt."""
        gap_key = e.data.get("gap_key")
        by      = e.data.get("from", "?")
        reason  = e.data.get("reason", "")
        if not gap_key:
            return
        item_id = self.human_inbox.find_by_gap(gap_key)
        if item_id and self.human_inbox.propose_resolution(item_id, by, reason):
            logging.getLogger("village.inbox").info(
                "📝 %s stelt voor item %s (gap %s) te sluiten: %s", by, item_id, gap_key, reason)

    def _on_verband_suggestion(self, e: Event) -> None:
        """Schrijf een verband-voorstel (topic 'verband') naar de human inbox (3c).

        De mens beslist later: approve schrijft het touwtje, reject laat het weg.
        Fail-closed: zonder beide kaart-ids gebeurt er niets.
        """
        if e.data.get("topic") != "verband":
            return
        a = e.data.get("kaart_a_id")
        b = e.data.get("kaart_b_id")
        if not a or not b:
            return
        iid = self.human_inbox.add_verband(
            a, b, e.data.get("voorstel_claim", ""), e.data.get("reason", ""))
        logging.getLogger("village.inbox").info(
            "📬 verband-voorstel in human_inbox: item %s (%s ↔ %s)", iid, a, b)

    def _on_content_opportunity(self, e: Event) -> None:
        """Schrijf een gespotte content-kans naar de human inbox (model C).
        Fail-closed: zonder seed_id gebeurt er niets."""
        seed_id = e.data.get("seed_id")
        if not seed_id:
            return
        iid = self.human_inbox.add_content_suggestion(
            seed_id, e.data.get("cluster_ids", []), e.data.get("reason", ""))
        logging.getLogger("village.inbox").info(
            "📬 content-kans in human_inbox: item %s (cluster '%s')", iid, seed_id)

    def _on_content_draft_ready(self, e: Event) -> None:
        """Schrijf een gegenereerde content-draft naar de human inbox, klaar om te
        herschrijven. Fail-closed: zonder seed_id of tekst gebeurt er niets."""
        seed_id = e.data.get("seed_id")
        text = e.data.get("text")
        if not seed_id or not text:
            return
        iid = self.human_inbox.add_content_draft(
            seed_id, e.data.get("kind", "blog"), text,
            e.data.get("claim_insight_ids", []))
        logging.getLogger("village.inbox").info(
            "📬 content-draft in human_inbox: item %s (cluster '%s')", iid, seed_id)

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
        # Herstel het voorstel in Secretary._pending zodat governance_verdict het kan vinden.
        # Secretary._pending is leeg na een herstart; de opgeslagen proposal-dict herstelt dit.
        stored = item["context"].get("proposal")
        if stored:
            from nooch_village.governance import proposal_from_dict
            self.secretary.store_pending(proposal_from_dict(stored))
        self.human_inbox.resolve(item_id, "approved", reason=reason)
        self.bus.publish(Event("governance_verdict",
                               {"proposal_id": pid, "decision": "approve", "reason": reason},
                               "the_source"))
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
        # Een gearchiveerde rol mag geen openstaande activatie-vraag achterlaten.
        self.human_inbox.withdraw_archived_activations(self.records.all())

    def start(self):
        self.human_inbox.sync_unmanned(self.records.all(), CLASS_MAP)
        self.human_inbox.withdraw_archived_activations(self.records.all())
        self._audit_role_provenance()
        self._write_role_status()
        self.root.start()

    def _write_role_status(self) -> None:
        """Schrijf de bemenst/onbemand-status (de laatste reconcile) weg zodat de read-only cockpit
        het kan tonen zonder zelf een dorp te draaien. 'bemenst' = code (CLASS_MAP) of actieve skill;
        'onbemand' = rol bestaat maar kan niet werken. Zie docs/ONTWERP_inwoners.md (de code-as)."""
        from nooch_village.util import atomic_write_json
        def _is_role(rid):
            r = self.records.get(rid)
            return r is not None and r.type == RecordType.ROLE
        manned = sorted(rid for rid in self.reconciler.live if _is_role(rid))
        unmanned = sorted(self.reconciler.unmanned.keys())
        atomic_write_json(os.path.join(self.context.data_dir, "role_status.json"),
                          {"manned": manned, "unmanned": unmanned, "generated_at": time.time()})

    def _audit_role_provenance(self) -> None:
        """Herkomst-wachter: waarschuw luid bij een seed-gehardcodeerde niet-bootstrap rol.
        Zo'n rol hoort via governance geboren te zijn (source=sensed), niet geseed."""
        from nooch_village.seeds import role_provenance_violations
        for rid in role_provenance_violations(self.records):
            logging.getLogger("village.governance").warning(
                "⚠️ herkomst: rol '%s' is seed-gehardcodeerd (geen governance-geboorte). "
                "Draai 'python -m nooch_village.village formalize' of dien een add_role-voorstel in.",
                rid)

    def stop(self):
        self.root.stop()

    def report_keys(self) -> str:
        """Niet-blokkerend opstart-rapport: welke LLM-treden + skills hebben hun sleutel."""
        from nooch_village.key_audit import audit_keys, format_key_report
        return format_key_report(audit_keys(self.registry, self.context))

    def run_forever(self):
        print(self.report_keys())
        self.bus.subscribe("pulse_completed", lambda e: logging.getLogger("village").info(
            "✅ dagpuls verwerkt — het dorp leeft en wacht nu op de volgende dag-puls. "
            "Geen nieuwe regels = normaal, niet vastgelopen. Ctrl+C om te stoppen."))
        self.start()
        print("🌙 Het dorp draait (daemon). Zodra het log stilvalt is dat normaal: het wacht "
              "op de volgende dag-puls. Ctrl+C om te stoppen.\n")
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
        human_held = {r.id: r.held_by for r in all_recs if r.held_by}
        if human_held:
            zetels = ", ".join(f"{rid} ← {who}" for rid, who in sorted(human_held.items()))
            print(f"  Door mens bezet: {zetels}")
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


def _run_single_pulse(v: "Village") -> None:
    """Draai één puls op een al-geconstrueerde Village: print de sleutels, abonneer op de
    afronding, trap 'dag_begint' af, wacht tot de puls (en Noochie) klaar zijn, print de uitkomst.
    Gedeeld door once() (tegen data/) en once_sandbox() (tegen een wegwerp-kopie). Puur extractie."""
    print(v.report_keys())
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


def once():
    """Eén echte puls en dan stoppen. Ideaal voor een cron-job ('s ochtends)."""
    v = Village(heartbeat_seconds=0)
    _run_single_pulse(v)


def once_sandbox(keep: bool = False, src: str | None = None) -> str:
    """Draai één puls tegen een wegwerp-KOPIE van data/, zodat de productie-data nooit
    geschreven wordt. Volgt het simulate()-patroon (Village met data_dir-override), maar
    kopieert de echte data/ i.p.v. een lege map. Geeft het sandbox-pad terug.

    keep=True laat de kopie staan zodat je de output kunt inzien; standaard wordt hij in een
    finally opgeruimd. `src` is injecteerbaar voor tests; standaard de echte data/-map."""
    src = src or os.path.join(BASE_DIR, "data")
    tmp = tempfile.mkdtemp(prefix="noochville-pulse-")
    shutil.copytree(src, tmp, dirs_exist_ok=True)
    print(f"[sandbox] puls draait tegen kopie van data/: {tmp}")
    try:
        v = Village(heartbeat_seconds=0, data_dir=tmp)
        _run_single_pulse(v)
    finally:
        if keep:
            print(f"[sandbox] kopie behouden (--keep): {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            print("[sandbox] kopie opgeruimd.")
    return tmp


if __name__ == "__main__":
    from nooch_village.cli import main
    main()
