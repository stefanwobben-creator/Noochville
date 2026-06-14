from __future__ import annotations
from queue import Queue, Empty
from nooch_village.models import Task


class Inbox:
    """Eigen postbus per inwoner. Bewust een interface: de in-memory Queue
    is later vervangbaar door Redis/SQS zonder inwoner-logica aan te raken.

    Twee soorten werk-items:
    - Task  : toegewezen werk via de matchmaker (skill-dispatch).
    - object: event-job (callable) via react(), draait op de eigen thread.
    """

    def __init__(self, owner: str):
        self.owner = owner
        self._q: Queue[object] = Queue()

    def deliver(self, task: Task) -> None:
        self._q.put(task)

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
