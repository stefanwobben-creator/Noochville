"""Werkoverleg (tactical meeting) — de operationele bijeenkomst van een cirkel.

Vaste volgorde: check-in, checklist, metrics, projecten, agenda (spanningen), check-out, sluiten.
Alleen de secretaris opent en sluit. De inhoud per stap hergebruikt de BESTAANDE schermen
(members, checklists, metrics, projecten); er is geen tweede versie.

Deze store houdt alleen de overleg-staat bij (status, tijd, aanwezigheid, agenda, check-out,
samenvatting). De rest leeft in de bestaande stores. Opslag: data/werkoverleg.json.
"""
from __future__ import annotations
import json
import os
import time

from nooch_village.util import atomic_write_json

STEPS = [("checkin", "Check-in"), ("checklist", "Checklist"), ("metrics", "Metrics"),
         ("projecten", "Projecten"), ("agenda", "Agenda"), ("checkout", "Check-out"),
         ("sluiten", "Sluiten")]


class WerkoverlegStore:
    def __init__(self, path: str):
        self.path = path
        self._m: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._m = d
            except Exception:
                self._m = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._m)

    def get(self, circle: str) -> dict | None:
        return self._m.get(circle)

    def is_open(self, circle: str) -> bool:
        return (self._m.get(circle) or {}).get("status") == "open"

    def open(self, circle: str) -> dict:
        """Start een overleg (idempotent zolang het open is)."""
        st = self._m.get(circle)
        if not st or st.get("status") != "open":
            st = {"status": "open", "started_at": time.time(), "ended_at": None,
                  "presence": {}, "agenda": [], "checkout": {}}
            self._m[circle] = st
            self._save()
        return st

    def close(self, circle: str) -> dict | None:
        st = self._m.get(circle)
        if not st or st.get("status") != "open":
            return None
        st["status"] = "closed"
        st["ended_at"] = time.time()
        self._save()
        return st

    def duration_min(self, circle: str) -> int:
        st = self._m.get(circle) or {}
        start, end = st.get("started_at"), st.get("ended_at") or time.time()
        return int((end - start) / 60) if start else 0
