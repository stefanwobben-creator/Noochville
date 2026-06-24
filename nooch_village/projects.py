"""ProjectLedger — de proces-store: volgt de status van lopend en gepland werk.

Opslag: data/projects.json (atomic write). Elke entry is een project-record:
  id, owner, scope, trigger, status, blocked_on, created_at, updated_at, outcome.
Governance-records en human_inbox blijven ongemoeid.
"""
from __future__ import annotations
import json, os, time, uuid
from nooch_village.util import atomic_write_json

_VALID_TRIGGERS = {"clock", "human", "noochie", "tension"}
_TERMINAL       = {"done"}


class ProjectLedger:

    def __init__(self, path: str):
        self.path = path
        self._projects: dict[str, dict] = {}
        self._mtime: float = 0.0
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                self._projects = json.load(open(self.path))
                self._mtime = os.path.getmtime(self.path)
            except Exception:
                self._projects = {}

    def _maybe_reload(self) -> None:
        """Herlaad van schijf als het bestand door een extern proces is gewijzigd."""
        try:
            if os.path.exists(self.path) and os.path.getmtime(self.path) > self._mtime:
                self._load()
        except Exception:
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._projects)

    def _touch(self, project: dict) -> None:
        project["updated_at"] = time.time()

    # ── schrijven ──────────────────────────────────────────────────────────────

    def create(self, owner: str, scope, trigger: str) -> str:
        if trigger not in _VALID_TRIGGERS:
            raise ValueError(f"ongeldig trigger: '{trigger}'")
        pid = uuid.uuid4().hex[:12]
        now = time.time()
        self._projects[pid] = {
            "id":         pid,
            "owner":      owner,
            "scope":      scope,
            "trigger":    trigger,
            "status":     "queued",
            "blocked_on": None,
            "created_at": now,
            "updated_at": now,
            "outcome":    None,
        }
        self._save()
        return pid

    def start(self, pid: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "running"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    def block(self, pid: str, on_role: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "blocked"
        p["blocked_on"] = on_role
        self._touch(p)
        self._save()
        return True

    def unblock(self, pid: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "running"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    def complete(self, pid: str, outcome: str | None = None) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "done"
        p["outcome"] = outcome
        self._touch(p)
        self._save()
        return True

    def edit(self, pid: str, scope=None, owner: str | None = None) -> bool:
        """Bewerk de inhoud van een project (scope en/of owner). Status blijft ongemoeid;
        done-projecten zijn vergrendeld. Lege waarden worden genegeerd. Geeft True bij succes."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        if scope is not None and str(scope).strip():
            p["scope"] = scope
        if owner is not None and str(owner).strip():
            p["owner"] = owner
        self._touch(p)
        self._save()
        return True

    def to_future(self, pid: str) -> bool:
        """Park een project als 'future' (later oppakken als er ruimte is). Niet-terminaal:
        het kan later weer naar running/blocked. Done-projecten blijven done."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "future"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    # ── lezen ──────────────────────────────────────────────────────────────────

    def get(self, pid: str) -> dict | None:
        self._maybe_reload()
        return self._projects.get(pid)

    def all(self) -> list[dict]:
        self._maybe_reload()
        return list(self._projects.values())

    def by_status(self, status: str) -> list[dict]:
        self._maybe_reload()
        return [p for p in self._projects.values() if p["status"] == status]

    def open(self) -> list[dict]:
        self._maybe_reload()
        return [p for p in self._projects.values() if p["status"] not in _TERMINAL]
