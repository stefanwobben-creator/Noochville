from __future__ import annotations
import threading, logging, uuid, re, os, json, time
from nooch_village.util import atomic_write_json, read_json
from nooch_village.event_bus import EventBus, Event
from nooch_village.inbox import Inbox
from nooch_village.models import Task, Response, Record, RecordType, Tension
from nooch_village.skills import SkillRegistry
from nooch_village.projects import PREP_CHECKLIST_TITLE
from nooch_village.triage_engine import TriageContext, classify as _triage_classify
from nooch_village.coherence import evaluate_coherence


def _parse_opportunity(text: str) -> dict:
    """Parse het gestructureerde antwoord van de opportunity-reflex (TYPE/TITEL/WAT/WAAROM/
    EFFECT/EFFORT/CONFIDENCE) in gewone taal. Robuust tegen markdown/bullets."""
    out: dict = {}
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("*-•# ").strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower().strip("*").strip()
        val = val.strip().strip("*").strip()
        if not val:
            continue
        if key == "type":
            v = val.lower()
            out["type"] = ("amend_role" if "amend" in v else
                           "add_role" if "add" in v or "nieuwe" in v else "project")
        elif key in ("titel", "title"):
            out["titel"] = val[:120]
        elif key == "wat":
            out["wat"] = val[:600]
        elif key in ("waarom", "hypothese", "hypothesis"):
            out["waarom"] = val[:300]
        elif key == "effect":
            out["effect"] = val
        elif key == "effort":
            m = re.search(r"\d+", val)
            out["effort"] = int(m.group()) if m else 3
        elif key == "confidence":
            m = re.search(r"[\d.]+", val)
            out["confidence"] = float(m.group()) if m else 0.5
    return out


