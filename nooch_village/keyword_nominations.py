"""Keyword-nominaties (IA-fase 4) — het instrument, nog geen sturing.

Iedereen mag een keyword NOMINEREN; alleen Lara (de Library-rolvervuller) SCHRIJFT naar de
beschermde woordenschat (`Library.curate`). Elke beslissing wordt append-only geborgd in de
Kroniek (`data/keyword_nominaties.jsonl`): welke rol, welk woord, accept/reject, met welke reden.
Een afwijzing dwingt een echte reden af (leeg/"n.v.t." wordt geweigerd).

Twee onderdelen:
- `NominationQueue`  — de pending-wachtrij (lock-veilig, JsonStore).
- `NominationKroniek` — de append-only beslissingsgeschiedenis (jsonl, flock zoals de EvidenceLedger).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime

from nooch_village.util import JsonStore, file_lock

# Een afwijzing zonder echte reden is geen borging. Fail-closed op lege/nietszeggende redenen.
_BAD_REASONS = {"", "n.v.t.", "nvt", "n.v.t", "-", "—", "geen", "geen reden"}


def valid_reason(reason: str | None) -> bool:
    return (reason or "").strip().lower() not in _BAD_REASONS


class NominationQueue(JsonStore):
    """Pending keyword-nominaties, gededupliceerd op de term (kleine letter)."""
    _STATE = "_items"
    _default = dict
    _EXPECT = dict
    _WRITE_METHODS = ("nominate", "remove")

    def nominate(self, term: str, by: str) -> bool:
        term = (term or "").strip()
        if not term:
            return False
        key = term.lower()
        if key in self._items:                      # al in de wachtrij → geen dubbele nominatie
            return False
        self._items[key] = {"term": term, "by": by or "onbekend",
                            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M")}
        self._save()
        return True

    def remove(self, term: str) -> bool:
        key = (term or "").strip().lower()
        if key in self._items:
            del self._items[key]
            self._save()
            return True
        return False

    # ── lezen (lock-vrij) ──
    def pending(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda r: r.get("created_at") or "")

    def has(self, term: str) -> bool:
        return (term or "").strip().lower() in self._items


class NominationKroniek:
    """Append-only Kroniek van nominatie-beslissingen. Eén regel per beslissing."""

    def __init__(self, path: str):
        self.path = path

    def record(self, *, role_id: str, term: str, decision: str, reason: str,
               ts: float | None = None) -> dict:
        if decision not in ("accept", "reject"):
            raise ValueError(f"ongeldige decision {decision!r} — verwacht 'accept' of 'reject'")
        row = {
            "id": uuid.uuid4().hex[:12],
            "role_id": role_id,
            "term": term,
            "decision": decision,
            "reason": reason or "",
            "ts": ts if ts is not None else time.time(),
        }
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        with file_lock(self.path):                  # procesbrede flock → veilige append naast de daemon
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        return row

    # ── lezen (lock-vrij) ──
    def all_records(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out
