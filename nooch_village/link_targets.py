"""Store voor linkbuilding-doelwitten: gidsen/lijstjes waar Nooch in vermeld wil worden.

Zelfde mens-gated gedachte als de merkenstore: de radar stelt doelwitten voor, de mens
bepaalt of een gids het pitchen waard is. Gekeyd op de artikel-link (uniek).

  candidates : {link: {title, source, priority, first_seen}}  — wacht op jouw oordeel
  pursued    : {link: {...}}                                   — ga je pitchen
  ignored    : {link: {...}}                                   — niks voor Nooch
"""
from __future__ import annotations
import json
import os

from nooch_village.util import atomic_write_json

_PRIO_ORDER = {"hoog": 0, "midden": 1, "onbekend": 2, "laag": 3}


class LinkTargets:
    def __init__(self, path: str):
        self.path = path
        self._data = {"candidates": {}, "pursued": {}, "ignored": {}}
        if os.path.exists(path):
            try:
                loaded = json.load(open(path))
                self._data.update({k: loaded.get(k, self._data[k]) for k in self._data})
            except Exception:
                pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._data)

    def status(self, link: str) -> str | None:
        for name in ("candidates", "pursued", "ignored"):
            if link in self._data[name]:
                return {"candidates": "candidate", "pursued": "pursued",
                        "ignored": "ignored"}[name]
        return None

    def add_candidate(self, link: str, title: str = "", source: str = "",
                      priority: str = "onbekend") -> bool:
        link = (link or "").strip()
        if not link or self.status(link) is not None:
            return False
        from datetime import date
        self._data["candidates"][link] = {
            "title": title, "source": source, "priority": priority,
            "first_seen": date.today().isoformat()}
        self._save()
        return True

    def _move(self, link: str, dest: str) -> bool:
        meta = None
        for name in ("candidates", "pursued", "ignored"):
            if link in self._data[name]:
                meta = self._data[name].pop(link)
                break
        if meta is None:
            return False
        self._data[dest][link] = meta
        self._save()
        return True

    def pursue(self, link: str) -> bool:
        return self._move(link, "pursued")

    def ignore(self, link: str) -> bool:
        return self._move(link, "ignored")

    def candidates(self) -> list[dict]:
        rows = [{"link": k, **v} for k, v in self._data["candidates"].items()]
        return sorted(rows, key=lambda r: _PRIO_ORDER.get(r.get("priority"), 9))

    def pursued(self) -> list[dict]:
        return [{"link": k, **v} for k, v in self._data["pursued"].items()]
