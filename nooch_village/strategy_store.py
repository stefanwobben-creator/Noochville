"""StrategyStore — per-cirkel strategie (operationele vertaling van de cirkel-purpose).

Eén dict in data/strategies.json, keyed by circle_id. De aanwezigheid van een entry betekent
dat de cirkel een strategie heeft — er is bewust GEEN `has_strategy`-veld op het governance-record
(dat zou bij elke records.save() gedropt worden; zie governance.py). Lezen is vrij; schrijven (set)
komt later achter de rechten-laag. Volgt het Library-patroon (one dict, atomic write).
"""
from __future__ import annotations
import json, os
from nooch_village.util import atomic_write_json


class StrategyStore:
    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            self._data = json.load(open(self.path))

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._data)

    def get(self, circle_id: str) -> dict | None:
        return self._data.get(circle_id)

    def has(self, circle_id: str) -> bool:
        return circle_id in self._data

    def set(self, circle_id: str, data: dict) -> None:
        self._data[circle_id] = data
        self._save()

    def all(self) -> dict:
        return self._data
