from __future__ import annotations
import json, os
from datetime import datetime
from nooch_village.util import atomic_write_json


class Library:
    """De woordenschat-bibliotheek: een DOMEIN dat de Librarian beheert.
    Lezen is vrij voor iedereen; cureren (schrijven) is voorbehouden aan de Librarian.
    Een entry draagt niet alleen een oordeel maar ook het WAAROM (het is een ontologie,
    geen blocklist)."""

    def __init__(self, path: str):
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            self._data = json.load(open(self.path))

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._data)

    # --- lezen (vrij) ---
    def status(self, word: str) -> dict | None:
        return self._data.get(word.lower())

    def is_forbidden(self, word: str) -> bool:
        e = self.status(word)
        return bool(e and e["status"] in ("forbidden", "avoid"))

    def is_approved(self, word: str) -> bool:
        e = self.status(word)
        return bool(e and e["status"] == "approved")

    def all(self) -> dict:
        return self._data

    # --- cureren (alleen de Librarian hoort dit aan te roepen) ---
    def curate(self, word: str, status: str, rationale: str = "",
               evidence: dict | None = None, by: str = "Librarian") -> dict:
        entry = {
            "status": status,                 # approved | forbidden | avoid | escalated
            "rationale": rationale,
            "evidence": evidence or {},
            "by": by,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        self._data[word.lower()] = entry
        self._save()
        return entry
