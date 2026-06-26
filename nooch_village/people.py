"""Mensen — de echte personen die rollen vervullen (GlassFrog 'Members'/'Role Fillers').

Een mens is iets anders dan een inwoner (Persona = AI-karakter). Een rol kan vervuld worden door
mensen én/of AI-inwoners (de hybride vorm). Mensen leven hier (data/people.json); wie welke rol
vervult staat in assignments.py (los van de governance-records: bemenst, niet geboren).
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, asdict

from nooch_village.util import atomic_write_json


@dataclass
class Person:
    """Een mens in de organisatie."""
    id: str
    name: str
    email: str = ""


class PeopleStore:
    """JSON-store voor mensen (data/people.json). Zelfde bestand-interface als de andere stores."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                self._items = json.load(open(path))
            except Exception:
                self._items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, name: str, email: str = "") -> Person:
        """Maak een mens. Dedup op (genormaliseerde) naam: bestaat die al, geef de bestaande terug."""
        name = (name or "").strip()
        if not name:
            raise ValueError("een mens heeft een naam nodig")
        existing = self.by_name(name)
        if existing is not None:
            return existing
        pid = uuid.uuid4().hex[:12]
        p = Person(id=pid, name=name[:80], email=(email or "").strip()[:120])
        self._items[pid] = asdict(p)
        self._save()
        return p

    def by_name(self, name: str) -> Person | None:
        nl = (name or "").strip().lower()
        for d in self._items.values():
            if d.get("name", "").strip().lower() == nl:
                return Person(**d)
        return None

    def get(self, pid: str | None) -> Person | None:
        if not pid:
            return None
        d = self._items.get(pid)
        return Person(**d) if d else None

    def all(self) -> list[Person]:
        return [Person(**d) for d in sorted(self._items.values(), key=lambda x: x.get("name", ""))]

    def update(self, pid: str, *, name: str | None = None, email: str | None = None) -> Person | None:
        d = self._items.get(pid)
        if d is None:
            return None
        if name is not None and name.strip():
            d["name"] = name.strip()[:80]
        if email is not None:
            d["email"] = email.strip()[:120]
        self._save()
        return Person(**d)

    def remove(self, pid: str) -> bool:
        if pid in self._items:
            del self._items[pid]
            self._save()
            return True
        return False
