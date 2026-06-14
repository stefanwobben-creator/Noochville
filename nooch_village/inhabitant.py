from __future__ import annotations
import threading, logging, uuid, re, os, json, time
from nooch_village.util import atomic_write_json
from nooch_village.event_bus import EventBus, Event
from nooch_village.inbox import Inbox
from nooch_village.models import Task, Response, Record, RecordType, Tension
from nooch_village.skills import SkillRegistry
from nooch_village.triage_engine import TriageContext, classify as _triage_classify


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
        self._stop = threading.Event()
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

    def sense_tension(self, description: str, kind: str = "operational") -> None:
        """Sens een spanning: logt naar het audittrail én triageert voor dispatch."""
        tension = Tension(sensed_by=self.id, description=description, kind=kind)
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
            # Roster-match oordeelsstap: beslist ADD_ROLE of AMEND_ROLE
            from nooch_village.roster_match import roster_match
            records = getattr(self.context, "records", None)
            r_kind, r_id, r_purpose = roster_match(desc, self.id, records)
            if r_kind == ChangeKind.ADD_ROLE:
                change = GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id=r_id,
                                          purpose=r_purpose, new_role_parent="noochville")
            else:
                change = GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=self.id,
                                          add_accountabilities=[desc[:80]])

        if change.kind == ChangeKind.ADD_ROLE and not is_reflection:
            rationale = (
                "Structureel terugkerend gat: geen bestaande rol dekt deze "
                "accountability voldoende (roster-match onder drempel)."
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
            trigger_example=f"{self.id}:{desc[:80]}",
            rationale=rationale,
        )
        self.bus.publish(Event("proposal_raised",
                               {"proposal": proposal_to_dict(proposal)}, self.id))
        self.log.info("🏛️ structureel → voorstel %s (%s)", proposal.id, change.kind.value)

    def _report_means_gap(self, gap_key: str, description: str) -> None:
        """Routeer een structurele capaciteitsgrens direct naar de inbox als means-gap-item.

        Gaat NIET door de governance-gate: geen amend_role, geen voorstel, geen churn.
        De inbox dedupt op gap_key zodat het hooguit één keer verschijnt.
        """
        self.bus.publish(Event("means_gap_sensed", {
            "gap_key":     gap_key,
            "description": description,
            "by":          self.id,
        }, self.id))

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
            self.sense_tension(description, kind=kind)
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
            return {"error": f"'{self.id}' heeft skill '{capability}' niet in zijn DNA"}
        ok, result = self._execute_skill(capability, payload)
        if ok:
            return result
        return {"error": result}

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
        while not self._stop.is_set():
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
        self._stop.set()


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
