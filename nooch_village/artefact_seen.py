"""Seen-markering — per-gebruiker 'gewijzigd sinds laatst gezien' op de artefact-tabs.

Aparte data-file (`data/artefact_seen.json`). Een gebruiker-specifiek signaal op tab-niveau:

- **seen-store**: per gebruiker een `last_seen`-tijdstip per (rol, tab).
- **geel** = er is een artefact-mutatie (brok-2 changelog: ts + erfketen) van die soort met de
  rol in de erfketen, ná het laatste bezoek van die tab. De markering zit dus op tab-niveau.
- `mark()` bij het openen van de tab schuift `last_seen` op → de markering verdwijnt.

Guest heeft geen persistente identiteit → geen markering (mark is een no-op, unseen leeg).
Governance-owned policies lopen NIET via de changelog (andere mutation_path) en zetten dus
geen seen-markering — bewust: die worden via governance gewijzigd, niet via de artefact-routes.
"""
from __future__ import annotations
import os
import time

from nooch_village.util import read_json, atomic_write_json, file_lock

# artefact-soort → tab-naam (spiegelt _KIND_TAB in de view).
_KIND_TAB = {"policy": "policies", "note": "notes", "tool": "tools"}


class SeenStore:
    """`data/artefact_seen.json`: {user: {f'{role_id}:{tab}': last_seen_ts}}. User = e-mail."""

    def __init__(self, path: str):
        self.path = path
        self._d: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._d)

    def mark(self, user: str | None, role_id: str, tab: str) -> None:
        """Zet last_seen voor (user, rol, tab) op nu. No-op voor guest/onbekend."""
        if not user or user == "guest" or not role_id or not tab:
            return
        with file_lock(self.path):
            self._d = read_json(self.path, {})       # verse toestand onder slot
            self._d.setdefault(user, {})[f"{role_id}:{tab}"] = time.time()
            self._save()

    def last_seen(self, user: str | None, role_id: str, tab: str) -> float:
        return float((self._d.get(user) or {}).get(f"{role_id}:{tab}", 0.0))


def unseen_tabs(seen: SeenStore, changelog: list[dict], user: str | None, role_id: str) -> set[str]:
    """Welke artefact-tabs van `role_id` 'gewijzigd sinds laatst gezien' tonen voor `user`.

    Voor elke changelog-entry: als de soort → een tab mapt, de rol in de erfketen-snapshot zit én
    de mutatie ná het laatste bezoek van die tab plaatsvond, is die tab ongezien. Guest / lege
    changelog → lege set."""
    if not user or user == "guest" or not changelog:
        return set()
    out: set[str] = set()
    for e in changelog:
        tab = _KIND_TAB.get(e.get("kind"))
        if not tab or tab in out:
            continue
        if role_id in (e.get("erfketen") or []) and e.get("ts", 0) > seen.last_seen(user, role_id, tab):
            out.add(tab)
    return out
