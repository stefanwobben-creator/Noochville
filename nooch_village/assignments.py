"""Bezetting — wie vervult welke rol (GlassFrog 'Role Fillers').

Meervoudig én hybride: een rol kan door meerdere *fillers* vervuld worden, en een filler is een
mens (`person`) of een AI-inwoner (`persona`). Een mens kan meerdere rollen vervullen.

Dit is bewust een aparte laag náást de governance-records: een rol *bestaat* (geboren) via een
record; wie 'm *vervult* (bemenst) is operationeel en wijzigt vaak, zonder governance-wijziging.
`fillers_of` voegt legacy `Record.held_by` (mens) en `Record.persona_id` (AI) samen met de nieuwe
lijst, zodat bestaande data blijft werken.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass

from nooch_village.util import atomic_write_json

_VALID_TYPES = ("person", "persona")


@dataclass(frozen=True)
class Filler:
    """Een rolvervuller: een mens (person) of een AI-inwoner (persona)."""
    type: str   # "person" | "persona"
    id: str

    def as_dict(self) -> dict:
        return {"type": self.type, "id": self.id}


class Assignments:
    """Store: role_id -> lijst fillers. data/assignments.json."""

    def __init__(self, path: str):
        self.path = path
        self._by_role: dict[str, list[dict]] = {}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._by_role = {k: list(v) for k, v in d.items()}
            except Exception:
                self._by_role = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._by_role)

    def assign(self, role_id: str, filler_type: str, filler_id: str) -> bool:
        """Ken een filler toe aan een rol. Idempotent (dubbele bezetting telt één keer)."""
        if filler_type not in _VALID_TYPES or not role_id or not filler_id:
            return False
        lst = self._by_role.setdefault(role_id, [])
        ref = {"type": filler_type, "id": filler_id}
        if ref in lst:
            return True
        lst.append(ref)
        self._save()
        return True

    def unassign(self, role_id: str, filler_type: str, filler_id: str) -> bool:
        lst = self._by_role.get(role_id, [])
        ref = {"type": filler_type, "id": filler_id}
        if ref in lst:
            lst.remove(ref)
            if not lst:
                self._by_role.pop(role_id, None)
            self._save()
            return True
        return False

    def _stored(self, role_id: str) -> list[Filler]:
        return [Filler(r["type"], r["id"]) for r in self._by_role.get(role_id, [])
                if r.get("type") in _VALID_TYPES and r.get("id")]

    def fillers_of(self, role_id: str, record=None) -> list[Filler]:
        """Alle fillers van een rol: de toegewezen lijst, aangevuld met legacy `held_by` (mens) en
        `persona_id` (AI) van het record (indien meegegeven). Dedup, volgorde stabiel."""
        out: list[Filler] = list(self._stored(role_id))
        seen = {(f.type, f.id) for f in out}
        if record is not None:
            held = getattr(record, "held_by", None)
            if held and ("person", held) not in seen:
                out.append(Filler("person", held)); seen.add(("person", held))
            pid = getattr(record, "persona_id", None)
            if pid and ("persona", pid) not in seen:
                out.append(Filler("persona", pid)); seen.add(("persona", pid))
        return out

    def roles_of(self, filler_type: str, filler_id: str) -> list[str]:
        """Alle rollen die deze filler vervult (alleen de toegewezen laag)."""
        ref = {"type": filler_type, "id": filler_id}
        return [rid for rid, lst in self._by_role.items() if ref in lst]

    def all(self) -> dict[str, list[dict]]:
        return {k: list(v) for k, v in self._by_role.items()}
