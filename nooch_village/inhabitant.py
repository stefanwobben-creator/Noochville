from __future__ import annotations
import threading, logging, uuid, re, os, json, time
from nooch_village.event_bus import EventBus, Event
from nooch_village.inbox import Inbox
from nooch_village.models import Task, Response, Record, RecordType, Tension
from nooch_village.skills import SkillRegistry

# Trefwoorden die duiden op een structurele, terugkerende spanning die governance vereist
_STRUCTURAL_KW = frozenset([
    "voortaan", "altijd", "elke keer", "niemand bezit", "niemand heeft",
    "niemand pakt", "ontbreekt", "terugkerend", "structureel", "policy",
    "accountability", "nooit belegd", "verwacht wordt", "structuur",
    "verwacht dat", "zou moeten", "onbeheerd",
])


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
        """Classificeer en routeer een spanning. Eerste match wint.

        1. Structureel/terugkerend  → Proposal via proposal_raised (governance-engine)
        2. Eigen werk               → zelf doen (al in uitvoering)
        3. Andere rol               → routeer via help_requested of broadcast
        4. Geen passende rol        → tactisch proberen; matchmaker escaleert naar mens
        """
        desc = tension.description
        desc_l = desc.lower()
        cls = "onbekend"

        # Optionele LLM-classificatie (als er een sleutel is)
        llm = self._classify_llm(desc)

        if llm == "structural" or (llm is None and self._is_structural(desc_l)):
            cls = "structureel"
            self._raise_governance_proposal(tension)

        elif llm == "own" or (llm is None and self._fits_own_role(desc_l)):
            cls = "eigen-werk"
            self._do_own_work(tension)

        elif llm and llm not in ("tactical", "own", "structural"):
            # LLM gaf een rol-id terug
            role_id = llm
            records = getattr(self.context, "records", None)
            cap = None
            if records:
                rec = records.get(role_id)
                if rec and rec.definition.skills:
                    cap = rec.definition.skills[0]
            cls = f"andere-rol:{role_id}"
            self._route_to_role(tension, role_id, cap)

        else:
            role_id, cap = self._find_other_role(desc_l)
            if role_id:
                cls = f"andere-rol:{role_id}"
                self._route_to_role(tension, role_id, cap)
            else:
                cls = "tactisch"
                self._try_tactical_or_escalate(tension)

        self.bus.publish(Event("tension_triaged", {
            "by": self.id,
            "description": desc[:80],
            "classification": cls,
        }, self.id))

    # ── Triage-helpers ──────────────────────────────────────────────────────────

    def _is_structural(self, desc_l: str) -> bool:
        return any(kw in desc_l for kw in _STRUCTURAL_KW)

    def _fits_own_role(self, desc_l: str) -> bool:
        """True als een significant woord uit de spanning in mijn purpose/accountabilities voorkomt."""
        own = (self.dna.purpose + " " + " ".join(self.dna.accountabilities)).lower()
        for word in desc_l.split():
            if len(word) >= 6 and word in own:
                return True
        for word in own.split():
            if len(word) >= 6 and word in desc_l:
                return True
        return False

    def _find_other_role(self, desc_l: str) -> tuple[str | None, str | None]:
        """Zoek een andere rol wiens domeinen of accountabilities beter passen."""
        records = getattr(self.context, "records", None)
        if records is None:
            return None, None
        desc_words = {w for w in desc_l.split() if len(w) >= 6}
        for rec in records.all():
            if rec.id == self.id or rec.archived:
                continue
            # Domein-match heeft prioriteit (sterkste signaal)
            for domain in rec.definition.domains:
                if domain.lower() in desc_l:
                    cap = rec.definition.skills[0] if rec.definition.skills else None
                    return rec.id, cap
            # Accountability-overlap
            acc_text = " ".join(rec.definition.accountabilities).lower()
            acc_words = {w for w in acc_text.split() if len(w) >= 6}
            if acc_words & desc_words:
                cap = rec.definition.skills[0] if rec.definition.skills else None
                return rec.id, cap
        return None, None

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
        else:
            if is_reflection:
                # Extraheer de accountability-naam na het "accountability:"-marker
                idx      = desc_l.index(_ACC) + len(_ACC)
                acc_text = desc[idx:].strip()
                # Neem tot " — " of einde; trim tot 100 tekens
                acc_text = acc_text.split(" — ")[0].split("\n")[0].strip()[:100]
            else:
                acc_text = desc[:80]
            change = GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=self.id,
                                      add_accountabilities=[acc_text])

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
        force     : omzeil min_count voor structureel bekende, altijd-geldige limieten

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

        gap = state.setdefault(gap_key, {"count": 0, "first_seen": None, "last_seen": None})
        now = time.time()
        if gap["first_seen"] is None:
            gap["first_seen"] = now
        gap["last_seen"] = now
        gap["count"] += 1

        with open(path, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        if force or gap["count"] >= min_count:
            self.sense_tension(description, kind=kind)
            self.log.info("🔍 gat '%s' → spanning gesensed (observaties: %d)", gap_key, gap["count"])
            return True
        self.log.info("🔍 gat '%s' geregistreerd (%d/%d — nog geen spanning)", gap_key, gap["count"], min_count)
        return False

    # --- het werk ---
    def handle(self, task: Task) -> Response:
        if task.capability not in self.dna.skills:
            return Response(success=False, error=f"'{self.id}' heeft skill '{task.capability}' niet in zijn DNA")
        skill = self.registry.get(task.capability)
        if skill is None:
            return Response(success=False, error=f"skill '{task.capability}' niet geregistreerd")
        try:
            return Response(success=True, data=skill.run(task.payload, self.context))
        except Exception as e:
            self.log.error("skill '%s' faalde: %s", task.capability, e)
            return Response(success=False, error=str(e))

    def use_skill(self, capability: str, payload: dict) -> dict:
        """Zelf een eigen skill gebruiken (voor zelf-geinitieerd werk, niet via de matchmaker)."""
        if capability not in self.dna.skills:
            return {"error": f"'{self.id}' heeft skill '{capability}' niet in zijn DNA"}
        skill = self.registry.get(capability)
        if skill is None:
            return {"error": f"skill '{capability}' niet geregistreerd"}
        try:
            return skill.run(payload, self.context)
        except Exception as e:
            self.log.error("skill '%s' faalde: %s", capability, e)
            return {"error": str(e)}

    def tick(self) -> None:
        """Hartslag-hook: wordt elke cyclus aangeroepen. Default niets.
        Inwoners die zichzelf wakker maken (zoals TimeKeeper) overschrijven dit."""
        pass

    def react(self, event_name: str, handler) -> None:
        """Abonneer op een event en laat het werk op de eigen thread draaien.
        De wrapper keert meteen terug; de handler draait asynchroon via de inbox."""
        def _enqueue(event: Event) -> None:
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
