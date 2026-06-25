"""Signaalwachtrij voor seed-oplevingen.

Een seed (volg-woord) dat een aanhoudende recente opleving toont is een spanning: het vraagt om
een verklaring. enrich_volumes schrijft de opleving hierheen; Harry (TijdgeestWachter) pakt 'm op
de puls op en grondt de term academisch. De cockpit toont het signaal apart via de evidence-vlag.
Dedup op term: eenmaal gesignaleerd blijft het staan tot Harry het onderzocht heeft."""
from __future__ import annotations
import json
import os
import time
from nooch_village.util import atomic_write_json


class SeedSurges:
    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                self._data = json.load(open(path))
            except Exception:
                self._data = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._data)

    def add(self, term: str, *, locale: str = "", pct: float | None = None,
            direction: str = "stijgend") -> bool:
        """Registreer een verschuiving (opleving of daling). True = nieuw toegevoegd. Bestaat de
        term al, dan blijft de status (geen her-onderzoek elke run)."""
        term = (term or "").strip()
        if not term or term in self._data:
            return False
        self._data[term] = {"term": term, "locale": locale, "pct": pct,
                            "direction": direction, "status": "new",
                            "detected": time.strftime("%Y-%m-%d")}
        self._save()
        return True

    def pending(self) -> list[dict]:
        return [v for v in self._data.values() if v.get("status") == "new"]

    def mark_investigated(self, term: str) -> None:
        e = self._data.get((term or "").strip())
        if e:
            e["status"] = "investigated"
            self._save()

    def set_explanation(self, term: str, explanation: dict) -> None:
        """Nieuws-duiding van de scout (titel/link/datum) bij een opleving bewaren."""
        e = self._data.get((term or "").strip())
        if e:
            e["explanation"] = explanation
            self._save()

    def all(self) -> dict:
        return dict(self._data)
