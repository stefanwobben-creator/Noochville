"""Mensen — de echte personen die rollen vervullen (GlassFrog 'Members'/'Role Fillers').

Een mens is iets anders dan een inwoner (Persona = AI-karakter). Een rol kan vervuld worden door
mensen én/of AI-inwoners (de hybride vorm). Mensen leven hier (data/people.json); wie welke rol
vervult staat in assignments.py (los van de governance-records: bemenst, niet geboren).

Auth-velden (password_hash, invited_at, last_login) zijn optioneel. Ontbreken ze in het JSON-
bestand, dan vult de dataclass-default in. people.json is de enige bron van waarheid: geen
aparte users.json meer.
"""
from __future__ import annotations
import os
import time
import uuid
from dataclasses import dataclass, asdict

from nooch_village.util import atomic_write_json, read_json


@dataclass
class Person:
    """Een mens in de organisatie."""
    id: str
    name: str
    email: str = ""
    password_hash: str = ""
    invited_at: float = 0.0
    last_login: float = 0.0
    must_change_password: bool = False   # True = op een admin-uitgegeven temp; wijzigen verplicht


class PeopleStore:
    """JSON-store voor mensen (data/people.json). Zelfde bestand-interface als de andere stores."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def _to_person(self, d: dict) -> Person:
        known = {f.name for f in Person.__dataclass_fields__.values()}
        return Person(**{k: v for k, v in d.items() if k in known})

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
                return self._to_person(d)
        return None

    def by_email(self, email: str) -> Person | None:
        el = (email or "").strip().lower()
        if not el:
            return None
        for d in self._items.values():
            if d.get("email", "").lower() == el:
                return self._to_person(d)
        return None

    def get(self, pid: str | None) -> Person | None:
        if not pid:
            return None
        d = self._items.get(pid)
        return self._to_person(d) if d else None

    def all(self) -> list[Person]:
        return [self._to_person(d) for d in sorted(self._items.values(), key=lambda x: x.get("name", ""))]

    def update(self, pid: str, *, name: str | None = None, email: str | None = None) -> Person | None:
        d = self._items.get(pid)
        if d is None:
            return None
        if name is not None and name.strip():
            d["name"] = name.strip()[:80]
        if email is not None:
            d["email"] = email.strip()[:120]
        self._save()
        return self._to_person(d)

    def set_password(self, pid: str, password_hash: str, invited_at: float | None = None,
                     must_change: bool = True) -> None:
        """Admin-weg: zet een (temp-)wachtwoord. Standaard `must_change=True` → de gebruiker moet het bij
        de eerstvolgende login zelf vervangen (dekt zowel toevoegen als resetten)."""
        d = self._items.get(pid)
        if d is not None:
            d["password_hash"] = password_hash
            d["invited_at"] = invited_at if invited_at is not None else time.time()
            d["must_change_password"] = must_change
            self._save()

    def set_own_password(self, pid: str, password_hash: str) -> None:
        """Self-service-weg: de gebruiker kiest zijn eigen wachtwoord → wis de 'moet wijzigen'-flag."""
        d = self._items.get(pid)
        if d is not None:
            d["password_hash"] = password_hash
            d["must_change_password"] = False
            self._save()

    def must_change(self, email: str) -> bool:
        """Moet deze gebruiker (op e-mail) eerst zijn wachtwoord wijzigen? Onbekend → False (fail-open op
        deze niet-beveiligingskritieke poort; de auth zelf blijft de echte grens)."""
        p = self.by_email(email)
        return bool(p and p.must_change_password)

    def backfill_must_change(self) -> int:
        """Idempotente migratie: markeer uitstaande, nog-nooit-door-de-gebruiker-gewijzigde temps
        (`invited_at >= last_login and invited_at > 0`). Wie z'n eigen wachtwoord al koos
        (`last_login > invited_at`) wordt niet geforceerd. Geeft het aantal gemarkeerde records terug."""
        n = 0
        for d in self._items.values():
            if not d.get("password_hash") or d.get("must_change_password"):
                continue
            inv, last = d.get("invited_at", 0.0), d.get("last_login", 0.0)
            if inv > 0 and inv >= last:
                d["must_change_password"] = True
                n += 1
        if n:
            self._save()
        return n

    def touch_login(self, email: str) -> None:
        el = (email or "").lower()
        for d in self._items.values():
            if d.get("email", "").lower() == el:
                d["last_login"] = time.time()
                self._save()
                return

    def remove(self, pid: str) -> bool:
        if pid in self._items:
            del self._items[pid]
            self._save()
            return True
        return False
