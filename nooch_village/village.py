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
from nooch_village.governance import (Records, Secretary, Reconciler,
                                      GovernanceGate, proposal_to_dict)
from nooch_village.models import Proposal, RecordType
from nooch_village.roles import Facilitator, Noochie
from nooch_village.library import Library
from nooch_village.lexicon import Lexicon
from nooch_village.observers.coherence_observer import CoherenceObserver
from nooch_village.registry_factory import build_skill_registry
from nooch_village.human_inbox import HumanInbox
from nooch_village.gap_classifier import classify_gap
from nooch_village.observations import ObservationStore
from nooch_village.monitoring import MonitoringStore
from nooch_village.projects import ProjectLedger
from nooch_village.seeds import (
    seed_lexicon, seed_records, migrate_records,
)
from nooch_village.competitor_brands import CompetitorBrands

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# De zes AI-rolklassen (WebsiteWatcherWorker, Librarian, TrendsWorker, HarryHemp,
# ContentStrategist, ConcurrentScout) zijn op 19 sept 2026 verwijderd: hun rollen waren tussen
# 15 en 18 september al op governance-niveau gearchiveerd, en daarmee was 1.903 van de 2.404 regels
# in roles.py code voor inwoners die niet meer bestaan.
CLASS_MAP = {
    # 'facilitator' is de historische seed-id van de governance-motor (G0-G4-poort + dagcadans/dag_begint);
    # de roltekst is bewust Engels (Holacracy-Facilitator), GEEN vreemd NL-duplicaat. Niet hernoemen/verplaatsen.
    "facilitator":     Facilitator,
    "noochie":         Noochie,
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
        # Koppelingen van middelen aan accountabilities. Alleen uitvoeringswaarheid als
        # skill_links_active=1; anders puur weergave (zie skill_links.py).
        from nooch_village.ai_tasks import AITaskStore
        self.context.links = AITaskStore(os.path.join(self.context.data_dir, "ai_tasks.json"))
        self.context.lexicon = Lexicon(os.path.join(self.context.data_dir, "lexicon.json"))
        seed_lexicon(self.context.lexicon)
        # Community-listening (Billy Buzz) hing hier: zoek-sets + observatie-store voor Reddit,
        # YouTube en Bluesky. Weg op 19 september 2026 (fase 4). De 5,4 MB aan observaties in
        # data/buzz_observations.jsonl blijft staan als historie; er komt niets meer bij.
        # Gedeelde concurrent-store: confirmed merken die de scout heeft laten bevestigen
        # zijn nu leesbaar voor élke rol (voor KE/SerpAPI-analyses).
        self.context.competitors = CompetitorBrands(
            os.path.join(self.context.data_dir, "competitor_brands.json"))
        self.context.observations = ObservationStore(
            os.path.join(self.context.data_dir, "observations.jsonl"))
        from nooch_village import llm_usage          # CO2-KPI: LLM-usage-log naar de juiste data_dir
        llm_usage.set_path(os.path.join(self.context.data_dir, "llm_usage.jsonl"))
        from nooch_village.source_status import SourceStatusStore
        from nooch_village.collector import migrate_data_sources
        self.context.sources = SourceStatusStore(
            os.path.join(self.context.data_dir, "sources.json"))
        migrate_data_sources(self.context.data_dir)   # legacy visitors_day + Plausible actief (idempotent)
        self.context.monitoring = MonitoringStore(
            os.path.join(self.context.data_dir, "role_metrics.json"))
        self.context.projects = ProjectLedger(
            os.path.join(self.context.data_dir, "projects.json"))
        from nooch_village.deliverable_store import DeliverableStore
        self.context.deliverables = DeliverableStore(       # skill-resultaten overleven het project
            os.path.join(self.context.data_dir, "deliverables.json"))
        # Eenmalig (idempotent): bestaande duplicaat-stapels markeren. Elke retry legde er een naast
        # in plaats van te vervangen; zonder deze migratie houdt elk project dat nooit meer
        # herdraait zijn stapel, en blijft het bewijsvenster van de critic gevuld met duplicaten.
        try:
            self.context.deliverables.migrate_vervangen()
        except Exception as e:                              # noqa: BLE001
            logging.getLogger("village.deliverables").warning(
                "deliverable-ontdubbeling overgeslagen: %s", e)
        # Gedeelde set (daemon-intern): pids die _claim_run_complete AL inline als route="autonoom"
        # aankondigde. De board-watch skipt die zodat een autonome afronding niet dubbel vuurt.
        self.context._autonomous_done = set()
        from nooch_village.project_doc_store import ProjectDocStore
        self.context.project_docs = ProjectDocStore(self.context.data_dir)   # levend einddocument per project
        from nooch_village.personas import PersonaStore
        # De inwoners in de rugzak: `llm_keuze` leest hier de modelvoorkeur van de persona die op een
        # rol zit (`context.personas`). Zonder deze regel is dat attribuut None en valt ELK daemon-pad
        # stil terug op de dorpsladder — de puls-einddocumenten en de Field Note draaiden daardoor op
        # de goedkoopste trede terwijl de persona iets anders vroeg. De cockpit had de bedrading al.
        self.context.personas = PersonaStore(
            os.path.join(self.context.data_dir, "personas.json"))
        # Prijs-sweep bij het opstarten: een trede zonder prijs telt voor EUR 0,00 en maakt de
        # maandcap blind. Dat hoor je te weten bij het opstarten, niet pas als er toevallig een
        # premium-call langskomt — zo bleef `openrouter:openai/gpt-5.6-luna` in de dorpsstaart
        # maandenlang onzichtbaar. Fail-soft: een sweep mag het dorp nooit tegenhouden.
        try:
            from nooch_village import llm_keuze as _lk
            _lk.meld_prijsloze_bronnen(self.context.personas.all())
        except Exception as e:                       # noqa: BLE001
            logging.getLogger("village.prijzen").warning("prijs-sweep overgeslagen: %s", e)
        # Board-watch: de cockpit draait in een LOS proces met een eigen in-memory bus; een bord-drag
        # naar ACTIEF schrijft alleen projects.json. Deze village-poll herleest dat bestand en vertaalt
        # een verse naar-'running'-overgang naar een in-memory project_activated-event, zodat de
        # eigenaar-rol het binnen seconden oppakt i.p.v. pas bij de volgende dag-puls. `_activated_seen`
        # dedupliceert (één event per overgang); `board_poll_seconds` stuurt de cadans (default 2s).
        self._activated_seen: set[str] = set()
        self._board_poll_seconds: float = float(
            self.context.settings.get("board_poll_seconds", "2"))
        from nooch_village.attachments import AttachmentStore as _AttachmentStore
        self.context.att = _AttachmentStore(          # policies/notes/tools — o.a. de WIP-cirkelpolicy
            os.path.join(self.context.data_dir, "attachments.json"))
        from nooch_village.pinboard import Pinboard as _Pinboard
        self.context.pinboard = _Pinboard(
            os.path.join(self.context.data_dir, "pinboard.json"))
        self.human_inbox = HumanInbox(os.path.join(self.context.data_dir, "human_inbox.json"))
        self.registry = build_skill_registry()                            # gedeelde factory (ook cockpit-match)
        self.records = Records(os.path.join(self.context.data_dir, "governance_records.json"))
        # Domein-sweep, zelfde gedachte als de prijs-sweep: een bewaakt domein zonder houder zet
        # stilzwijgend skills uit. De Librarian hield `library` waar de code `bibliotheek` bedoelt,
        # en `keyword_review` weigerde daardoor vijftien dagen elke aanroep zonder dat iets zich
        # meldde. Een pytest-guard ziet alleen seeds.py; dit ziet de LEVENDE records.
        try:
            from nooch_village import skill_meta as _sm
            for _gat in _sm.domein_gaten(self.records.all()):
                logging.getLogger("village.domeinen").warning("DOMEIN_GAT: %s", _gat)
        except Exception as _e:                      # noqa: BLE001
            logging.getLogger("village.domeinen").warning("domein-sweep overgeslagen: %s", _e)
        seed_records(self.records)
        migrate_records(self.records)
        self.context.records = self.records
        # DE HARTSLAG STAAT NAAST DE ROLLEN, niet erin. Hij zat in `Facilitator`, en toen die rol
        # slapend werd gelegd stond het dorp drie dagen stil. Een klok is geen deelnemer: het dorp
        # mag over zijn structuur besluiten, niet over zijn cadans. Zie `dagcyclus.py`.
        from nooch_village.dagcyclus import Dagcyclus
        self.dagcyclus = Dagcyclus(self.bus, self.context)
        # De geldigheidspoort hoort bij de motor, niet bij een rol: zie GovernanceGate. Vóór de
        # Secretary, zodat de volgorde op de bus leest zoals de governance-stroom loopt
        # (poort -> adoptie) en niet andersom.
        self.governance_gate = GovernanceGate(self.records, self.bus, self.context)
        self.secretary = Secretary(self.records, self.bus, links=self.context.links)
        self.reconciler = Reconciler(self.records, self.bus, self.registry, self.context,
                                     class_map=CLASS_MAP)
        self.bus.subscribe("pulse_completed",             self._observe)
        self.bus.subscribe("tension_sensed",              self._observe)
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
        self.bus.subscribe("means_gap_sensed",            self._observe)
        self.bus.subscribe("means_gap_sensed",            self._on_means_gap)
        self.bus.subscribe("individuele_actie",           self._observe)
        self.bus.subscribe("individuele_actie",           self._on_individuele_actie)
        self.bus.subscribe("opportunity_sensed",          self._observe)
        self.bus.subscribe("opportunity_sensed",          self._on_opportunity)
        self.bus.subscribe("resolution_proposed",         self._on_resolution_proposed)
        self.bus.subscribe("bulletin_geschreven",         self._observe)
        self.bus.subscribe("noochie_weighed_in",          self._observe)
        self.bus.subscribe("kennis_geraadpleegd",         self._observe)   # kennis-eerst zichtbaar in system_log
        self.bus.subscribe("board_pulse_completed",       self._observe)
        # Twee autonome rondes aan de BESTAANDE dagcadans (dag_begint) — geen tweede timer erbij, en
        # dus geen tweede plek waar het ritme kan verlopen. Infra-subscribe (zoals Matchmaker en
        # Reconciler): beide handlers zijn deterministisch, doen geen netwerk-I/O en publiceren niet
        # terug de keten in. Eerst het ritme, dan de voorstellen; de volgorde is voor de veiligheid
        # niet kritisch (een vers voorstel heeft status 'proposed' en valt sowieso buiten de puls).
        #   1. de bord-puls: activaties worden binnen seconden door `_poll_board` opgepakt als
        #      project_activated, zodat de eigenaar-rol in dezelfde puls aan het werk gaat;
        #   2. de voorstel-ronde: zet niets op het bord, elk voorstel wacht op de mens (cap + dedup
        #      remmen de ruis).
        self.bus.subscribe("dag_begint",                  self._on_board_pulse)
        # Generieke databron-collector + dode-bron-sensor (16 sept 2026): verplaatst uit
        # website_watcher, want dit was dorpsbrede infrastructuur op een rol-thread — zelfde
        # koppelfout als de dagbel-op-facilitator van 28 augustus. Zie Village._veilig_databron_puls.
        self.bus.subscribe("dag_begint",                  lambda e: self._veilig_databron_puls())
        self.coherence_observer = CoherenceObserver(self.bus)
        self.root = self.reconciler.build()

    def _observe(self, e: Event) -> None:
        with open(os.path.join(self.context.data_dir, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": e.name, **e.data}, ensure_ascii=False, default=str) + "\n")

    def _on_board_pulse(self, e: Event) -> None:
        """De autonome pull-scheduler, één keer per dagcadans. Fail-soft: een fout hier mag de
        dagpuls (Field Note, rolwerk) nooit omvertrekken — daarom vangen we breed en loggen we."""
        try:
            from nooch_village.board_loop import run_board_pulse
            run_board_pulse(self.context, records=self.records, bus=self.bus,
                            unmanned=set(self.reconciler.unmanned))
        except Exception as exc:      # noqa: BLE001 — de cadans is belangrijker dan deze puls
            logging.getLogger("village.board").warning("bord-puls overgeslagen: %s", exc)

    # HIER STOND `_on_propose_projects`: de voorstel-generator, één ronde per dagcadans. Weg op
    # 21 september 2026, en de reden is niet dat hij stuk was maar dat hij in het NIETS produceerde.
    # De enige plek waar een mens een voorstel kon aannemen of afwijzen was de Founder Flow, en dat
    # scherm is in fase 1-9 verwijderd. De generator bleef intussen elke dag draaien: op productie
    # stonden 10 voorstellen te wachten, de oudste 43 dagen, die niemand kón beoordelen.
    #
    # Dat is dezelfde vorm als de triage-keten van 20 september: een lus die werk maakt zonder
    # uitgang naar een mens. Stefans besluit: de hele lus weg, geen nieuw scherm erbij.

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

    def _collect_daily_observations(self) -> None:
        """Generieke dag-observatie-collector: elke ACTIEVE DataSourceSkill schrijft z'n gedeclareerde
        velden weg onder `<source>_<field>_day`. Niets per bron/veld hardcoded; fail-closed.

        Verplaatst uit WebsiteWatcherWorker (16 sept 2026). Dit was generieke dorpsinfrastructuur op
        een rol-thread: sliep of archiveerde `website_watcher`, dan stopte de dagelijkse verzameling
        van ELKE databron (GDELT, GSC, Plausible-afgeleiden, Shopify, ...), niet alleen zijn eigen
        werk. Exact de dagcyclus-les van 28 augustus (de dagbel hing toen aan `facilitator`), nu
        toegepast op databron-collectie. Reageert rechtstreeks op `dag_begint`, rolonafhankelijk."""
        from nooch_village.collector import collect_daily_observations
        obs = getattr(self.context, "observations", None)
        sources = getattr(self.context, "sources", None)
        if obs is None or sources is None or self.registry is None:
            return
        log = logging.getLogger("village")
        try:
            written = collect_daily_observations(self.registry, sources, obs, self.context)
            if written:
                log.info("dag-observaties geschreven: %s", written)
            # Contract-healthcheck (meetcatalogus): ongecatalogiseerde reeks of niet-vullende ACTIEVE
            # family → luid signaal. Bewust-inactieve bronnen zwijgen. Nooit blokkerend voor de puls.
            try:
                from nooch_village.meetcatalog import healthcheck
                for sig in healthcheck(obs):
                    log.warning("🩺 meetcatalogus-signaal: %s", sig)
            except Exception as exc:
                log.warning("meetcatalogus-healthcheck faalde: %s", exc)
        except Exception as exc:
            log.warning("dag-observatie-collector faalde: %s", exc)

    def _sense_dead_sources(self) -> None:
        """Senst op de OVERGANG van 'recente data' naar 'dood' (fresh→stale uit indicator_freshness):
        publiceert per overgang een `source_died`-event; `_on_source_died` hierboven schrijft er
        generiek een means-gap voor in de human_inbox. Dedup + kind-aware drempel zitten in de sensor.
        Fail-closed.

        Verplaatst uit WebsiteWatcherWorker (16 sept 2026) — zelfde reden als hierboven: de sensor
        die moet waarschuwen als een bron doodgaat, mag zelf niet doodgaan zodra de rol die hem droeg
        slaapt. Reageert rechtstreeks op `dag_begint`, rolonafhankelijk."""
        import os
        from nooch_village.deadsource import DeadSourceState, sense_dead_sources
        if getattr(self.context, "observations", None) is None or self.registry is None:
            return
        log = logging.getLogger("village")
        state = DeadSourceState(os.path.join(self.context.data_dir, "deadsource_state.json"))

        def emit(source, field, last_datum, days_ago, cadans):
            self.bus.publish(Event("source_died", {
                "source": source, "field": field, "last_datum": last_datum,
                "days_ago": days_ago, "cadans": cadans, "by": "dorp"}, "dorp"))
        try:
            died = sense_dead_sources(self.registry, self.context, state, emit)
            if died:
                log.info("dode-bron-overgangen gesensed: %s", died)
        except Exception as exc:
            log.warning("dode-bron-sensor faalde: %s", exc)

    def _veilig_databron_puls(self) -> None:
        """Combineert de databron-collector en de dode-bron-sensor in de vaste volgorde die
        `WebsiteWatcherWorker._morning_pulse` ook aanhield: eerst verzamelen, dan senst de
        dode-bron-detectie tegen de zojuist bijgewerkte reeksen. Beide stappen zijn zelf al
        fail-closed; deze wrapper is de buitenste laag, zoals `_veilig_verweesd` hieronder."""
        try:
            self._collect_daily_observations()
        except Exception as e:                               # noqa: BLE001
            logging.getLogger("village").warning("databron-puls faalde (collector): %s", e)
        try:
            self._sense_dead_sources()
        except Exception as e:                               # noqa: BLE001
            logging.getLogger("village").warning("databron-puls faalde (dode-bron-sensor): %s", e)

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
        # Rollen die op een runner-poort staan (seed-grant zonder green-light) krijgen hun vraag.
        self.human_inbox.sync_runner_gates(self.records.all())
        # Een gearchiveerde rol mag geen openstaande activatie-vraag achterlaten.
        self.human_inbox.withdraw_archived_activations(self.records.all())

    def start(self):
        self.human_inbox.sync_unmanned(self.records.all(), CLASS_MAP)
        # De seed (in __init__) kan zojuist een activatie-poort hebben gezet; die hoort meteen als
        # vraag in de inbox te staan, niet pas na de eerstvolgende governance-wijziging.
        self.human_inbox.sync_runner_gates(self.records.all())
        self.human_inbox.withdraw_archived_activations(self.records.all())
        self._migrate_persona_bindings()
        self._audit_role_provenance()
        self._write_role_status()
        self._prime_board_watch()          # bestaande 'running'-projecten niet als nieuwe activatie vuren
        self.root.start()
        # NA de rollen: eerst luisteraars, dan pas bellen. Andersom valt de eerste ring in een leeg
        # dorp — en die ring komt pas de volgende kalenderdag terug.
        self.dagcyclus.start()

    def _migrate_persona_bindings(self) -> None:
        """Legacy `record.persona_id` → de assignments-store: één bron van waarheid voor bemensing.

        Idempotent, dus gratis zodra hij een keer geland is. Zonder deze migratie las een rol die
        alléén in de legacy-laag zat (compliance) als onbemand, en kopieerde elk bericht naar de
        Circle Lead. Fail-soft: een mislukte migratie mag het dorp niet tegenhouden."""
        try:
            from nooch_village.assignments import Assignments, migrate_persona_bindings
            pad = os.path.join(self.context.data_dir, "assignments.json")
            n = migrate_persona_bindings(self.records, Assignments(pad))
            if n:
                logging.getLogger("village").info(
                    "🔗 %d legacy persona-binding(en) naar de assignments-store gemigreerd", n)
        except Exception as e:                           # noqa: BLE001
            logging.getLogger("village").warning("persona-migratie overgeslagen: %s", e)

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
        self.dagcyclus.stop()
        self.root.stop()

    def report_keys(self) -> str:
        """Niet-blokkerend opstart-rapport: welke LLM-treden + skills hebben hun sleutel."""
        from nooch_village.key_audit import audit_keys, format_key_report
        return format_key_report(audit_keys(self.registry, self.context))

    def _meld_verweesde_pulse_skills(self) -> list[str]:
        """Een pulse-skill die aan GEEN ENKELE levende rol is toegekend, draait nooit.

        Dit is de derde puls-toestand, en de enige die werk voor een mens is. De andere twee
        (overgeslagen door ritme, gedraaid en niets gevonden) zijn rust en blijven log-only.

        WAAROM DIT OP DORPSNIVEAU STAAT en niet in de rol-lus: "ik heb deze skill niet" is voor
        vrijwel elke rol de normale toestand — de Copywriter hoort geen claims-scan te draaien.
        Per rol melden zou 31 rollen × 2 skills = 62 meldingen per puls opleveren voor iets wat
        niemand hoeft op te lossen. Een rol kan bovendien niet weten of een ANDER hem heeft; alleen
        het dorp weet dat. Eén keer per puls, gededupliceerd door de HumanInbox op `gap_key`.

        Geeft de verweesde skill-namen terug (leeg = alles is belegd)."""
        rauw = self.context.settings.get("pulse_skills", "claims_site_scan")
        skills = [x.strip() for x in str(rauw).split(",") if x.strip()]
        belegd: set[str] = set()
        for rec in self.records.all():
            if getattr(rec, "slaapt", False) or getattr(rec, "archived", False):
                continue                                   # een slapende rol draagt geen capaciteit
            belegd.update((getattr(rec, "definition", None) and rec.definition.skills) or [])
        wees = [s for s in skills if s not in belegd]
        log = logging.getLogger("village")
        if not wees:
            log.info("⏱ pulse-skills belegd: %s — elke skill heeft minstens één rol",
                     ", ".join(skills) or "(geen)")
            return []
        for naam in wees:
            log.warning("⏱ pulse-skill '%s' is aan GEEN ENKELE levende rol toegekend — "
                        "hij loopt mee op de puls maar draait nooit", naam)
            try:                                           # fail-soft: melden mag de puls niet breken
                self.human_inbox.add_means_gap(
                    f"pulse_skill:{naam}",
                    f"Periodieke skill '{naam}' loopt mee op de dagpuls maar is aan geen enkele "
                    f"levende rol toegekend — hij draait dus nooit.",
                    sensed_by="dorp")
            except Exception:                              # noqa: BLE001
                log.warning("⏱ verweesde pulse-skill '%s' niet gemeld", naam)
        return wees

    def _veilig_verweesd(self) -> None:
        try:
            self._meld_verweesde_pulse_skills()
        except Exception as e:                             # noqa: BLE001
            logging.getLogger("village").warning("verweesde-pulse-skill-check faalde: %s", e)

    def _meld_weesprojecten(self) -> list[str]:
        """Een niet-afgerond project waarvan de eigenaar-rol gearchiveerd of slapend is, heeft geen
        levende bezetter meer over — er gebeurt nooit meer iets mee, tenzij een mens het opmerkt.
        Precies het patroon van de compliance-rol-migratie (10 september) en van harry_hemp erna:
        een rol wordt afgeslankt, maar het werk dat erop stond verhuist niet vanzelf mee.

        Zelfde vorm als `_meld_verweesde_pulse_skills` hierboven, en om dezelfde reden: één melding
        per ROL, niet per project — een gearchiveerde rol met 90 openstaande projecten mag niet 90
        losse inbox-items opleveren voor iets waar de oplossing voor allemaal hetzelfde is
        (herverdelen naar een levende rol, of bewust laten liggen). `gap_key` per rol dedupliceert
        dat via de HumanInbox, ongeacht status — zelfde afweging die daar al voor pulse-skills geldt.

        AFGEROND IS NIET DE ENIGE MANIER WAAROP WERK EINDIGT. Er is geen `cancelled`-status; een
        project dat stopt zonder af te zijn wordt gearchiveerd, en dat is de gangbare weg — bij
        concurrent_scout waren 15 van de 16 openstaande projecten zo beëindigd. Alleen op `status`
        kijken maakte van die 15 alsnog wezen op het moment dat de rol werd opgeruimd: een melding
        over werk dat een mens al had afgesloten. `afslank_wezen.wezen` slaat gearchiveerd werk om
        dezelfde reden over; dit is diezelfde regel, niet een tweede definitie van "open project".

        Geeft de rol-ids terug die weesprojecten hebben (leeg = niemand)."""
        from nooch_village.projects import KLAAR
        dood: dict[str, list[str]] = {}
        for p in self.context.projects.all():
            if p.get("status") in KLAAR or p.get("archived"):
                continue                                    # afgerond of afgesloten: geen eigenaar nodig
            owner = p.get("owner", "")
            rec = self.records.get(owner) if owner else None
            if rec is not None and (getattr(rec, "archived", False) or getattr(rec, "slaapt", False)):
                dood.setdefault(owner, []).append(p.get("title") or p.get("id", ""))
        log = logging.getLogger("village")
        for rol_id, titels in dood.items():
            log.warning("👻 rol '%s' is gearchiveerd/slapend maar bezit nog %d "
                        "openstaand project(en)", rol_id, len(titels))
            try:                                             # fail-soft: melden mag de puls niet breken
                voorbeeld = "; ".join(titels[:3])
                if len(titels) > 3:
                    voorbeeld += f" (+{len(titels) - 3} meer)"
                self.human_inbox.add_means_gap(
                    f"weesprojecten:{rol_id}",
                    f"Rol '{rol_id}' is gearchiveerd of slapend maar bezit nog {len(titels)} "
                    f"niet-afgerond project(en), dus daar gebeurt niets meer mee: {voorbeeld}. "
                    f"Herverdeel de accountability naar een levende rol, of laat bewust liggen.",
                    role_id=rol_id, sensed_by="dorp")
            except Exception:                                # noqa: BLE001
                log.warning("👻 weesprojecten van '%s' niet gemeld", rol_id)
        return list(dood.keys())

    def _radar_ingest(self) -> dict:
        """De Inoreader-feeds ophalen en ongefilterd in de swipefile zetten.

        DIT DRAAIDE TOT 19 SEPTEMBER 2026 ALS LOSSE CRON (`30 6 * * *` onder gebruiker `nooch`),
        buiten het dorp om. Dat is dezelfde koppelfout als de dagbel-op-de-facilitator van 28
        augustus, maar dan andersom: een taak van het dorp die alleen in de serverconfig bestond,
        onzichtbaar in de repo en niet meetbaar in de puls. Nu hangt hij aan `dag_begint`, net als
        de databron-collector en de twee wees-sweeps.

        BIJ HET DEPLOYEN MOET DIE CRONTAB-REGEL WEG, anders draait de ingest tweemaal per dag. De
        ontdubbeling op artikel-URL vangt dubbele signalen op, dus het is niet gevaarlijk — het is
        twee keer de Inoreader-API en een log met twee bronnen."""
        from nooch_village.inoreader_ingest import ingest_all
        return ingest_all(self.context.data_dir)

    def _veilig_radar_ingest(self) -> None:
        try:
            uit = self._radar_ingest()
            n = sum((v or {}).get("proposed", 0) for v in uit.values())
            logging.getLogger("village").info("📡 radar-ingest: %d nieuw over %d feed(s)", n, len(uit))
        except Exception as e:                              # noqa: BLE001
            logging.getLogger("village").warning("radar-ingest faalde: %s", e)

    def _veilig_weekmemo(self) -> None:
        """De weekmemo: één synthese per ISO-week over de vijf bronnen, als DM bij de founder.

        NA de ingest en de legal-check gewired, om dezelfde reden als die twee onderling: wat
        vanochtend binnenkwam telt vandaag mee in plaats van pas volgende week.

        OP DE DAGCADANS, NIET ALS PULSE-SKILL OP EEN ROL. De memo is dorpswerk — hij leest vijf
        bronnen die bij verschillende domeinen horen en levert bij een mens af. Als skill zou hij
        een DNA-grant nodig hebben, en dan zou zijn ritme afhangen van welke rol hem toevallig
        draagt (de les van 28 augustus: de dagbel hoorde niet aan de facilitator te hangen).
        `weekmemo.ronde` bewaakt zijn eigen weekritme, dus dagelijks aantikken kost niets."""
        try:
            from nooch_village import weekmemo
            uit = weekmemo.ronde(self.context.data_dir, omgeving=self.context)
            logging.getLogger("village").info(
                "🗂 weekmemo %s: %s", uit.get("periode"), uit.get("reden") or "niets te melden")
        except Exception as e:                              # noqa: BLE001
            logging.getLogger("village").warning("weekmemo faalde: %s", e)

    def _veilig_weesprojecten(self) -> None:
        try:
            self._meld_weesprojecten()
        except Exception as e:                              # noqa: BLE001
            logging.getLogger("village").warning("weesprojecten-check faalde: %s", e)

    def run_forever(self):
        print(self.report_keys())
        self.bus.subscribe("pulse_completed", lambda e: logging.getLogger("village").info(
            "✅ dagpuls verwerkt — het dorp leeft en wacht nu op de volgende dag-puls. "
            "Geen nieuwe regels = normaal, niet vastgelopen. Ctrl+C om te stoppen."))
        # De nul moet zichzelf verklaren: na elke dag-puls één keer toetsen of elke pulse-skill
        # überhaupt een eigenaar heeft. Fail-soft — een controle mag de puls nooit breken.
        #
        # Op dag_begint, NIET pulse_completed (16 sept, gevonden tijdens het gdelt_tone-alert):
        # pulse_completed wordt uitsluitend gepubliceerd door website_watcher se eigen
        # _morning_pulse. Slaapt of archiveert die rol, dan vuurt dit vangnet dus NOOIT — precies
        # het patroon dat het hoort te detecteren, ondermijnt zichzelf. dag_begint komt uit
        # dagcyclus.py en is rolonafhankelijk (28 augustus-les), dus daar hangt het vangnet nu aan.
        self.bus.subscribe("dag_begint", lambda e: self._veilig_verweesd())
        # Zelfde controle, andere vraag: bezit een gearchiveerde/slapende rol nog open werk?
        # (Stefan, 15 sept: "we werken naar het verwijderen van de AI-rollen" — elke keer dat dat
        # gebeurt mag het werk dat erop stond niet stil verdwijnen, zoals bij harry_hemp nu al was.)
        self.bus.subscribe("dag_begint", lambda e: self._veilig_weesprojecten())
        # De radar-ingest: verhuisd van een losse crontab-regel naar de dagcadans (19 sept 2026).
        # Eerst ophalen, dan de weekmemo, zodat een vers signaal dezelfde puls nog wordt gezien.
        #
        # HIER STOND OOK `_veilig_legal_check`: de dagelijkse ronde die per legal-signaal een
        # inbox-item maakte. Weg op 20 september 2026 — sinds de weekmemo droeg diezelfde bron
        # twee uitgangen naar dezelfde mens, en dat is precies de vorm waarin twee beelden uit
        # elkaar gaan lopen. De memo leest de feed nu als een van de vijf bronnen.
        self.bus.subscribe("dag_begint", lambda e: self._veilig_radar_ingest())
        # De weekmemo als laatste in deze rij: hij leest wat de ingest net heeft opgeleverd. Zijn
        # eigen weekpoort zorgt dat hij hooguit één keer per ISO-week iets doet.
        self.bus.subscribe("dag_begint", lambda e: self._veilig_weekmemo())
        self.start()
        print("🌙 Het dorp draait (daemon). Zodra het log stilvalt is dat normaal: het wacht "
              "op de volgende dag-puls. Ctrl+C om te stoppen.\n")
        try:
            while True:
                time.sleep(self._board_poll_seconds)
                self._poll_board()          # bord-drag naar ACTIEF → binnen seconden opgepakt
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
        """Maak een project aan in het grootboek. Het staat dan in TOEKOMST (slapend); een mens
        sleept het naar Active, en dát is het signaal waar de rol op reageert (project_activated).
        Er gaat hier dus geen event meer uit (scope 49: het `project_queued`-event is weg)."""
        return self.context.projects.create(owner, scope, trigger)

    def _prime_board_watch(self) -> None:
        """Zaad de board-watch met de projecten die bij het opstarten AL 'running' zijn. Zo vuurt de
        eerste poll geen project_activated voor bestaande actieve projecten (die lopen al mee via de
        normale flow / dag_begint) — alleen NIEUWE naar-ACTIEF-overgangen tijdens de rit tellen."""
        led = getattr(self.context, "projects", None)
        from nooch_village.projects import plan_wacht_op_akkoord
        self._activated_seen = ({p["id"] for p in led.by_status("running") if not plan_wacht_op_akkoord(p)}
                                if led is not None else set())
        # DONE-brug (#10): al-afgeronde projecten primen zodat de eerste poll geen historische
        # project_completed vuurt — alleen NIEUWE review-goedkeuringen tijdens de rit tellen.
        self._completed_seen = {p["id"] for p in led.by_status("done")} if led is not None else set()

    def _poll_board(self) -> list[str]:
        """Board-watch (cross-proces-brug). Detecteer projecten die sinds de vorige poll naar 'running'
        zijn gezet — meestal een bord-drag naar ACTIEF in het losse cockpit-proces — of waarvan het
        uitvoerplan sinds de vorige poll is goedgekeurd, en kondig ze aan als project_activated zodat
        de eigenaar-rol ze binnen seconden oppakt. `by_status` triggert `_maybe_reload`, dus een
        externe schrijf naar projects.json wordt hier zichtbaar. dag_begint blijft het vangnet; dit is
        een versnelling, geen vervanging. Geeft de pids terug die nu aan de beurt zijn geraakt
        (voor tests/observatie)."""
        led = getattr(self.context, "projects", None)
        if led is None:
            return []
        running = {p["id"]: p for p in led.by_status("running")}
        # AAN DE BEURT = ACTIEF ÉN het uitvoerplan wacht niet meer op een mens. Sinds scope 4 zijn dat
        # TWEE overgangen die hetzelfde feit opleveren ("er is werk voor de eigenaar-rol"): de drag
        # naar ACTIEF, en het akkoord op het plan dat daarna gemaakt werd. Dat akkoord is geen
        # statuswijziging, dus een watch die alleen naar `running` kijkt ziet 'm nooit — je klikt
        # 'go ahead' en er gebeurt tot 04:32 de volgende ochtend niets. Eén set voor beide, zodat er
        # ook maar één plek is waar de dedup kan misgaan.
        from nooch_village.projects import plan_wacht_op_akkoord
        klaar = {pid: p for pid, p in running.items() if not plan_wacht_op_akkoord(p)}
        new_ids = [pid for pid in klaar if pid not in self._activated_seen]
        for pid in new_ids:
            self.bus.publish(Event("project_activated",
                                   {"pid": pid, "owner": klaar[pid].get("owner")}, "board_watch"))
        # Prune verdwenen pids: een project dat later opnieuw aan de beurt komt mag opnieuw vuren.
        self._activated_seen = set(klaar)
        # ── DONE-brug (#10-fix): project_completed vuurt voor ELKE nieuwe done (lifecycle-feit), zodat
        # ook een mens-DONE in het losse cockpit-proces de in-memory bus bereikt. De route wordt afgeleid:
        #   • autonoom — de rol-thread kondigde 'm al inline aan (_autonomous_done) → hier SKIPPEN (geen dubbel);
        #   • review   — via de gate: complete() liet blocked_on=="review" als marker staan;
        #   • direct    — mens sleepte Actief→Done zonder de gate.
        # Consumenten filteren zelf op route/deliverable_ids (zie WORKING_AGREEMENTS, kanaal-model).
        auto = getattr(self.context, "_autonomous_done", set())
        done = {p["id"]: p for p in led.by_status("done")}
        # Done → signaal op /signals (feed 'Projecten'), voor ELKE nieuwe done — óók de autonome,
        # die hieronder voor het event geskipt worden (al inline aangekondigd). De RadarStore wordt
        # hier vers geïnstantieerd op data_dir (de daemon-context kent geen _Stores); link-dedupe
        # ("/project?id=<pid>") maakt dit idempotent met de cockpit-hook. Fail-soft: een falend
        # signaal mag een done (of dit event) nooit blokkeren.
        nieuw_done = [pid for pid in done if pid not in self._completed_seen]
        # HIER STOND DE PROJECT→SIGNAAL→STAGING-LUS. Een afgerond project werd een radarsignaal en
        # zijn einddocument werd geatomiseerd naar de kennisbank-staging. Beide bestemmingen zijn op
        # 19 sept 2026 verdwenen (project_signal + de intake/staging-laag), en een afgerond project
        # hoort volgens het nieuwe model in de wiki te landen via Keep-in-wiki — met menselijke
        # input, niet als automatische atomisering.
        for pid, p in done.items():
            if pid in self._completed_seen or pid in auto:
                continue                                        # al gezien, of al inline aangekondigd (autonoom)
            route = "review" if p.get("blocked_on") == "review" else "direct"
            dstore = getattr(self.context, "deliverables", None)
            deliverable_ids = [r["id"] for r in dstore.for_project(pid)] if dstore is not None else []
            self.bus.publish(Event("project_completed",
                                   {"project_id": pid, "owner": p.get("owner"), "outcome": p.get("outcome"),
                                    "deliverable_ids": deliverable_ids, "route": route}, "board_watch"))
        # Prune: een heropend (done→running) project mag bij een latere her-afronding opnieuw vuren;
        # houd _autonomous_done gelijk aan de nog-done autonome pids.
        self._completed_seen = set(done)
        auto &= set(done)
        return new_ids


#: Rollen die de groei-puls dragen. Slaapt er één, dan komt `pulse_completed` niet — en dat mag
#: geen stilte zijn maar een melding met een naam.
_PULS_ROLLEN = ("website_watcher",)


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
    if not done:
        # STILTE IS GEEN UITKOMST. Dit printte "Field Note: None | tension=None" en dat leest als een
        # lege dag, niet als een uitgevallen puls. `pulse_completed` komt van een ROL, en een rol kan
        # slapen — dus zeg dat dan ook, met de naam erbij. De bel is inmiddels infrastructuur
        # (dagcyclus.py); het WERK dat erop volgt blijft rolwerk, en dat mag je zien.
        stil = [rid for rid in _PULS_ROLLEN if rid not in v.reconciler.live]
        waarom = (f" — slapend of onbemand: {', '.join(stil)}" if stil
                  else " — de rol draait wel; kijk in het log waar hij bleef")
        print(f"⚠️  Geen groei-puls afgerond (geen pulse_completed){waarom}")
        return
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
