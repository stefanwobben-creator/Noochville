from __future__ import annotations
import threading, logging, uuid, re, os, json, time
from nooch_village.util import atomic_write_json
from nooch_village.event_bus import EventBus, Event
from nooch_village.inbox import Inbox
from nooch_village.models import Task, Response, Record, RecordType, Tension
from nooch_village.skills import SkillRegistry
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
        handler(event.data.get("payload", {}))

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
        out = reason(prompt)
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
        prompt = (
            f"Je bent de rol '{self.id}' in NoochVille. Purpose: {dna.purpose}\n"
            f"Accountabilities: {', '.join(dna.accountabilities) or '-'}\n"
            f"Skills: {', '.join(dna.skills) or '-'}\n"
            f"Noordster: {ns_txt}. Actief doel: {goals}.\n{eerder_txt}\n"
            "Bedenk vanuit JOUW rol de ÉNE hoogst-renderende kans die ons dichter bij de noordster "
            "brengt: een project, een uitbreiding van je eigen rol, of een nieuwe rol.\n\n"
            "SCHRIJFREGELS (heel belangrijk):\n"
            "- Leg het idee uit alsof je het aan een 12-jarige vertelt. GEEN jargon, geen vakwoorden, "
            "geen afkortingen.\n"
            "- Wees CONCREET: wat gaan we precies doen, stap voor stap als dat helpt. Niet vaag.\n"
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
        out = reason(prompt)
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
        try:
            with open(path) as f:
                inbox = json.load(f)
        except Exception:
            return []
        out = []
        for item in inbox.values():
            ctx = item.get("context") or {}
            if (item.get("type") == "opportunity" and item.get("status") == "rejected"
                    and ctx.get("by") == self.id):
                out.append((item.get("subject", ""), item.get("resolution") or "afgewezen"))
        return out

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

    def _claim_run_complete(self, pid: str) -> None:
        """Start het project, voer het uit en markeer het als afgerond.
        Losgekoppeld van _on_project_queued zodat tests 'm direct kunnen aanroepen.
        """
        ledger = getattr(self.context, "projects", None)
        if ledger is None:
            self.log.warning("project '%s': geen ProjectLedger in context", pid)
            return
        project = ledger.get(pid)
        if project is None:
            self.log.warning("project '%s': niet gevonden", pid)
            return
        ledger.start(pid)
        self.log.info("▶ project '%s' gestart: %s", pid, str(project.get("scope", ""))[:60])
        outcome = self.run_project(project)
        current = ledger.get(pid)
        if current and current["status"] == "running":
            ledger.complete(pid, outcome)
            self.log.info("✅ project '%s' afgerond (outcome=%s)", pid, outcome)
        else:
            self.log.info("⏸ project '%s' niet afgerond door run_project (status=%s)",
                          pid, current and current["status"])

    def run_project(self, project: dict) -> str | None:
        """Overridebaar: voer het projectwerk uit. Geef een outcome-marker terug.
        Default-stub: logt de scope en geeft een vaste marker terug.
        """
        scope = str(project.get("scope", ""))[:60]
        self.log.info("🔨 project: '%s'", scope)
        return "stub:done"

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
