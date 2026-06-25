"""Per-merk laatste nieuwsfeit — gedeelde, leesbare store.

De ConcurrentScout schrijft hier het meest recente nieuwsitem per concurrent weg; de cockpit
leest het om bij elke gemonitorde concurrent de naam + laatste nieuwsfeit te tonen. Achter
dezelfde JSON-bestand-interface als de andere stores (schaal-naad: later DB/API)."""
from __future__ import annotations
import json
import os
from nooch_village.util import atomic_write_json


class CompetitorNews:
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

    def update(self, items: list[dict]) -> None:
        """Houd per merk het nieuwste item (op publicatiedatum) vast. Idempotent."""
        changed = False
        for it in items or []:
            brand = (it.get("brand") or "").strip()
            if not brand:
                continue
            date = it.get("date") or ""
            cur = self._data.get(brand)
            if cur is None or date >= (cur.get("date") or ""):
                self._data[brand] = {"title": it.get("title", ""),
                                     "link": it.get("link", ""), "date": date}
                changed = True
        if changed:
            self._save()

    def all(self) -> dict:
        return dict(self._data)

    def latest(self, brand: str) -> dict | None:
        return self._data.get(brand)
