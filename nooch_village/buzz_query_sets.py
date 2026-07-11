"""Configureerbare zoek-sets voor community_listening (Billy Buzz).

Een set bundelt de queries + subreddits die de community-luister-skill afzoekt. Zo is de
onderwerp-keuze data, geen code: een nieuwe set toevoegen is een record, geen deploy.

Achter de JsonStore-basis: elke schrijf neemt het gedeelde bestandsslot (fcntl flock) en leest
vers van schijf ONDER het slot, zoals elke store in het dorp. De mens (of de seed) cureert de
sets; de skill leest ze vrij.
"""
from __future__ import annotations

from nooch_village.util import JsonStore

# Zaad-set uit de briefing: barefoot-ervaringen. Idempotent geseed bij village-start,
# net als het lexicon — bestaat de set al, dan blijft de mens-curatie ongemoeid.
_SEED_SETS: dict[str, dict] = {
    "barefoot_ervaringen": {
        "id": "barefoot_ervaringen",
        "label": "Barefoot-ervaringen",
        "queries": ["barefoot shoes experience", "barefoot shoes review", "vegan barefoot"],
        "subreddits": ["BarefootRunning", "barefootshoestalk", "vegan", "veganfashion"],
        "active": True,
    }
}


class BuzzQuerySets(JsonStore):
    """JSON-store van zoek-sets (data/buzz_query_sets.json). Sleutel = set-id."""

    _WRITE_METHODS = ("add", "set_active")
    _STATE = "_items"
    _default = dict
    _EXPECT = dict

    def add(self, set_id: str, label: str, queries: list[str], subreddits: list[str],
            active: bool = True) -> dict | None:
        """Voeg een set toe of overschrijf 'm. Lege id → geweigerd (None)."""
        set_id = (set_id or "").strip()
        if not set_id:
            return None
        rec = {
            "id": set_id,
            "label": (label or set_id).strip()[:120],
            "queries": [q.strip()[:120] for q in (queries or []) if q and q.strip()],
            "subreddits": [s.strip().lstrip("r/").strip("/")[:80]
                           for s in (subreddits or []) if s and s.strip()],
            "active": bool(active),
        }
        self._items[set_id] = rec
        self._save()
        return rec

    def set_active(self, set_id: str, active: bool) -> dict | None:
        rec = self._items.get(set_id)
        if rec is None:
            return None
        rec["active"] = bool(active)
        self._save()
        return rec

    def get(self, set_id: str | None) -> dict | None:
        return self._items.get(set_id) if set_id else None

    def all(self) -> list[dict]:
        return list(self._items.values())

    def active(self) -> list[dict]:
        return [s for s in self._items.values() if s.get("active")]


def seed_buzz_query_sets(store: BuzzQuerySets) -> None:
    """Laad de zaad-sets idempotent: alleen ontbrekende sets worden toegevoegd, bestaande
    (mens-gecureerde) sets blijven ongemoeid. Zoals seed_lexicon."""
    for set_id, rec in _SEED_SETS.items():
        if store.get(set_id) is None:
            store.add(rec["id"], rec["label"], rec["queries"], rec["subreddits"], rec["active"])
