"""Koppelingen op een accountability van een rol — autonome AI-taken én dorpsmiddelen.

Twee soorten koppeling, één store (`data/ai_tasks.json`), onderscheiden door `kind`:

- `kind="autonoom"` (de bestaande AI-taak): "deze AI doet dit zelfstandig binnen die
  accountability". Hybride (AI helpt de mens) is de basislijn en markeren we niet; het bestaan
  van een autonome koppeling betekent 'autonoom'. De mens blijft verantwoordelijk.
- `kind="middel"` (de skill-link): "dit dorpsmiddel is beschikbaar voor die belofte". Een
  registry-capability, gelegd door de Circle Lead, per direct omkeerbaar.

Een koppeling hangt aan (`role`, `acc_id`) — het STABIELE id van de accountability, niet aan
zijn positie. Zie acc_ids.py: indices verschuiven bij elke governance-ronde, ids niet.
"""
from __future__ import annotations
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict, field

from nooch_village.util import atomic_write_json, read_json

log = logging.getLogger("village.ai_tasks")

KIND_AUTONOOM = "autonoom"
KIND_MIDDEL = "middel"


@dataclass
class AITask:
    id: str
    role: str            # rol-id
    acc_id: str          # stabiel id van de accountability binnen de rol
    agent: str           # persona-id (AI-inwoner) — leeg bij kind="middel"
    wat: str             # korte omschrijving van wat de AI zelfstandig doet
    kind: str = KIND_AUTONOOM        # "autonoom" | "middel"
    skill: str = ""                  # registry-capability — alleen bij kind="middel"
    gelegd_door: str = ""            # wie de koppeling legde (e-mail/persoon-id)
    gelegd_op: float = field(default_factory=time.time)

    @classmethod
    def from_dict(cls, d: dict) -> "AITask":
        """Fail-soft lezen: oude records (zonder kind/skill/acc_id) blijven werken."""
        return cls(
            id=d.get("id", ""),
            role=d.get("role", ""),
            acc_id=str(d.get("acc_id") or ""),
            agent=d.get("agent", ""),
            wat=d.get("wat", ""),
            kind=d.get("kind") or KIND_AUTONOOM,
            skill=d.get("skill", "") or "",
            gelegd_door=d.get("gelegd_door", "") or "",
            gelegd_op=float(d.get("gelegd_op") or 0.0),
        )


class AITaskStore:
    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    # ── Schrijven ────────────────────────────────────────────────────────────

    def add(self, role: str, acc_id: str, agent: str, wat: str,
            gelegd_door: str = "") -> AITask | None:
        """Koppel een autonome AI-taak aan een accountability."""
        if not role or not agent or not acc_id:
            return None
        return self._put(AITask(id=uuid.uuid4().hex[:12], role=role, acc_id=str(acc_id),
                                agent=agent, wat=(wat or "").strip()[:200],
                                kind=KIND_AUTONOOM, gelegd_door=gelegd_door))

    def add_link(self, role: str, acc_id: str, skill: str, wat: str = "",
                 gelegd_door: str = "") -> AITask | None:
        """Koppel een dorpsmiddel (registry-capability) aan een accountability.

        De aanroeper is verantwoordelijk voor de autorisatie (Circle Lead) én voor de
        domeinpoort — deze store weigert alleen het structureel ongeldige.
        """
        if not role or not skill or not acc_id:
            return None
        # Idempotent: hetzelfde middel op dezelfde belofte is één koppeling.
        for t in self.for_acc(role, acc_id):
            if t.kind == KIND_MIDDEL and t.skill == skill:
                return t
        return self._put(AITask(id=uuid.uuid4().hex[:12], role=role, acc_id=str(acc_id),
                                agent="", wat=(wat or "").strip()[:200],
                                kind=KIND_MIDDEL, skill=skill, gelegd_door=gelegd_door))

    def _put(self, t: AITask) -> AITask:
        self._items[t.id] = asdict(t)
        self._save()
        return t

    def remove(self, tid: str) -> bool:
        if tid in self._items:
            del self._items[tid]
            self._save()
            return True
        return False

    # ── Lezen ────────────────────────────────────────────────────────────────

    def for_acc(self, role: str, acc_id: str) -> list[AITask]:
        return [AITask.from_dict(d) for d in self._items.values()
                if d.get("role") == role and str(d.get("acc_id") or "") == str(acc_id)]

    def for_role(self, role: str) -> list[AITask]:
        return sorted((AITask.from_dict(d) for d in self._items.values()
                       if d.get("role") == role), key=lambda t: (t.kind, t.acc_id))

    def for_roles(self, role_ids) -> list[AITask]:
        s = set(role_ids)
        return [AITask.from_dict(d) for d in self._items.values() if d.get("role") in s]

    def all(self) -> list[AITask]:
        return [AITask.from_dict(d) for d in self._items.values()]

    def links_for_role(self, role: str) -> list[AITask]:
        """Alleen de middel-koppelingen van deze rol."""
        return [t for t in self.for_role(role) if t.kind == KIND_MIDDEL]

    # ── Migratie ─────────────────────────────────────────────────────────────

    def migrate_acc_ids(self, records) -> int:
        """Zet bestaande `acc_index`-koppelingen om naar het stabiele `acc_id`.

        Fail-soft en idempotent: een taak die al een acc_id heeft blijft ongemoeid; een taak
        waarvan de rol of de index niet (meer) bestaat wordt niet stilzwijgend verplaatst maar
        blijft staan met een lege acc_id — zichtbaar kapot is beter dan onzichtbaar verkeerd.
        Geeft het aantal gemigreerde taken terug.
        """
        from nooch_village.acc_ids import acc_id_at

        n = 0
        for tid, d in list(self._items.items()):
            if d.get("acc_id"):
                continue
            if "acc_index" not in d:
                continue
            rec = records.get(d.get("role")) if records is not None else None
            if rec is None:
                log.warning("ai_tasks: taak %s verwijst naar onbekende rol '%s'", tid, d.get("role"))
                continue
            try:
                idx = int(d.get("acc_index", -1))
            except (TypeError, ValueError):
                idx = -1
            new_id = acc_id_at(rec.definition, idx) if idx >= 0 else ""
            if not new_id:
                log.warning("ai_tasks: taak %s had index %s die niet meer bestaat in '%s'",
                            tid, idx, d.get("role"))
                continue
            d["acc_id"] = new_id
            d.pop("acc_index", None)
            d.setdefault("kind", KIND_AUTONOOM)
            n += 1
        if n:
            self._save()
            log.info("ai_tasks: %d koppeling(en) van index naar stabiel acc_id gemigreerd", n)
        return n
