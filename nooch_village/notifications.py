"""Notificaties — een rol of persoon weet dat er een @-mention voor hem/haar is.

Lichtgewicht store (data/notifications.json). Een notificatie heeft een doel (rol of persoon),
verwijst naar het project + de feed-entry, en draagt een snippet voor de weergave.
"""
from __future__ import annotations
import json
import os
import time
import uuid

from nooch_village.util import atomic_write_json


class NotifStore:
    def __init__(self, path: str):
        self.path = path
        self._items: list[dict] = []
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, list):
                    self._items = d
            except Exception:
                self._items = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, target_type: str, target_id: str, project_id: str, entry_id: str = "",
            by: str = "", snippet: str = "") -> dict:
        n = {
            "id": uuid.uuid4().hex[:10],
            "target_type": target_type, "target_id": target_id,
            "project_id": project_id, "entry_id": entry_id,
            "by": by, "snippet": (snippet or "")[:160],
            "at": time.time(), "read": False,
        }
        self._items.append(n)
        self._save()
        return n

    def for_targets(self, targets) -> list[dict]:
        """Notificaties voor een set (type, id)-doelen, nieuwste eerst."""
        s = {(t, i) for t, i in targets}
        out = [n for n in self._items if (n.get("target_type"), n.get("target_id")) in s]
        return sorted(out, key=lambda n: -(n.get("at") or 0))

    def unread_count(self, targets) -> int:
        return sum(1 for n in self.for_targets(targets) if not n.get("read"))

    def mark_read(self, targets) -> None:
        s = {(t, i) for t, i in targets}
        changed = False
        for n in self._items:
            if (n.get("target_type"), n.get("target_id")) in s and not n.get("read"):
                n["read"] = True; changed = True
        if changed:
            self._save()

    def all(self) -> list[dict]:
        return list(self._items)
