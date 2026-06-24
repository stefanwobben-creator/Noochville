"""SeedScheduler — spaced repetition voor zaadwoorden.

Vervangt het platte roterende venster: in plaats van iedereen even vaak, krijgen nieuwe en
productieve zaadwoorden voorrang en zakken uitgekauwde woorden naar een langer interval.

Werking (in 'runs', niet in dagen):
- Elke run: `tick()` zet de teller op.
- `select(seeds)` kiest de meest-achterstallige zaadwoorden (nieuw = nooit bevraagd = direct
  aan de beurt), tot het budget. Niets achterstallig → niets bevraagd (credits gespaard).
- Na het bevragen: `record(word, produced_new)`. Leverde het nieuwe termen op → interval terug
  naar 1 (blijf verkennen). Niks nieuws → interval verdubbelen (tot een plafond), zodat een
  saai woord met rust gelaten wordt maar af en toe nog herbekeken (trends verschuiven).

State in data/<naam>.json. Geen netwerk, volledig testbaar.
"""
from __future__ import annotations
import json
import os

from nooch_village.util import atomic_write_json


class SeedScheduler:
    def __init__(self, path: str, *, budget: int = 5, max_interval: int = 8):
        self.path = path
        self.budget = max(int(budget), 1)
        self.max_interval = max(int(max_interval), 1)
        self._state = {"counter": 0, "seeds": {}}   # seeds: {word: {"interval": int, "due": int}}
        if os.path.exists(path):
            try:
                loaded = json.load(open(path))
                self._state["counter"] = int(loaded.get("counter", 0))
                self._state["seeds"] = dict(loaded.get("seeds", {}))
            except Exception:
                pass

    @property
    def counter(self) -> int:
        return self._state["counter"]

    def tick(self) -> None:
        self._state["counter"] += 1

    def _due(self, word: str) -> int:
        return int(self._state["seeds"].get(word, {}).get("due", 0))

    def select(self, seeds: list[str]) -> list[str]:
        """Kies de meest-achterstallige zaadwoorden (nieuw eerst) tot het budget.
        Alleen woorden die 'due' zijn (due <= teller); nieuw = due 0 = altijd due."""
        now = self.counter
        due = [w for w in seeds if self._due(w) <= now]
        due.sort(key=self._due)                      # laagste due eerst = meest achterstallig/nieuw
        return due[:self.budget]

    def record(self, word: str, produced_new: bool) -> None:
        prev = int(self._state["seeds"].get(word, {}).get("interval", 1))
        interval = 1 if produced_new else min(prev * 2, self.max_interval)
        self._state["seeds"][word] = {"interval": interval, "due": self.counter + interval}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._state)
