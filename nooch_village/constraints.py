"""Huis-regels / constraints — de feiten en eisen die het dorp altijd moet respecteren.

Ontstaan uit triage: als de mens een kans afwijst met een reden en die als constraint markeert
("bio-afbreekbaar is een producteis", "we bieden geen kinderschoenen", "klein assortiment"), dan
wordt die reden een vaste regel. De opportunity-reflex leest ze en stelt niets meer voor dat
ertegen botst. Zo maakt jouw oordeel het dorp slimmer. JSON-bestand achter een simpele interface."""
from __future__ import annotations
import os
import time
from nooch_village.util import atomic_write_json, read_json


class Constraints:
    def __init__(self, path: str):
        self.path = path
        self._items: list[dict] = read_json(path, [], expect=list)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, text: str, *, by: str = "human", source: str = "") -> bool:
        """Voeg een huis-regel toe. Dedup op tekst (case-insensitief). True = nieuw."""
        text = (text or "").strip()
        if not text or any(c["text"].lower() == text.lower() for c in self._items):
            return False
        self._items.append({"text": text, "by": by, "source": source,
                            "date": time.strftime("%Y-%m-%d")})
        self._save()
        return True

    def all(self) -> list[dict]:
        return list(self._items)

    def texts(self) -> list[str]:
        return [c["text"] for c in self._items]
