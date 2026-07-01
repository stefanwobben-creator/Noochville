"""Autonome AI-taken — wat een AI-agent zelfstandig doet binnen een accountability van een rol.

Hybride (AI helpt de mens) is de basislijn en markeren we niet. We leggen alléén vast wat een
AI-agent autonoom uitvoert (bijv. 'stelt conceptteksten op'); de mens blijft verantwoordelijk en
publiceert/keurt goed. Opslag: data/ai_tasks.json.

Een taak hangt aan (role_id, acc_index): de positie van de accountability in de rol. Geen mode-veld:
het bestaan van de taak betekent 'autonoom'.
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, asdict

from nooch_village.util import atomic_write_json, read_json


@dataclass
class AITask:
    id: str
    role: str            # rol-id
    acc_index: int       # index van de accountability binnen de rol
    agent: str           # persona-id (AI-inwoner)
    wat: str             # korte omschrijving van wat de AI zelfstandig doet


class AITaskStore:
    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, role: str, acc_index: int, agent: str, wat: str) -> AITask | None:
        if not role or not agent:
            return None
        tid = uuid.uuid4().hex[:12]
        t = AITask(id=tid, role=role, acc_index=int(acc_index), agent=agent,
                   wat=(wat or "").strip()[:200])
        self._items[tid] = asdict(t)
        self._save()
        return t

    def remove(self, tid: str) -> bool:
        if tid in self._items:
            del self._items[tid]
            self._save()
            return True
        return False

    def for_acc(self, role: str, acc_index: int) -> list[AITask]:
        return [AITask(**d) for d in self._items.values()
                if d.get("role") == role and int(d.get("acc_index", -1)) == int(acc_index)]

    def for_role(self, role: str) -> list[AITask]:
        return sorted((AITask(**d) for d in self._items.values() if d.get("role") == role),
                      key=lambda t: t.acc_index)

    def for_roles(self, role_ids) -> list[AITask]:
        s = set(role_ids)
        return [AITask(**d) for d in self._items.values() if d.get("role") in s]

    def all(self) -> list[AITask]:
        return [AITask(**d) for d in self._items.values()]
