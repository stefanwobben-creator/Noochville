from __future__ import annotations
import threading, logging, time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("village.bus")


@dataclass
class Event:
    name: str
    data: dict
    sender: str
    at: float = field(default_factory=time.time)


class EventBus:
    """Het marktplein. ALTIJD injecteren, nooit als global singleton gebruiken:
    dat is de enige discipline die geneste cirkels later mogelijk houdt."""

    def __init__(self, name: str = "root"):
        self.name = name
        self._subs: dict[str, list[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_name: str, cb: Callable[[Event], None]) -> None:
        with self._lock:
            self._subs.setdefault(event_name, []).append(cb)

    def publish(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._subs.get(event.name, []))
        for cb in handlers:
            try:
                cb(event)
            except Exception as e:        # één kapotte luisteraar legt het plein niet plat
                log.error("luisteraar faalde op '%s': %s", event.name, e)