class Inhabitant(threading.Thread):
    """Eén rol per inwoner (leaf). Doet zelf werk via zijn skills."""

    def __init__(self, record: Record, bus: EventBus, registry: SkillRegistry, context):
        super().__init__(daemon=True, name=record.id)
        self.record = record
        self.id = record.id
        self.dna = record.definition
        self.bus = bus                 # geinjecteerd, geen global
        self.registry = registry
        self.context = context
        self.inbox = Inbox(self.id)
        self._stop_event = threading.Event()
        self.log = logging.getLogger(f"village.{self.id}")
        self._last_reflect: float = 0.0
        # Productie: wekelijks; demo/test: reflect_interval_seconds=0 → altijd
        self._reflect_interval: float = float(
            self.context.settings.get("reflect_interval_seconds", str(7 * 24 * 3600)))
        self._setup_events()
        self.react("project_queued", self._on_project_queued)
        # Uitvoer-primitief: elke dag mijn eigen projecten verzorgen (TOEKOMST=voorbereiden,
        # ACTIEF=uitvoeren). Universeel gewired (niet in _setup_events, dat subklassen overschrijven).
        self.react("dag_begint", self._tend_projects)
        # Versnelling: een statuswijziging naar ACTIEF (meestal een bord-drag in het losse
        # cockpit-proces) wordt door de village-board-watch vertaald naar project_activated. Pak dan
        # meteen ALLEEN dat ene project op, zonder op de dag-puls (dag_begint) te wachten — dat blijft
        # het vangnet. Zie Village._poll_board voor de cross-proces-brug.
        self.react("project_activated", self._on_project_activated)

    def _setup_events(self) -> None:
        """Koppel dag_begint aan _maybe_reflect. Rollen met een eigen pulsgate overschrijven dit."""
        self.react("dag_begint", self._maybe_reflect)

    @property
    def display_name(self) -> str:
        """Geeft de persona-naam als die gezet is, anders de rol-id."""
        return self.record.persona or self.id

    # --- buitenkant: van buiten ben ik gewoon een rol ---
    def capabilities(self) -> list[str]:
        return list(self.dna.skills)

    def deliver(self, task: Task) -> None:
        self.inbox.deliver(task)

    def ask(self, capability: str, payload: dict) -> str:
        rid = uuid.uuid4().hex
        self.bus.publish(Event("help_requested",
            {"request_id": rid, "capability": capability, "payload": payload, "from": self.id}, self.id))
        return rid

    # --- spelregel 5: rol-vraagt-rol om een accountability (dorpsbreed) ---
    def offer(self, accountability_key: str, handler) -> None:
        """Bied een accountability aan die elke andere rol mag aanvragen (spelregel 5).
        De eerste aanbieding abonneert op accountability_requested; de handler draait dan
        op de eigen thread van deze inwoner (via react)."""
        if not hasattr(self, "_offered"):
            self._offered: dict = {}
            self.react("accountability_requested", self._on_accountability_requested)
        self._offered[accountability_key] = handler

    def _on_accountability_requested(self, event: Event) -> None:
        if event.data.get("target") != self.id:
            return                                  # niet aan mij gericht
        key = event.data.get("accountability")
        handler = getattr(self, "_offered", {}).get(key)
        if handler is None:
            self.sense_tension(
                f"Gevraagd om accountability '{key}' die ik niet aanbied; "
                f"verzoeker: {event.data.get('from', '?')}", kind="operational")
            return
        self.log.info("📨 verzoek van %s: voer accountability '%s' uit",
                      event.data.get("from", "?"), key)
        result = handler(event.data.get("payload", {}))
        # Sluit de generieke offer→complete-lus: elke AANGEBODEN accountability meldt af met een
        # completion-event, zodat een wachter (bv. de ask_accountability-CLI) altijd antwoord krijgt —
        # ook als de handler geen eigen, specifiek event publiceert (voorheen deed alleen nl_corpus dat,
        # waardoor elke andere accountability eeuwig op 'geen antwoord' bleef staan).
        self.bus.publish(Event("accountability_check_completed", {
            "target":         self.id,
            "accountability": key,
            "from":           event.data.get("from", "?"),
            "result":         result if isinstance(result, dict) else {},
            "ok":             True,
        }, self.id))

    def propose_close(self, gap_key: str, reason: str) -> None:
        """Stel voor een inbox-item (met deze gap_key) te sluiten omdat ik de accountability nu
        dek: "ik dek dit nu, voorstel tot sluiten". De mens bevestigt met één klik; ik sluit
        nooit zelf — dat zou de dichtgeklapte lus zijn (het systeem dat z'n eigen huiswerk
        beoordeelt)."""
        self.bus.publish(Event("resolution_proposed",
            {"gap_key": gap_key, "reason": reason, "from": self.id}, self.id))

    def ask_accountability(self, target_role: str, accountability_key: str,
                           payload: dict | None = None) -> None:
        """Vraag een andere rol een van diens accountabilities op te pakken (spelregel 5).
        Geen commando: de rol-eigenaar beslist zelf of hij het doet of er een spanning van maakt.
        Een mens-bemenste rol (bv. de founder in the_source) is gewoon een van de vragers."""
        self.bus.publish(Event("accountability_requested", {
            "target":         target_role,
            "accountability": accountability_key,
            "payload":        payload or {},
            "from":           self.id,
        }, self.id))

    def sense_tension(self, description: str, kind: str = "operational",
                      evidence: dict | None = None) -> None:
        """Sens een spanning: logt naar het audittrail én triageert voor dispatch.

        evidence: optioneel verifieerbaar herhalingsbewijs uit het logboek
        (observaties/first_seen), zodat de poort echte feiten leest, geen woord."""
        tension = Tension(sensed_by=self.id, description=description, kind=kind,
                          evidence=evidence)
        self.bus.publish(Event("tension_sensed",
            {"by": self.id, "description": description, "kind": kind}, self.id))
        self.triage(tension)

    # ── Triage ─────────────────────────────────────────────────────────────────

    def triage(self, tension: Tension) -> None:
        """Classificeer en routeer een spanning via TriageEngine (dunne facade).

        1. Structureel/terugkerend  → Proposal via proposal_raised (governance-engine)
        2. Eigen werk               → zelf doen (al in uitvoering)
        3. Andere rol               → routeer via help_requested of broadcast
        4. Geen passende rol        → tactisch proberen; matchmaker escaleert naar mens
        """
        desc  = tension.description
        desc_l = desc.lower()

        llm = self._classify_llm(desc)
        ctx = TriageContext(
            role_id=self.id,
            purpose=self.dna.purpose,
            accountabilities=self.dna.accountabilities,
            domains=getattr(self.dna, "domains", []),
            records=getattr(self.context, "records", None),
        )
        result = _triage_classify(desc_l, ctx, llm_result=llm)

        if result.classification == "structureel":
            self._raise_governance_proposal(tension)
        elif result.classification == "eigen-werk":
            self._do_own_work(tension)
        elif result.classification.startswith("andere-rol:"):
            self._route_to_role(tension, result.target_role_id, result.target_capability)
        else:
            self._try_tactical_or_escalate(tension)

        self.bus.publish(Event("tension_triaged", {
            "by": self.id,
            "description": desc[:80],
            "classification": result.classification,
        }, self.id))

    def _raise_governance_proposal(self, tension: Tension) -> None:
        """Zet een structurele spanning om in een Proposal en stuur het door de engine."""
        from nooch_village.models import GovernanceChange, ChangeKind, Proposal
        from nooch_village.governance import proposal_to_dict

        desc   = tension.description
        desc_l = desc.lower()
        _ACC   = "accountability:"
        is_reflection = _ACC in desc_l

        # Eerlijke trigger: stempel het echte logboek-bewijs (observaties + sinds)
        # i.p.v. een zelfgeschreven woord. De poort (G0) leest dit. Zonder bewijs
        # (≥2 observaties) blijft de trigger neutraal en wijst G0 een add_role af —
        # precies wat we willen voor een eenmalig gat.
        ev  = tension.evidence or {}
        obs = ev.get("observations", 0)
        def _trigger(body: str) -> str:
            if obs >= 2:
                since = ""
                if ev.get("first_seen"):
                    import datetime
                    since = " sinds " + datetime.date.fromtimestamp(
                        ev["first_seen"]).isoformat()
                return f"{self.id}: gat meermaals waargenomen ({obs}x{since}); {body[:50]}"
            return f"{self.id}:{body[:80]}"

        if "policy" in desc_l and not is_reflection:
            pid = re.sub(r"\W+", "_", desc_l[:25]).strip("_")
            change = GovernanceChange(kind=ChangeKind.ADD_POLICY,
                                      policy_id=pid, policy_text=desc[:200])
        elif ("rol ontbreekt" in desc_l or "nieuwe rol" in desc_l) and not is_reflection:
            rid = re.sub(r"\W+", "_", desc_l[:20]).strip("_")
            change = GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id=rid,
                                      purpose=desc[:100], new_role_parent="noochville")
        elif is_reflection:
            # Extraheer de accountability-naam na het "accountability:"-marker
            idx      = desc_l.index(_ACC) + len(_ACC)
            acc_text = desc[idx:].strip()
            # Neem tot " — " of einde; trim tot 100 tekens
            acc_text = acc_text.split(" — ")[0].split("\n")[0].strip()[:100]
            change = GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=self.id,
                                      add_accountabilities=[acc_text])
        else:
            # classify_gap beslist A/B/C: A/B → geen geboorte, C → ADD_ROLE
            from nooch_village.gap_classifier import classify_gap
            from nooch_village.roster_match import (
                gap_signature, _role_id_from_gap, _purpose_from_gap)
            records = getattr(self.context, "records", None)
            recs_list = records.all() if records is not None else []
            outcome, matched_role, reason = classify_gap(desc, recs_list)
            if outcome == "A":
                self.log.info(
                    "✅ spanning A (gedekt door '%s'): %s — %s",
                    matched_role, desc[:60], reason)
                return
            elif outcome == "B":
                gap_key = re.sub(r"\W+", "_", desc[:30]).strip("_")
                self._report_means_gap(gap_key, desc)
                self.log.info(
                    "📌 spanning B → means-gap voor '%s': %s — %s",
                    matched_role, desc[:60], reason)
                return
            # C: geen dekkende rol.
            gap       = gap_signature(desc)
            r_id      = (_role_id_from_gap(gap) if gap
                         else re.sub(r"\W+", "_", desc[:20]).strip("_"))
            # Categorie-splitsing (Holacracy): een rol is een DOORLOPENDE
            # verantwoordelijkheid. Zonder herhalingsbewijs in het logboek is dit
            # geen rol maar een EENMALIGE individuele actie buiten ieders scope →
            # naar de mens, niet als (door G0 toch geweigerde) rol-geboorte.
            if obs < 2:
                self.log.info(
                    "🙋 C-gap zonder herhaling → individuele actie naar mens: %s",
                    desc[:60])
                self.bus.publish(Event("individuele_actie", {
                    "gap_key": r_id, "description": desc, "by": self.id}, self.id))
                return
            # obs ≥ 2: echt doorlopend gat → rol-voorstel (geboorte).
            # Purpose = de echte gat-beschrijving (een betekenisvolle zin), nooit
            # een mechanische term-smurrie ("Beheert en bewaakt X, Y, Z").
            r_purpose = desc[:100]
            change    = GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id=r_id,
                                         purpose=r_purpose, new_role_parent="noochville")
            proposal  = Proposal(
                proposer_role=self.id,
                change=change,
                tension=desc[:200],
                trigger_example=_trigger(desc),
                rationale=(
                    "Geen bestaande rol dekt deze accountability (classify_gap "
                    "uitkomst C). Het herhalingsbewijs staat in de trigger."
                ),
            )
            if not self._funnel_c_proposal(desc, r_id, recs_list):
                self.log.info(
                    "🚫 C-trechter: voorstel gedropt voor gap_key='%s'", r_id)
                return
            self.bus.publish(Event("proposal_raised",
                                   {"proposal": proposal_to_dict(proposal)}, self.id))
            self.log.info(
                "🏛️ structureel → voorstel %s (%s)", proposal.id, change.kind.value)
            return

        # Niet-C paden: policy / "rol ontbreekt" / reflectie
        if change.kind == ChangeKind.ADD_ROLE and not is_reflection:
            rationale = (
                "Structureel terugkerend gat: geen bestaande rol dekt deze "
                "accountability voldoende (classify_gap uitkomst C)."
            )
        else:
            rationale = (
                "Periodieke reflectie gesignaleerd: structureel gat tussen eigen capaciteit "
                "en vereiste accountability."
                if is_reflection
                else "Structurele spanning gedetecteerd via automatische triage"
            )
        proposal = Proposal(
            proposer_role=self.id,
            change=change,
            tension=desc[:200],
            trigger_example=_trigger(desc),
            rationale=rationale,
        )
        self.bus.publish(Event("proposal_raised",
                               {"proposal": proposal_to_dict(proposal)}, self.id))
        self.log.info("🏛️ structureel → voorstel %s (%s)", proposal.id, change.kind.value)

    def _funnel_c_proposal(self, gap_description: str, gap_key: str, records: list) -> bool:
        """Drie-filter trechter voor classify_gap C-voorstellen.

        Retourneert True als het voorstel door mag, False als het gedropt wordt.
        """
        # Filter 1: Kandidaat-dedup (deterministisch).
        for rec in records:
            if not getattr(rec, "archived", False) and rec.id == gap_key:
                self.log.info(
                    "C-trechter: dedup op gap_key=%s — record bestaat al", gap_key)
                return False

        # Filter 2: Recurrence-passage (no-op met logregel).
        # Twee-slag-gate upstream gegarandeerd, hier passage.
        self.log.info("C-trechter: recurrence al geverifieerd stroomopwaarts")

        # Filter 3: Coherentiepoort via LLM.
        # Fail-closed: error, unparseable en "vague" → False. Alleen "coherent" → True.
        verdict, reason_text = evaluate_coherence(gap_description)
        if verdict == "coherent":
            self.log.info(
                "C-trechter: coherentiepoort=coherent (%s), doorgelaten", reason_text)
            return True
        if verdict == "vague":
            self.log.warning(
                "C-trechter: coherentiepoort=vague (%s), dropped", reason_text)
            return False
        # error of unparseable → fail-closed
        self.log.warning(
            "C-trechter: coherentiepoort %s (%s), fail-closed dropped", verdict, reason_text)
        return False

    def _report_means_gap(self, gap_key: str, description: str) -> None:
        """Routeer een structurele capaciteitsgrens direct naar de inbox als means-gap-item.

        Gaat NIET door de governance-gate: geen amend_role, geen voorstel, geen churn.
        De inbox dedupt op gap_key zodat het hooguit één keer verschijnt.

        Cross-path-memory: staat dit gat al in de inbox-historie (welke status dan ook,
        ook resolved/withdrawn/deferred), dan eenmaal-gemeld-altijd-stil — niet opnieuw
        sensen. Anders blijft een rol elke reflect hetzelfde gat publiceren, en evalueert
        de B-observer het telkens opnieuw als ruis (de 'resolve-dan-opnieuw'-lus).
        """
        if self._means_gap_already_known(gap_key):
            self.log.info(
                "🤫 means-gap '%s' staat al in de inbox-historie → niet opnieuw gesensed",
                gap_key)
            return
        self.bus.publish(Event("means_gap_sensed", {
            "gap_key":     gap_key,
            "description": description,
            "by":          self.id,
        }, self.id))

    def _means_gap_already_known(self, gap_key: str) -> bool:
        """True als er al een means_gap-item met dit gap_key in de inbox staat — ongeacht
        status. Spiegelt de dedup-sleutel van HumanInbox.add_means_gap (type + subject),
        maar dan aan de sense-kant zodat ook het event en de B-observer-ruis stoppen."""
        data_dir = getattr(self.context, "data_dir", None)
        if not data_dir:
            return False
        inbox_path = os.path.join(data_dir, "human_inbox.json")
        if not os.path.exists(inbox_path):
            return False
        try:
            with open(inbox_path) as f:
                inbox = json.load(f)
        except Exception:
            return False
        return any(
            item.get("type") == "means_gap" and item.get("subject") == gap_key
            for item in inbox.values()
        )

    def _do_own_work(self, tension: Tension) -> None:
        """De spanning valt binnen mijn eigen rol — wordt hier al opgepakt."""
        self.log.info("🔧 spanning in eigen scope (%s) → geen aparte actie", self.id)

    def _route_to_role(self, tension: Tension, role_id: str, capability: str | None) -> None:
        """Routeer naar een andere rol die beter bij de spanning past."""
        if capability:
            self.ask(capability, {"description": tension.description, "from": self.id})
            self.log.info("🔀 spanning gerouteerd → %s via '%s'", role_id, capability)
        else:
            self.bus.publish(Event("tension_routed", {
                "from": self.id, "to": role_id,
                "description": tension.description[:80],
            }, self.id))
            self.log.info("🔀 spanning gerouteerd → %s (broadcast)", role_id)

    def _try_tactical_or_escalate(self, tension: Tension) -> None:
        """Geen passende rol gevonden. Probeer tactisch; matchmaker escaleert naar mens."""
        self.log.info("🔀 geen passende rol → tactisch via help_requested")
        self.ask("assistance", {
            "description": tension.description,
            "from": self.id,
            "context": "geen passende rol gevonden in het dorp",
        })

    def _classify_llm(self, desc: str) -> str | None:
        """Optionele LLM-classificatie. Geeft 'structural','own',<rol_id>,'tactical' of None."""
        from nooch_village.llm import reason
        records = getattr(self.context, "records", None)
        if records is None:
            return None
        roster = "\n".join(
            f"- {r.id}: {', '.join(r.definition.accountabilities[:3])}"
            for r in records.all() if not r.archived and r.id != self.id
        )
        prompt = (
            f"Jouw rol ({self.id}): {self.dna.purpose}\n"
            f"Jouw accountabilities: {', '.join(self.dna.accountabilities)}\n"
            f"Andere rollen:\n{roster}\n\n"
            f"Gevoelde spanning: \"{desc}\"\n\n"
            "Classificeer op EXACT ÉÉN regel (eerste match wint):\n"
            "STRUCTURAL  — terugkerend, governance-structuur ontbreekt of niemand bezit het\n"
            "OWN         — eenmalig werk dat binnen mijn eigen rol valt\n"
            "OTHER:<id>  — werk dat bij een andere bestaande rol past (geef de rol-id)\n"
            "TACTICAL    — eenmalig werk, geen passende rol"
        )
        out = reason(prompt, call_site="classify_tension")
        if not out:
            return None
        out_l = out.strip().lower().split("\n")[0]
        if out_l.startswith("structural"):
            return "structural"
        if out_l.startswith("own"):
            return "own"
        if out_l.startswith("other:"):
            return out_l[6:].strip()
        if out_l.startswith("tactical"):
            return "tactical"
        return None

    # ── Periodieke reflectie ────────────────────────────────────────────────────

    def _maybe_reflect(self, event: Event) -> None:
        """Reflecteer periodiek, niet bij elke dag_begint-puls."""
        now = time.time()
        if self._reflect_interval > 0 and now - self._last_reflect < self._reflect_interval:
            return
        self._last_reflect = now
        self._reflect()
        self._sense_redundancy()
        self._opportunity_reflex()

    def _opportunity_reflex(self) -> None:
        """Fase 2 — denk vanuit je rol één hoogst-renderende KANS richting de noordster, en zet
        die als onderbouwd voorstel (project / rol-uitbreiding / nieuwe rol) met hypothese +
        business-case op de backlog. Sensen + voorstellen, NOOIT zelf uitvoeren. Fail-closed
        zonder LLM. Mens beslist via de gate (governance) of pakt het project op."""
        from nooch_village.llm import reason
        from nooch_village.business_case import make_business_case, business_value
        dna = getattr(self, "dna", None)
        if dna is None:
            return
        records = getattr(self.context, "records", None)
        root = records.root() if records is not None else None
        if root is not None and self.id == root.id:
            return                                        # de wortelcirkel doet dit niet
        strat = getattr(self.context, "strategy", {}) or {}
        ns = strat.get("north_star", {}) or {}
        ns_txt = (f"{ns.get('target')} {ns.get('unit', '')} {ns.get('horizon', '')}".strip()
                  or "groei richting de missie")
        goals = "; ".join(g.get("description", "") for g in strat.get("goals", [])
                          if g.get("active")) or "—"
        eerder = self._rejected_opportunities()           # leerlus: niet herhalen, kalibreren
        eerder_txt = ""
        if eerder:
            eerder_txt = ("\nEerder door de mens AFGEWEZEN (niet opnieuw voorstellen, leer hiervan):\n"
                          + "\n".join(f"- {t}: {r}" for t, r in eerder[:5]) + "\n")
        regels = self._house_constraints()                 # vaste huis-regels: nooit tegen ingaan
        regels_txt = ""
        if regels:
            regels_txt = ("\nVASTE HUIS-REGELS (respecteer ALTIJD, stel niets voor dat hiertegen "
                          "ingaat):\n" + "\n".join(f"- {r}" for r in regels[:12]) + "\n")
        signalen_txt = self._training_signals()            # zachte oordelen: leer van beide kanten
        prompt = (
            f"Je bent de rol '{self.id}' in NoochVille. Purpose: {dna.purpose}\n"
            f"Accountabilities: {', '.join(dna.accountabilities) or '-'}\n"
            f"Skills: {', '.join(dna.skills) or '-'}\n"
            f"Noordster: {ns_txt}. Actief doel: {goals}.\n{regels_txt}{signalen_txt}{eerder_txt}\n"
            "Bedenk vanuit JOUW rol de ÉNE hoogst-renderende kans die ons dichter bij de noordster "
            "brengt: een project, een uitbreiding van je eigen rol, of een nieuwe rol.\n"
            "VUISTREGEL (belangrijk): begin bij een EXPERIMENT. Stel bij twijfel een PROJECT voor, "
            "niet meteen een accountability of nieuwe rol. Een accountability/rol is een STOLLING: "
            "alleen als iets meermaals terugkomt en structureel frictie geeft (anderen wachten erop). "
            "Een experiment mag vrij zolang het geen onomkeerbare schade kan doen.\n\n"
            "SCHRIJFREGELS (heel belangrijk):\n"
            "- Leg het idee uit alsof je het aan een 12-jarige vertelt. GEEN jargon, geen vakwoorden, "
            "geen afkortingen.\n"
            "- Verboden woorden (te zakelijk of verkeerd frame): validatie, valideren, transactie, "
            "conversie, optimaliseren, implementeren, funnel, KPI, e-commerce, doelgroep, consument. "
            "Gebruik gewone woorden.\n"
            "- Blijf in het BURGER-frame: het gaat om mensen die bewust kiezen, schoenen kópen en "
            "dragen — niet om 'consumenten', 'transacties' of 'conversies'.\n"
            "- Wees CONCREET: zeg wat er in de wereld of op het scherm verandert, niet een abstract "
            "proces. Stap voor stap als dat helpt.\n"
            "- Volledige zinnen, niet afgekapt. Kort mag, maar af.\n\n"
            "Antwoord exact zo:\n"
            "TYPE: project | amend_role | add_role\n"
            "TITEL: <korte naam, max 8 woorden>\n"
            "WAT: <2-4 zinnen: wat gaan we precies doen, in gewone taal>\n"
            "WAAROM: <1-2 zinnen: hoe helpt dit meer schoenen verkopen via nooch.earth>\n"
            "EFFECT: <geschat aantal extra paar schoenen, een getal>\n"
            "EFFORT: <1 (klein) tot 5 (groot)>\n"
            "CONFIDENCE: <0 tot 1: hoe zeker ben je>"
        )
        out = reason(prompt, call_site="opportunity_reflex")
        if not out:
            return
        o = _parse_opportunity(out)
        if not o.get("titel") or not o.get("wat"):
            return
        bc = make_business_case(metric=(ns.get("metric") or "pairs_sold"),
                                effect=o.get("effect", 0), effort=o.get("effort", 3),
                                confidence=o.get("confidence", 0.5),
                                horizon=ns.get("horizon", ""), rationale=o.get("waarom", ""))
        typ = o.get("type", "project")
        if typ == "project":
            # Mens-poort: een kans wordt GEEN project tot de mens akkoord geeft. Publiceer een
            # opportunity_sensed; de Village zet 'm als beslissing in de inbox/backlog.
            self.bus.publish(Event("opportunity_sensed", {
                "by": self.id, "title": o["titel"], "kind": "project",
                "wat": o["wat"], "waarom": o.get("waarom", ""), "business_case": bc}, self.id))
            self.log.info("💡 kans (project) → wacht op jouw akkoord: %s (waarde %s)",
                          o["titel"][:60], business_value(bc))
        else:
            self._raise_opportunity_governance(typ, o["titel"], o["wat"], o.get("waarom", ""), bc)

    def _rejected_opportunities(self) -> list[tuple]:
        """Lees de door de mens afgewezen kansen van DEZE rol (titel + reden) uit de inbox,
        zodat de reflex ze niet herhaalt en z'n schatting kan bijstellen. Read-only, fail-safe."""
        data_dir = getattr(self.context, "data_dir", None)
        if not data_dir:
            return []
        path = os.path.join(data_dir, "human_inbox.json")
        if not os.path.exists(path):
            return []
        inbox = read_json(path, {})
        out = []
        for item in inbox.values():
            ctx = item.get("context") or {}
            if (item.get("type") == "opportunity" and item.get("status") == "rejected"
                    and ctx.get("by") == self.id):
                out.append((item.get("subject", ""), item.get("resolution") or "afgewezen"))
        return out

    def _house_constraints(self) -> list[str]:
        """Lees de vaste huis-regels (uit triage) zodat de reflex er niet tegenin gaat. Read-only."""
        data_dir = getattr(self.context, "data_dir", None)
        if not data_dir:
            return []
        path = os.path.join(data_dir, "constraints.json")
        if not os.path.exists(path):
            return []
        return [c.get("text", "") for c in read_json(path, [], expect=list) if c.get("text")]

    def _training_signals(self) -> str:
        """Zachte oordeel-signalen van de mens (leuk idee / zachte nee / nu niet / elders) als
        prompt-blok, zodat de reflex van BEIDE kanten leert. Read-only, fail-safe → ''."""
        data_dir = getattr(self.context, "data_dir", None)
        if not data_dir:
            return ""
        path = os.path.join(data_dir, "feedback.json")
        if not os.path.exists(path):
            return ""
        try:
            from nooch_village.feedback import training_block
            with open(path) as f:
                return training_block(json.load(f), role=self.id)
        except Exception:
            return ""

    def _raise_opportunity_governance(self, typ: str, titel: str, wat: str, waarom: str,
                                      bc: dict) -> None:
        """Rol-uitbreiding of nieuwe rol als onderbouwd governance-voorstel (mens-gated).
        'wat' = het idee in gewone taal; 'waarom' = de bijdrage aan de noordster."""
        import hashlib
        from nooch_village.models import GovernanceChange, ChangeKind, Proposal
        from nooch_village.governance import proposal_to_dict
        h = hashlib.sha256((typ + titel).encode()).hexdigest()[:16]
        seen = getattr(self, "_opp_seen", None)
        if seen is None:
            seen = self._opp_seen = set()
        if h in seen:
            return                                        # dedup per proces
        seen.add(h)
        if typ == "amend_role":
            change = GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=self.id,
                                      add_accountabilities=[titel])
        else:                                             # add_role
            r_id = re.sub(r"\W+", "_", titel.lower())[:40].strip("_") or "nieuwe_rol"
            change = GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id=r_id,
                                      purpose=titel, new_role_parent="noochville")
        proposal = Proposal(
            proposer_role=self.id, change=change,
            tension=f"kans: {titel}"[:200],
            trigger_example=f"{self.id}: kans richting de noordster — {titel[:60]}",
            rationale=wat or waarom or "Onderbouwde kans uit de opportunity-reflex.",
            hypothesis=waarom, business_case=bc)
        self.bus.publish(Event("proposal_raised",
                               {"proposal": proposal_to_dict(proposal)}, self.id))
        self.log.info("💡 kans (%s) → voorstel %s: %s", typ, proposal.id, titel[:60])

    def _sense_redundancy(self, min_count: int = 2) -> bool:
        """Pioniers-reflectie (spiegelbeeld van gap-sensing): ben ik nog nodig?

        Als ELKE eigen accountability inmiddels door andere live rollen gedekt is,
        draft ik (na herhaalde bevestiging) een mens-gegateerd remove_role-voorstel
        voor mezelf. De pionier die verdwijnt zodra de bodem hersteld is. Schrijft
        zelf niets weg; de mens beslist via de gate (onomkeerbaar). Fail-closed
        richting behouden: twijfel betekent blijven.
        """
        records = getattr(self.context, "records", None)
        if records is None:
            return False
        root = records.root()
        if root is not None and self.id == root.id:
            return False   # de wortelcirkel heft zichzelf nooit op
        my_rec = records.get(self.id)
        if my_rec is None:
            return False
        my_accs = list(getattr(my_rec.definition, "accountabilities", None) or [])
        if not my_accs:
            return False

        from nooch_village.models import RecordType
        from nooch_village.redundancy import is_redundant
        others = {
            r.id: list(getattr(r.definition, "accountabilities", None) or [])
            for r in records.all()
            if r.id != self.id and not getattr(r, "archived", False)
            and r.type == RecordType.ROLE
        }
        redundant, coverers = is_redundant(my_accs, others)

        # Geduld + dedup via reflect-state (zelfde bestand als _sense_gap).
        path = os.path.join(self.context.data_dir, f"reflect_{self.id}.json")
        state = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    state = json.load(f)
            except Exception:
                pass
        rs = state.setdefault("_redundancy", {"count": 0, "emitted": False})

        if not redundant:
            rs["count"], rs["emitted"] = 0, False
            atomic_write_json(path, state)
            return False

        rs["count"] += 1
        if rs["emitted"] or rs["count"] < min_count:
            atomic_write_json(path, state)
            self.log.info("🪴 overbodigheid geregistreerd (%d/%d) — gedekt door %s",
                          rs["count"], min_count, ", ".join(coverers))
            return False

        rs["emitted"] = True
        atomic_write_json(path, state)
        self._propose_self_removal(coverers)
        return True

    def _propose_self_removal(self, coverers: list[str]) -> None:
        """Draft een remove_role-voorstel voor de eigen rol. Mens-gegateerd: de gate
        (G3) escaleert een remove_role met accountabilities naar de mens."""
        from nooch_village.models import GovernanceChange, ChangeKind, Proposal
        from nooch_village.governance import proposal_to_dict
        desc = (f"Pioniers-reflectie: alle accountabilities van '{self.id}' lijken "
                f"inmiddels gedekt door {', '.join(coverers)}. Kandidaat om de rol op "
                f"te heffen.")
        change = GovernanceChange(kind=ChangeKind.REMOVE_ROLE, role_id=self.id)
        proposal = Proposal(
            proposer_role=self.id,
            change=change,
            tension=desc[:200],
            trigger_example=f"{self.id}:redundancy:{','.join(coverers)[:60]}",
            rationale=("Zelf-overbodigheid: elke eigen accountability is door andere "
                       "live rollen gedekt. De pionier verdwijnt als de bodem hersteld "
                       "is. Mens beslist via de gate (onomkeerbaar)."),
        )
        self.bus.publish(Event("proposal_raised",
                               {"proposal": proposal_to_dict(proposal)}, self.id))
        self.log.info("🪴 zelf-overbodigheid → remove_role-voorstel %s (gedekt door %s)",
                      proposal.id, ", ".join(coverers))

    def _reflect(self) -> None:
        """Periodieke zelf-reflectie: vergelijk missie/doelen en eigen capaciteit.

        Subklassen overschrijven dit voor hun specifieke gaten.
        HARDE GRENS: produceer UITSLUITEND spanningen en voorstellen.
        Schrijf nooit nieuwe code, start nooit nieuwe externe verbindingen.
        Alles wat capaciteit uitbreidt is mens-gated activatie.
        """

    def _sense_gap(self, gap_key: str, description: str,
                   kind: str = "governance",
                   min_count: int = 2,
                   force: bool = False) -> bool:
        """Track een gat over meerdere reflecties; sens pas spanning bij aanhoudend bewijs.

        gap_key   : unieke sleutel voor dit gat (per rol in data/reflect_<id>.json)
        min_count : minimum observaties vóór spanning (default 2; voor ruis-filtering)
        force     : omzeil min_count — maar respecteert wél de dedup-check

        Dedup: als dit gat eerder gemeld is én de bijbehorende accountability al in
        het rol-record staat (of er een open inbox-item voor is), zwijg.
        Retourneert True als er een spanning gesensed is.
        """
        path = os.path.join(self.context.data_dir, f"reflect_{self.id}.json")
        state = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    state = json.load(f)
            except Exception:
                pass

        gap = state.setdefault(gap_key, {"count": 0, "emitted": False,
                                         "first_seen": None, "last_seen": None})
        now = time.time()
        if gap["first_seen"] is None:
            gap["first_seen"] = now
        gap["last_seen"] = now
        gap["count"] += 1

        # Dedup: als eerder gemeld, check of het gat al verwerkt is.
        if gap.get("emitted"):
            acc_text = gap.get("acc", "")
            in_dna   = bool(acc_text) and acc_text in (getattr(self.dna, "accountabilities", None) or [])
            in_inbox = self._gap_in_inbox(acc_text)
            if in_dna or in_inbox:
                atomic_write_json(path, state)
                self.log.debug("gap '%s' al gemeld en verwerkt, zwijg (dna=%s inbox=%s)",
                               gap_key, in_dna, in_inbox)
                return False
            # Geen verwerking gevonden (triage mislukt?) → reset, opnieuw rapporteren.
            gap["emitted"] = False

        emit = force or gap["count"] >= min_count
        if emit:
            gap["emitted"] = True
            gap["acc"]     = self._extract_acc_text(description)

        atomic_write_json(path, state)

        if emit:
            # Stempel het echte logboek-bewijs mee: de poort leest dit, niet de
            # zelfgeschreven rationale. count is hier al ≥ min_count (twee slagen).
            self.sense_tension(description, kind=kind, evidence={
                "observations": gap["count"],
                "first_seen": gap.get("first_seen"),
                "gap_key": gap_key,
            })
            self.log.info("🔍 gat '%s' → spanning gesensed (observaties: %d)", gap_key, gap["count"])
            return True
        self.log.info("🔍 gat '%s' geregistreerd (%d/%d — nog geen spanning)",
                      gap_key, gap["count"], min_count)
        return False

    @staticmethod
    def _extract_acc_text(description: str) -> str:
        """Extraheer de accountability-tekst zoals _raise_governance_proposal dat doet.

        Gebruikt als betrouwbare sleutel voor de DNA-check bij deduplicatie.
        """
        desc_l = description.lower()
        _ACC   = "accountability:"
        if _ACC not in desc_l:
            return ""
        idx      = desc_l.index(_ACC) + len(_ACC)
        acc_text = description[idx:].strip()
        return acc_text.split(" — ")[0].split("\n")[0].strip()[:100]

    def _gap_in_inbox(self, acc_text: str) -> bool:
        """Controleer of er al een open inbox-item bestaat dat de accountability adresseert."""
        if not acc_text:
            return False
        inbox_path = os.path.join(self.context.data_dir, "human_inbox.json")
        if not os.path.exists(inbox_path):
            return False
        try:
            with open(inbox_path) as f:
                inbox = json.load(f)
            return any(
                acc_text in json.dumps(item, ensure_ascii=False)
                for item in inbox.values()
                if item.get("status") in ("open", "pending")
            )
        except Exception:
            return False

    # ── Project-afhandeling ─────────────────────────────────────────────────────

    def _scan_queued_projects(self, event: Event) -> None:
        """Herstelpad: pik bij dag_begint queued-projecten op die via een extern proces
        zijn aangemaakt en waarvoor het project_queued-event gemist is.
        """
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            return
        for p in ledger.by_status("queued"):
            if p.get("owner") == self.id:
                self._claim_run_complete(p["id"])

    def _on_project_queued(self, event: Event) -> None:
        """Reageer op project_queued: alleen als ik de eigenaar ben."""
        if event.data.get("owner") != self.id:
            return
        pid = event.data.get("project_id")
        if pid is None:
            return
        self._claim_run_complete(pid)

    def _on_project_activated(self, event: Event) -> None:
        """Reageer op project_activated (statuswijziging → ACTIEF, meestal een bord-drag): alleen als
        ik de eigenaar ben. Voer UITSLUITEND dit ene project uit (niet _tend_projects over het hele
        bord). Idempotent via last_tended; geen checklist → project_needs_preparation — beide zitten al
        in _claim_run_complete/_execute_checklist, dus geen dubbele notes en geen stil falen."""
        if event.data.get("owner") != self.id:
            return
        pid = event.data.get("pid")
        if pid is None:
            return
        self._claim_run_complete(pid)

    _PREP_CHECKLIST_TITLE = PREP_CHECKLIST_TITLE          # gedeelde bron (nooch_village.projects)
    _WIP_POLICY_ID = "WIP-001"                    # cirkelpolicy die de voorbereidings-WIP-limiet aanzet

    @staticmethod
    def _extract_json(text):
        """Pak het eerste JSON-object uit een LLM-antwoord, robuust tegen markdown-fences (```json …```),
        leidend/volgend proza en whitespace. None als er geen geldig object in zit."""
        if not text:
            return None
        s = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL | re.IGNORECASE)   # ```json … ``` eraf
        if fence:
            s = fence.group(1).strip()
        m = re.search(r"\{.*\}", s, re.DOTALL)                                        # eerste {…}-blok
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    def _scope_text(self, project: dict) -> str:
        sc = project.get("scope")
        if isinstance(sc, str):
            return sc.strip()
        if isinstance(sc, dict):
            return str(sc.get("goal") or sc.get("title") or "").strip()
        return ""

    def _project_checklist(self, project: dict) -> dict | None:
        """Het voorbereide uitvoerplan (named checklist met onze titel), of None."""
        if not project:
            return None
        for cl in project.get("checklists", []):
            if cl.get("title") == self._PREP_CHECKLIST_TITLE:
                return cl
        return None

    def _tend_projects(self, event: "Event | None" = None) -> None:
        """Dagelijkse verzorging van mijn EIGEN projecten: voorbereiden in TOEKOMST (status future, begrensd
        door de WIP-cirkelpolicy), uitvoeren in ACTIEF (status queued/running). Andere kolommen ongemoeid."""
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            return
        my_future = [p for p in ledger.by_status("future") if p.get("owner") == self.id]
        limit = self._wip_prepare_limit()                        # WIP-001 aan + AI-manned → N; anders None
        if limit is None:
            to_prepare = my_future                               # geen policy/limiet → alle (idempotent)
        else:
            prepared = sum(1 for p in my_future if self._project_checklist(p) is not None)
            slots = max(0, limit - prepared)                     # vrije WIP-plekken
            unprepared = sorted((p for p in my_future if self._project_checklist(p) is None),
                                key=lambda p: p.get("created_at", 0))   # FIFO: oudste TOEKOMST eerst
            to_prepare = unprepared[:slots]                      # de rest WACHT tot een plek vrijkomt
        for p in to_prepare:
            self.prepare_project(p["id"])
        for status in ("queued", "running"):                     # ACTIEF → uitvoeren (DEEL B)
            for p in ledger.by_status(status):
                if p.get("owner") == self.id:
                    self._claim_run_complete(p["id"])

    def _wip_prepare_limit(self):
        """De WIP-limiet op voorbereiding (int), of None (geen limiet). De cirkelpolicy WIP-001 is de
        expliciete AAN-schakelaar (via own_and_inherited op de omvattende cirkel); het getal N komt uit
        config (`wip_prepare_limit`, default 8) — NIET uit de policy-body. Geldt alleen voor AI-bemande
        rollen (persona_id gezet); mens-bemande rollen bereiden niet autonoom voor. Fail-closed: ontbreekt
        een leesbron → None (huidig, ongelimiteerd gedrag)."""
        if not getattr(self.record, "persona_id", None):
            return None                                          # mens-bemand → geen autonome voorbereiding
        att = getattr(self.context, "att", None)
        records = getattr(self.context, "records", None)
        if att is None or records is None:
            return None
        from nooch_village import artefacts
        try:
            pols = artefacts.own_and_inherited(self.id, "policy", records, att)
        except Exception:
            return None
        active = list(pols.get("own", [])) + [d["artefact"] for d in pols.get("inherited", [])]
        on = any(getattr(a, "id", "") == self._WIP_POLICY_ID and getattr(a, "status", "") == "active"
                 for a in active)
        if not on:
            return None                                          # policy afwezig/inactief → geen limiet
        try:
            return max(0, int(self.context.settings.get("wip_prepare_limit", "8")))
        except (TypeError, ValueError):
            return 8

    # ── DEEL A: voorbereiding (alleen voor een string-scope project in TOEKOMST) ──────────────
    def prepare_project(self, pid: str) -> None:
        """Breek het projectdoel op in een checklist: per item een skill-referentie OF 'geen skill' + reden.
        Draait ALLEEN voor een string-scope project in TOEKOMST zonder checklist. Voert NIETS uit; het
        project blijft in TOEKOMST."""
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            return
        p = ledger.get(pid)
        if p is None or p.get("status") != "future" or not isinstance(p.get("scope"), str):
            return                                                # alleen TOEKOMST + string-doel
        goal = self._scope_text(p)
        if not goal or self._project_checklist(p) is not None:
            return                                                # geen doel of al voorbereid (idempotent)
        plan = self._plan_checklist(goal, keyword=p.get("keyword") or "", exclude_pid=pid,
                                    description=p.get("description"))
        if plan is None:
            self.log.warning("📋 project '%s': geen checklist voorbereid (LLM-plan mislukte); blijft in TOEKOMST", pid)
            return
        cl = ledger.checklist_add(pid, title=self._PREP_CHECKLIST_TITLE)
        if cl is None:
            return
        n_skill = n_open = n_invalid = 0
        opens = []
        for it in plan["items"]:
            skill = it.get("skill")
            payload = it.get("payload") if isinstance(it.get("payload"), dict) else None
            reason = it.get("reason", "")
            payload_ok = True
            if skill:                                            # fail-fast: payload compleet vóór opslag?
                missing = self._missing_required(skill, payload or {})
                if missing:
                    payload_ok = False
                    reason = f"payload onvolledig: {', '.join(missing)} ontbreekt"
            ledger.check_add(pid, cl["id"], it.get("text", ""), skill=skill, payload=payload,
                             query=it.get("query", ""), reason=reason, payload_ok=payload_ok)
            if not skill:
                n_open += 1
                opens.append(f"{it.get('text','')}: {reason or 'geen skill'}")
            elif not payload_ok:
                n_invalid += 1
                opens.append(f"{it.get('text','')}: {reason}")
            else:
                n_skill += 1
        ledger.add_role_message(pid, (
            f"📋 Uitvoerplan voor '{goal}'. Deliverable: {plan.get('deliverable','')}. "
            f"{n_skill} item(s) uitvoerbaar, {n_open} zonder skill, {n_invalid} met onvolledige payload"
            + (": " + "; ".join(opens) if opens else "") + "."))
        self.log.info("📋 project '%s' voorbereid: %d uitvoerbaar, %d zonder skill, %d onvolledige payload",
                      pid, n_skill, n_open, n_invalid)

    def _missing_required(self, skill: str, payload: dict) -> list[str]:
        """Verplichte payload-velden (skill.required_payload) die ontbreken of leeg zijn. Leeg = geen
        validatie mogelijk (skill onbekend of geen required_payload) → fail-soft (item blijft uitvoerbaar)."""
        obj = self.registry.get(skill) if self.registry else None
        req = tuple(getattr(obj, "required_payload", ()) or ()) if obj is not None else ()
        pl = payload if isinstance(payload, dict) else {}
        return [f for f in req if not pl.get(f)]                  # ontbreekt of leeg (None/""/[]/{})

    def _opdracht_section(self, description) -> str:
        """De opdracht van de mens (p['description']) als prompt-sectie — die stuurt de planning.
        Leeg/ontbrekend → "" (geen lege kop). Hard begrensd op description_context_max_chars (default
        1500), nette woord-grens-afkap. Fail-closed: een corrupt/onleesbaar veld mag de prep nooit
        laten vallen (comments/wall lezen we bewust NIET mee — dat dekt de mention-feature later)."""
        try:
            d = (description or "").strip()
            if not d:
                return ""
            limit = int(self.context.settings.get("description_context_max_chars", "1500"))
            if len(d) > limit:
                cut = d[:limit].rsplit(" ", 1)[0]
                d = (cut or d[:limit]) + "…"
            return f"Opdracht van de mens (de checklist moet hieraan voldoen):\n{d}\n\n"
        except Exception:
            return ""

    def _plan_checklist(self, goal: str, *, keyword: str = "", exclude_pid: str = "",
                        description: str = "") -> dict | None:
        """LLM-stap (Noochie): toets het doel tegen mijn accountabilities + skills → checklist met per item
        de skill ÉN een payload in de vorm die de skill z'n input_schema voorschrijft. Machine-check: een
        skill buiten mijn harde DNA-lijst wordt 'geen skill' + reden. Fail-soft: een skill zonder ingevuld
        input_schema laat de LLM terugvallen op naam + description.

        `keyword`/`exclude_pid`: voeden de geheugen-laag (bestaande deliverables als context), fail-closed."""
        from nooch_village.llm import reason as llm_reason
        skills = list(self.dna.skills)
        catalog_lines = []
        for name in skills:                                      # catalogus mét description + input-vorm
            obj = self.registry.get(name) if self.registry else None
            desc = (getattr(obj, "description", "") or "").strip() if obj else ""
            insch = (getattr(obj, "input_schema", "") or "").strip() if obj else ""
            catalog_lines.append(f"- {name}: {desc[:160]}\n    input: " +
                                 (insch or "(geen schema — leid af uit naam/omschrijving)"))
        catalog = "\n".join(catalog_lines) or "(geen skills)"
        # Geheugen-laag (fase 1): bestaande deliverables als context. Config-geschakeld, fail-closed —
        # een leeg blok laat de sectie volledig weg (geen lege kop in de prompt).
        memory_section = ""
        if str(self.context.settings.get("deliverable_context_enabled", "1")) == "1":
            from nooch_village.deliverable_context import gather_deliverable_context
            blok = gather_deliverable_context(
                getattr(self.context, "projects", None), goal, keyword=keyword,
                max_notes=int(self.context.settings.get("deliverable_context_max_notes", "5")),
                max_chars=int(self.context.settings.get("deliverable_context_max_chars", "2000")),
                exclude_pid=exclude_pid, store=getattr(self.context, "deliverables", None))
            if blok:
                memory_section = ("Eerder afgerond onderzoek in het dorp (gebruik dit; plan geen items "
                                  f"die dit al beantwoordt):\n{blok}\n\n")
        opdracht_section = self._opdracht_section(description)   # mens-opdracht: stuurt de planning
        prompt = (
            f"Je bent {self.name}, een autonome rol. Projectdoel:\n\"{goal}\"\n\n"
            f"{opdracht_section}"
            f"Jouw skills (de ENIGE tools die je hebt), met hun INPUT-vorm:\n{catalog}\n\n"
            f"Jouw accountabilities: {list(self.dna.accountabilities) or '(geen)'}\n\n"
            f"{memory_section}"
            "Breek het doel op in 2 tot 5 concrete deel-items. Voor ELK item: als één van jouw skills het "
            "kan uitvoeren, geef de exacte skill-naam ÉN een 'payload'-object dat EXACT voldoet aan de "
            "'input'-vorm van die skill (bv. een term-skill wil {\"term\": \"...\"}, keywords_everywhere wil "
            "{\"kw\": [\"...\"]}, een merken-skill wil {\"brands\": [\"...\"]}). Kan geen enkele skill het item "
            "uitvoeren, zet \"skill\": null, \"payload\": {} en geef een korte reden (bv. \"geen patent-skill\"). "
            "Bepaal ook welke accountability het doel raakt en welke deliverable erbij hoort. "
            "Antwoord UITSLUITEND met JSON, exact dit schema:\n"
            "{\"deliverable\": \"...\", \"accountability\": \"...\", \"items\": [{\"text\": \"...\", "
            "\"skill\": \"skillnaam of null\", \"payload\": {}, \"reason\": \"...\"}]}"
        )
        # Ruim token-budget: een verbose trede (bv. mistral) kapt het plan-JSON anders middenin af →
        # onparsebaar. 1500 tokens is genoeg voor 2-5 items met payloads en langere velden.
        raw, tier = llm_reason(prompt, json_mode=True, return_tier=True, max_tokens=1500,
                               call_site="plan_checklist")
        if raw is None:                                          # onderscheid: LLM gaf niets terug…
            self.log.warning("📋 plan: LLM leverde geen antwoord (alle tredes uitgeput)")
            return None
        data = self._extract_json(raw)
        if not self._is_valid_plan(data):                        # …vs LLM antwoordde maar niet-parsebaar
            self.log.info("📋 plan: antwoord van %s niet parsebaar — gerichte retry (strak JSON)", tier)
            strak = prompt + ("\n\nBELANGRIJK: antwoord met ALLEEN het JSON-object — geen ``` fences, "
                              "geen uitleg ervoor of erna. Houd de tekst-, reason- en deliverable-velden kort.")
            raw2, tier2 = llm_reason(strak, json_mode=True, return_tier=True, max_tokens=1500,
                                     call_site="plan_checklist_retry")
            data = self._extract_json(raw2) if raw2 is not None else None
            if not self._is_valid_plan(data):
                self.log.warning("📋 plan: LLM-antwoord NIET PARSEBAAR (via %s). Rauw (afgekapt): %r",
                                 tier2 or tier, (raw2 or raw or "")[:400].replace("\n", " "))
                return None
        for it in data["items"]:
            sk = it.get("skill")
            if sk and sk not in skills:                          # machine-check tegen de harde DNA-lijst
                it["reason"] = ((it.get("reason") or "") + f" (voorgestelde skill '{sk}' niet in DNA)").strip()
                it["skill"] = None
                it["payload"] = {}
        return data

    @staticmethod
    def _is_valid_plan(data) -> bool:
        """Een bruikbaar plan = dict met een niet-lege 'items'-lijst."""
        return isinstance(data, dict) and isinstance(data.get("items"), list) and bool(data["items"])

    # ── DEEL B: uitvoering (bij de puls voor projecten in ACTIEF) ─────────────────────────────
    def _claim_run_complete(self, pid: str) -> None:
        """Voer een ACTIEF project uit via zijn checklist. Markeert DONE ALLEEN als run_project een outcome
        teruggeeft (alle items af). Geen valse done: onvoltooide checklist → blijft in ACTIEF."""
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            self.log.warning("project '%s': geen ProjectLedger in context", pid)
            return
        project = ledger.get(pid)
        if project is None:
            self.log.warning("project '%s': niet gevonden", pid)
            return
        ledger.start(pid)
        outcome = self.run_project(project)
        current = ledger.get(pid)
        if outcome is not None and current and current["status"] == "running":
            ledger.complete(pid, outcome)
            # Levenscyclus-event: de ENIGE autonome DONE-route (de guard hierboven is de idempotentie —
            # een tweede passage op een al-done project valt buiten 'status==running' en vuurt niets).
            # Sleutel heet project_id (conform project_queued/needs_preparation; NIET 'pid').
            dstore = getattr(self.context, "deliverables", None)
            deliverable_ids = [r["id"] for r in dstore.for_project(pid)] if dstore is not None else []
            # Markeer als autonoom aangekondigd zodat de board-watch deze done niet dubbel vuurt.
            auto = getattr(self.context, "_autonomous_done", None)
            if auto is not None:
                auto.add(pid)
            self.bus.publish(Event("project_completed",
                                   {"project_id": pid, "owner": self.id, "outcome": outcome,
                                    "deliverable_ids": deliverable_ids, "route": "autonoom"}, self.id))
            self.log.info("✅ project '%s' afgerond (outcome=%s)", pid, outcome)
        else:
            self.log.info("⏸ project '%s' nog niet af (status=%s)", pid, current and current["status"])

    def run_project(self, project: dict) -> str | None:
        """Uitvoering van een string-scope project via zijn voorbereide checklist (DEEL B). Geeft een
        outcome-marker terug ALLEEN als alle items af zijn; anders None (blijft in ACTIEF). Géén stub:done.
        (Discovery-scope wordt door de subklasse-override afgevangen vóór deze basis wordt bereikt.)"""
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        return self._execute_checklist(project, today)

    def _execute_checklist(self, project: dict, today: str) -> str | None:
        pid = project["id"]
        ledger = self.context.projects
        cl = self._project_checklist(project)
        if cl is None or not cl.get("items"):
            self.log.warning("⚠️ project '%s' in ACTIEF zonder voorbereiding — sleep terug naar TOEKOMST "
                             "voor voorbereiding", pid)
            self.bus.publish(Event("project_needs_preparation",
                                   {"project_id": pid, "owner": self.id}, self.id))
            return None
        if project.get("last_tended") == today:
            return None                                          # idempotent: al vandaag uitgevoerd
        clid = cl["id"]
        succeeded = 0                                            # geslaagde items deze puls → één synthese-pass
        for pos, item in enumerate(cl["items"]):
            if item.get("done"):
                continue                                         # idempotent: reeds afgevinkt
            skill = item.get("skill")
            if not skill:
                continue                                         # geen-skill-item blijft open (reden in item)
            if item.get("payload_ok") is False:
                continue                                         # onvolledige payload → skill NIET draaien, blijft open (reden in item)
            payload = item.get("payload")
            if not isinstance(payload, dict) or not payload:
                q = item.get("query", "")
                payload = {"term": q} if q else {}               # legacy back-compat ({term: query})
            result = self.use_skill(skill, payload)
            status, archetype = self._classify_result(result)    # normaliseer beide fail-conventies
            if status == "gelukt":
                summary = self._deliverable_note(item, result, archetype)
                wall_note_id = ledger.add_role_message(pid, summary)
                self._store_deliverable(project, item, pos, skill, result, summary, wall_note_id)
                ledger.check_toggle(pid, clid, item["id"])
                succeeded += 1
                self.log.info("✅ project '%s': item '%s' via %s afgerond", pid, item.get("text", "")[:40], skill)
            else:
                why = (result.get("error") or result.get("reason") or
                       ("geen resultaat" if status == "leeg" else "skill leverde geen resultaat"))
                ledger.add_role_message(pid, f"⚠️ '{item.get('text','')}' via {skill} niet gelukt ({status}): {why}")
                self.log.warning("⚠️ project '%s': item '%s' via %s %s: %s",
                                 pid, item.get("text", "")[:40], skill, status, why)
        ledger.mark_tended(pid, today)
        fresh_cl = self._project_checklist(ledger.get(pid)) or {}
        items = fresh_cl.get("items", [])
        done = sum(1 for it in items if it.get("done"))
        total = len(items)
        if total and done == total:
            # Review-gate: checklist volledig af → status 'wacht' (blocked, blocked_on='review'), NIET done.
            # De outcome-marker wordt pas bij Done-toekenning (mens sleept wacht→done) gezet. Alleen op een
            # VERSE all-done-overgang (review_raised nog niet gezet) — zo herblokkeert een afgewezen-en-
            # teruggesleept project niet elke puls (Q2).
            if not (ledger.get(pid) or {}).get("review_raised"):
                ledger.mark_awaiting_review(pid)
                self._synthesize_einddocument(ledger.get(pid), done, total, force_final=True)
                ledger.add_role_message(pid, "✅ Checklist voltooid — klaar voor review.")
                self.bus.publish(Event("project_awaiting_review",
                                       {"project_id": pid, "owner": self.id}, self.id))
                self.log.info("✅ project '%s' checklist voltooid (%d/%d) — wacht op review", pid, done, total)
            return None                                          # geen autonome DONE meer
        if succeeded:                                            # ≥1 item geslaagd deze puls → één reguliere pass
            self._synthesize_einddocument(ledger.get(pid), done, total, force_final=False)
        self.log.info("⏳ project '%s' voortgang %d/%d — blijft in ACTIEF", pid, done, total)
        return None

    def _synthesize_einddocument(self, project: dict, done: int, total: int, *, force_final: bool) -> None:
        """Constitutie-plicht (basisklasse, GEEN skill, GEEN governance per rol): werk het levende
        einddocument van het project bij in de PERSONA-stem. Eén synthese-call per project per puls
        (de caller vuurt hooguit één keer). Fail-closed: geen LLM-antwoord of exceptie → document
        ONGEWIJZIGD, logregel; wall/store/gate draaien door (de review-gate werkt ook zonder document).

        v1-besluit: de AI schrijft het HELE document (geen diff, geen merge-logica). Mens-edits via de
        edit-route zijn input voor de VOLGENDE pass (last-writer geldt tot dan). #task-comments van
        mensen (project["comments"]) gaan als sturing mee — dezelfde bron die de worker leest.
        #task-regels ÍN de documenttekst worden NIET geparseerd (v2-idee: liften naar de wall; nu niet)."""
        store = getattr(self.context, "project_docs", None)
        if store is None or project is None:
            return
        pid = project["id"]
        try:
            from nooch_village.llm import reason
            from nooch_village.project_worker import _persona_for
            persona = _persona_for(self.record, getattr(self.context, "personas", None))
            current = store.read(pid)
            dstore = getattr(self.context, "deliverables", None)
            recs = dstore.for_project(pid) if dstore is not None else []
            d_lines = []
            for r in recs:                                       # summaries altijd; content als GECAPTE preview
                d_lines.append(f"- {r.get('summary', '')}")
                content = dstore.content_for(r["id"]) if dstore is not None else None
                if content is not None:
                    d_lines.append(f"  (preview: {str(content)[:500]})")
            steer = " · ".join(c.get("text", "") for c in project.get("comments", []) if c.get("text"))
            scope = project.get("scope")
            scope_txt = (" · ".join(f"{k}: {v}" for k, v in scope.items())
                         if isinstance(scope, dict) else str(scope or ""))
            # Harde input-cap vóór de call (fail-loud bij afkap — nooit stil, call_site="einddocument").
            cap = int(self.context.settings.get("einddocument_input_max_chars", "20000"))
            variable = ("HUIDIG DOCUMENT:\n" + (current or "(nog geen document)") + "\n\n"
                        + "OPGELEVERDE DELIVERABLES:\n" + ("\n".join(d_lines) or "(nog geen)") + "\n\n"
                        + (f"STURING VAN DE MENS (#task-comments, volg dit): {steer}\n\n" if steer else ""))
            if len(variable) > cap:
                self.log.warning("DOC_INPUT_CAP: einddocument-input %d tekens > max %d — afgekapt | project=%s",
                                 len(variable), cap, pid)
                variable = variable[:cap]
            prompt = (
                (persona.strip() + "\n\n" if persona and persona.strip() else "")
                + f"Je werkt aan het lopende einddocument van dit project in NoochVille (Nooch.earth). "
                f"Projectdoel: {scope_txt}\n\n" + variable
                + "Schrijf het VOLLEDIGE, bijgewerkte einddocument in markdown — een lopend, leesbaar "
                "verhaal dat de opgeleverde deliverables integreert"
                + (" en klaar is voor review" if force_final else "")
                + ". Geef alleen het document terug, geen meta-uitleg.")
            out = reason(prompt, call_site="einddocument", max_tokens=1500)
        except Exception as e:                                   # fail-closed: document intact, puls draait door
            self.log.warning("einddocument-synthese overgeslagen (document intact): %s", e)
            return
        if not out or not out.strip():
            self.log.info("einddocument: geen LLM-antwoord voor project '%s' — document ongewijzigd", pid)
            return
        store.write(pid, out.strip())
        if force_final:
            self.context.projects.add_role_message(pid, "📄 Einddocument bijgewerkt — klaar voor review.")

    # Container-keys per archetype — de note-opmaak volgt de VORM van de output, niet de skill-naam.
    _LIST_KEYS = ("hits", "rows", "candidates", "items", "targets", "cards", "keywords", "patents")
    _TEXT_KEYS = ("text", "vraag", "voorstel")
    _METRIC_KEYS = ("values", "value", "results", "series")

    @classmethod
    def _classify_result(cls, result):
        """Normaliseer de twee fail-conventies ({error}/{no_data} en {ok:False,error}) naar één uitkomst:
        ('gelukt'|'leeg'|'fout', archetype). archetype = ('list'|'dictlist'|'text'|'metric', container_key)
        bij succes, anders None. Hierop vinkt het primitief af (gelukt) of laat open (leeg/fout)."""
        if not isinstance(result, dict):
            return "fout", None
        if result.get("error") or result.get("ok") is False:
            return "fout", None
        if result.get("no_data"):
            return "leeg", None
        for k in cls._LIST_KEYS:
            v = result.get(k)
            if isinstance(v, list):
                return ("gelukt" if v else "leeg"), ("list", k)
            if isinstance(v, dict):                              # bv. keywords_everywhere: {keyword: {...}}
                return ("gelukt" if v else "leeg"), ("dictlist", k)
        for k in cls._TEXT_KEYS:
            v = result.get(k)
            if isinstance(v, str) and v.strip():
                return "gelukt", ("text", k)
        for k in cls._METRIC_KEYS:
            if result.get(k) not in (None, "", [], {}):
                return "gelukt", ("metric", k)
        return "leeg", None                                     # geen herkende inhoud → leeg

    def _store_deliverable(self, project: dict, item: dict, position: int, skill: str, result,
                           summary: str, wall_note_id) -> None:
        """Bewaar het VOLLEDIGE skill-resultaat als gestructureerd record (naast de wall-note). Additief
        en NOOIT blokkerend: geen store in context → skip; een schrijffout → luide logregel en door
        (de wall-note staat al). Alleen voor geslaagde items; faalnotes (⚠️) komen hier niet.

        `checklist_item` = het adresseerbare item-id; ontbreekt dat (afwijkend/legacy item), dan de
        positie `pos:<index>` als adres, mét een luide logregel. `title` = de leesbare item-tekst."""
        store = getattr(self.context, "deliverables", None)
        if store is None:
            return
        item_ref = item.get("id")
        if not item_ref:                                    # geen id → positie als adres, luid gemeld
            item_ref = f"pos:{position}"
            self.log.warning("deliverable: checklist-item zonder id → positie-adres '%s' gebruikt", item_ref)
        try:
            store.add(project_id=project.get("id", ""), role=self.id, skill=skill,
                      checklist_item=item_ref, title=item.get("text", ""),
                      content=result, summary=summary, wall_note_id=wall_note_id or "",
                      max_bytes=int(self.context.settings.get("deliverable_content_max_bytes", "100000")))
        except Exception as e:                              # store is additief → nooit de puls breken
            self.log.warning("deliverable-record niet opgeslagen (wall-note staat wél): %s", e)

    def _deliverable_note(self, item: dict, result: dict, archetype) -> str:
        """Rauw-maar-leesbaar per archetype; geen velden weggooien, geen gemene-deler-vorm."""
        head = f"📎 {item.get('text','')} — via {item.get('skill')}"
        kind, key = archetype if archetype else (None, None)
        if kind == "list":
            recs = result.get(key, [])
            return "\n".join([f"{head}: {result.get('total', len(recs))} resultaten"]
                             + ["• " + self._format_record(r) for r in recs[:5]])
        if kind == "dictlist":
            d = result.get(key, {})
            return "\n".join([f"{head}: {len(d)} resultaten"]
                             + ["• " + self._format_record({"key": n, **(r if isinstance(r, dict) else {"value": r})})
                                for n, r in list(d.items())[:5]])
        if kind == "text":
            return f"{head}:\n{(result.get(key) or '')[:1500]}"
        if kind == "metric":
            return f"{head}:\n{self._format_metric(result.get(key))}"
        return f"{head}: {self._format_record(result)}"

    @staticmethod
    def _format_record(rec) -> str:
        """Elk record met zijn EIGEN velden (title-achtig veld eerst), rauw maar leesbaar, gecapt."""
        if not isinstance(rec, dict):
            return str(rec)[:200]
        first = [k for k in ("title", "titel", "term", "query", "brand", "name", "word", "key") if k in rec]
        rest = [k for k in rec if k not in first and k not in ("source", "locale")]
        out = []
        for k in first + rest:
            v = rec.get(k)
            if v in (None, "", [], {}):
                continue
            if isinstance(v, str):
                v = (v[:160] + "…") if len(v) > 160 else v
            elif isinstance(v, (list, dict)):
                s = json.dumps(v, ensure_ascii=False)
                v = (s[:120] + "…") if len(s) > 120 else s
            out.append(f"{k}: {v}")
        return " | ".join(out[:8])

    @staticmethod
    def _format_metric(vals) -> str:
        if isinstance(vals, dict):
            return "; ".join(f"{k}={v}" for k, v in list(vals.items())[:12])
        if isinstance(vals, list):
            return "; ".join(str(x) for x in vals[:12])
        return str(vals)[:200]

    # --- het werk ---

    def _execute_skill(self, capability: str, payload: dict) -> tuple[bool, object]:
        """Voer een skill uit en geef (ok, resultaat) terug.

        Gedeelde kern voor handle() en use_skill(); valideert registry maar
        NIET DNA — dat doet de aanroeper.
        """
        skill = self.registry.get(capability)
        if skill is None:
            return False, f"skill '{capability}' niet geregistreerd"
        try:
            return True, skill.run(payload, self.context)
        except Exception as e:
            self.log.error("skill '%s' faalde: %s", capability, e)
            return False, str(e)

    def handle(self, task: Task) -> Response:
        if task.capability not in self.dna.skills:
            return Response(success=False, error=f"'{self.id}' heeft skill '{task.capability}' niet in zijn DNA")
        ok, result = self._execute_skill(task.capability, task.payload)
        if ok:
            return Response(success=True, data=result)
        return Response(success=False, error=result)

    def use_skill(self, capability: str, payload: dict) -> dict:
        """Zelf een eigen skill gebruiken (voor zelf-geinitieerd werk, niet via de matchmaker)."""
        if capability not in self.dna.skills:
            # Luid, niet stil: een DNA-miss is bijna altijd een dode feature
            # (de skill wordt aangeroepen maar nooit gegrant). Stil falen heeft
            # verband_voorstel en curate maandenlang onzichtbaar dood gehouden.
            self.log.warning(
                "⚠️ dode capability: '%s' roept skill '%s' aan, maar die zit niet "
                "in zijn DNA (%s). Grant via governance of verwijder de aanroep.",
                self.id, capability, self.dna.skills)
            return {"error": f"'{self.id}' heeft skill '{capability}' niet in zijn DNA"}
        ok, result = self._execute_skill(capability, payload)
        if ok:
            return result
        return {"error": result}

    def referenced_capabilities(self) -> set[str]:
        """Alle skills die deze rol via een use_skill-aanroep met letterlijke naam
        gebruikt, statisch afgeleid uit de broncode van de klasse-MRO. Basis voor
        de dode-skill-audit."""
        import inspect
        found: set[str] = set()
        for cls in type(self).__mro__:
            if cls.__module__ == "builtins" or cls is threading.Thread:
                continue
            try:
                src = inspect.getsource(cls)
            except (OSError, TypeError):
                continue
            found.update(re.findall(r'use_skill\(\s*["\']([^"\']+)["\']', src))
        return found

    def dormant_capabilities(self) -> set[str]:
        """Skills die de rol aanroept maar niet in zijn DNA heeft: dode features.
        Leeg = gezond. Niet-leeg = grant ontbreekt of de aanroep is dood."""
        return self.referenced_capabilities() - set(self.dna.skills)

    def tick(self) -> None:
        """Hartslag-hook: wordt elke cyclus aangeroepen. Default niets.
        Inwoners die zichzelf wakker maken (zoals TimeKeeper) overschrijven dit."""
        pass

    def react(self, event_name: str, handler, *, drop_if_busy: bool = False) -> None:
        """Abonneer op een event en laat het werk op de eigen thread draaien.
        De wrapper keert meteen terug; de handler draait asynchroon via de inbox.
        drop_if_busy=True: gooi het event weg als _busy=True (geen queue-opbouw)."""
        def _enqueue(event: Event) -> None:
            if drop_if_busy and getattr(self, "_busy", False):
                return
            self.inbox.enqueue(lambda e=event: handler(e))
        self.bus.subscribe(event_name, _enqueue)

    def run(self) -> None:
        self.log.info("ontwaakt [source=%s] | purpose=%s | skills=%s",
                      self.record.source, self.dna.purpose, self.dna.skills)
        dormant = self.dormant_capabilities()
        if dormant:
            self.log.warning(
                "⚠️ dode capabilities bij ontwaken: '%s' roept %s aan zonder grant. "
                "Grant via governance of verwijder de aanroep.",
                self.id, sorted(dormant))
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as e:
                self.log.error("tick faalde: %s", e)
            item = self.inbox.take(timeout=0.5)
            if item is None:
                continue
            if isinstance(item, Task):
                self.log.info("taak ontvangen: %s", item.capability)
                resp = self.handle(item)
                self.bus.publish(Event("task_completed", {
                    "task_id": item.id, "by": self.id, "capability": item.capability,
                    "success": resp.success, "data": resp.data, "error": resp.error,
                    "request_id": item.request_id}, self.id))
            else:  # event-job: callable die de handler met het event aanroept
                try:
                    item()
                except Exception as e:
                    self.log.error("event-handler faalde: %s", e)
            self.inbox.done()

    def reload(self, record: Record) -> None:
        """Governance gaf me een nieuw record (bv. extra accountability/skill)."""
        self.record = record
        self.dna = record.definition
        self.log.info("DNA herladen (v%s) | skills=%s", record.version, self.dna.skills)

    def stop(self) -> None:
        self._stop_event.set()


class Circle(Inhabitant):
    """Van buiten een rol, van binnen een dorp. Heeft geen handen: delegeert."""

    def __init__(self, record, bus, registry, context, inner_bus=None):
        super().__init__(record, bus, registry, context)
        self.inner_bus = inner_bus or EventBus(name=record.id)
        self.members: dict[str, Inhabitant] = {}

    def add_member(self, inhabitant: Inhabitant) -> None:
        self.members[inhabitant.id] = inhabitant

    def capabilities(self) -> list[str]:
        caps = set(self.dna.skills)
        for m in self.members.values():
            caps.update(m.capabilities())          # later: cureren via Lead Link
        return sorted(caps)

    def handle(self, task: Task) -> Response:
        for m in self.members.values():            # delegeren, niet zelf uitvoeren
            if task.capability in m.capabilities():
                m.deliver(task)
                return Response(success=True, data={"delegated_to": m.id})
        return Response(success=False, error=f"cirkel '{self.id}' heeft geen member voor '{task.capability}'")

    def start(self) -> None:
        for m in self.members.values():
            m.start()
        super().start()

    def stop(self) -> None:
        for m in self.members.values():
            m.stop()
        super().stop()
