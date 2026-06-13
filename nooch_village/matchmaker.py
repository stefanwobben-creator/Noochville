from __future__ import annotations
import logging
from nooch_village.event_bus import EventBus, Event
from nooch_village.models import Task

log = logging.getLogger("village.matchmaker")


class Matchmaker:
    """Hoort 'wie kan dit?' en legt het werk in de inbox van een capabele inwoner."""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.by_cap: dict[str, list] = {}
        bus.subscribe("help_requested", self._route)

    def register(self, inhabitant) -> None:
        for cap in inhabitant.capabilities():
            lst = self.by_cap.setdefault(cap, [])
            if inhabitant not in lst:
                lst.append(inhabitant)

    def _route(self, e: Event) -> None:
        cap = e.data["capability"]
        candidates = self.by_cap.get(cap, [])
        if not candidates:
            log.warning("geen inwoner voor capability '%s'", cap)
            self.bus.publish(Event("human_intervention_needed", {
                "capability": cap,
                "request_id": e.data.get("request_id"),
                "payload": e.data.get("payload", {}),
                "reason": "geen capabele rol gevonden in het dorp",
            }, "Matchmaker"))
            return
        chosen = min(candidates, key=lambda i: i.inbox.pending())   # simpele load-balancing
        chosen.deliver(Task(capability=cap, payload=e.data.get("payload", {}),
                            request_id=e.data.get("request_id"), addressee=chosen.id))
        log.info("routeer '%s' -> %s", cap, chosen.id)
