from __future__ import annotations
import threading, logging, uuid
from nooch_village.event_bus import EventBus, Event
from nooch_village.inbox import Inbox
from nooch_village.models import Task, Response, Record, RecordType
from nooch_village.skills import SkillRegistry


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
        self.bus.publish(Event("tension_sensed",
            {"by": self.id, "description": description, "kind": kind}, self.id))

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
        self.log.info("ontwaakt | purpose=%s | skills=%s", self.dna.purpose, self.dna.skills)
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
