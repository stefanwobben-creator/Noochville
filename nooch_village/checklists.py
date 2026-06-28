"""Checklists — een dashboard van terugkerende acties die om bevestiging vragen (✓ / ✗).

Holacracy: een checklist-item geeft transparantie over de huidige werkelijkheid (als een pre-flight
check); het voegt GEEN nieuwe verwachting toe (dat loopt via governance/roloverleg). Elk cirkellid
mag een item toevoegen voor een al terugkerende actie, ook voor een ander om op te rapporteren.

Een item hangt aan een node (cirkel of rol), heeft een cadans (dag/week/maand/kwartaal) en een doel
(alle cirkelleden of één specifieke rol). Per cadans-periode wordt één keer gerapporteerd (✓/✗);
het ontbreken van een rapport voor de huidige periode = 'nu te doen'. Opslag: data/checklists.json.
"""
from __future__ import annotations
import json
import os
import time
import uuid
from datetime import datetime, timezone

from nooch_village.util import atomic_write_json

CADENCES = ("dag", "week", "maand", "kwartaal")
CADENCE_LABEL = {"dag": "Dagelijks", "week": "Wekelijks", "maand": "Maandelijks",
                 "kwartaal": "Per kwartaal"}


def period_key(cadence: str, now: datetime | None = None) -> str:
    """De sleutel van de huidige periode voor een cadans. Lexicaal sorteerbaar per cadans."""
    now = now or datetime.now(timezone.utc)
    if cadence == "dag":
        return now.strftime("%Y-%m-%d")
    if cadence == "week":
        iso = now.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if cadence == "maand":
        return now.strftime("%Y-%m")
    if cadence == "kwartaal":
        return f"{now.year}-Q{(now.month - 1) // 3 + 1}"
    return now.strftime("%Y-%m-%d")


class ChecklistStore:
    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._items = d
            except Exception:
                self._items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, node: str, description: str, cadence: str, *, target_type: str = "all",
            target_id: str = "", by: str = "") -> dict | None:
        description = (description or "").strip()
        if not node or not description:
            return None
        if cadence not in CADENCES:
            cadence = "week"
        if target_type not in ("all", "role"):
            target_type = "all"
        cid = uuid.uuid4().hex[:12]
        item = {"id": cid, "node": node, "description": description[:200],
                "cadence": cadence, "target_type": target_type,
                "target_id": (target_id or "") if target_type == "role" else "",
                "by": by or "", "created_at": time.time(), "reports": {}}
        self._items[cid] = item
        self._save()
        return item

    def remove(self, cid: str) -> bool:
        if cid in self._items:
            del self._items[cid]
            self._save()
            return True
        return False

    def get(self, cid: str) -> dict | None:
        return self._items.get(cid)

    def for_node(self, node: str) -> list[dict]:
        order = {c: i for i, c in enumerate(CADENCES)}
        items = [i for i in self._items.values() if i.get("node") == node]
        return sorted(items, key=lambda i: (order.get(i.get("cadence"), 9), i.get("created_at", 0)))

    def report(self, cid: str, ok: bool, *, by: str = "", now: datetime | None = None) -> bool:
        """Rapporteer ✓/✗ voor de HUIDIGE periode van het item (idempotent per periode)."""
        it = self._items.get(cid)
        if it is None:
            return False
        pk = period_key(it.get("cadence", "week"), now)
        it.setdefault("reports", {})[pk] = {"ok": bool(ok), "at": time.time(), "by": by or ""}
        self._save()
        return True

    @staticmethod
    def current_period(item: dict, now: datetime | None = None) -> str:
        return period_key(item.get("cadence", "week"), now)

    @staticmethod
    def is_due(item: dict, now: datetime | None = None) -> bool:
        """Nu te doen = nog geen rapport voor de huidige periode."""
        return period_key(item.get("cadence", "week"), now) not in (item.get("reports") or {})

    @staticmethod
    def current_status(item: dict, now: datetime | None = None):
        """ok/✗ voor de huidige periode, of None als nog niet gerapporteerd."""
        rep = (item.get("reports") or {}).get(period_key(item.get("cadence", "week"), now))
        return None if rep is None else bool(rep.get("ok"))

    @staticmethod
    def history(item: dict, n: int = 6) -> list[bool]:
        """De laatste n gerapporteerde periodes (oud -> nieuw) als lijst van bool (✓=True)."""
        reps = item.get("reports") or {}
        keys = sorted(reps.keys())[-n:]
        return [bool(reps[k].get("ok")) for k in keys]
