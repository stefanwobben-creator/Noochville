"""MonitoringStore — per-rol operationeel overzicht van gemonitorde metrics.

Opslag: data/role_metrics.json, keyed op role_id -> gesorteerde lijst metric-namen.
Beheerd door de rol zelf. Niet in het governance-record.
"""
from __future__ import annotations
import os
from nooch_village.util import atomic_write_json, read_json


class MonitoringStore:

    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        self._data = read_json(self.path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._data)

    def add_metrics(self, role_id: str, metrics: list[str]) -> list[str]:
        """Voeg metrics toe (dedup, gesorteerd). Geeft de bijgewerkte lijst terug."""
        current = set(self._data.get(role_id, []))
        current.update(metrics)
        self._data[role_id] = sorted(current)
        self._save()
        return self._data[role_id]

    def get_metrics(self, role_id: str) -> list[str]:
        return list(self._data.get(role_id, []))
