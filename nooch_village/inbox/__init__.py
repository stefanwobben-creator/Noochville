from __future__ import annotations
from queue import Queue, Empty


class Inbox:
    """Eigen postbus per inwoner. Bewust een interface: de in-memory Queue
    is later vervangbaar door Redis/SQS zonder inwoner-logica aan te raken.

    ÉÉN soort werk-item: de event-job (een callable) die `react()` erin legt en die op de eigen
    thread van de inwoner draait. Er was een tweede — `Task`, toegewezen werk van de Matchmaker —
    en die is op 20 september 2026 met de triage-keten opgeheven. De postbus zelf blijft: hij draagt
    harde regel 9, en dat is de discipline die geneste cirkels later mogelijk houdt.
    """

    def __init__(self, owner: str):
        self.owner = owner
        self._q: Queue[object] = Queue()

    def enqueue(self, item: object) -> None:
        """Legt een event-job (of ander werk-item) in de inbox."""
        self._q.put(item)

    def take(self, timeout: float = 1.0) -> object | None:
        try:
            return self._q.get(timeout=timeout)
        except Empty:
            return None

    def done(self) -> None:
        self._q.task_done()

    def pending(self) -> int:
        return self._q.qsize()
