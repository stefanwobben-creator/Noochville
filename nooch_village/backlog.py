"""Backlog Builder — de gestructureerde bugs-/wensen-/ideeën-backlog van de Website Developer-rol.

Prototype: datastructuur + store. GEEN LLM/Noochie-integratie (die komt later). Opslag:
data/backlog.json. Zelfde fail-loud read_json-patroon als de andere stores.

Een item doorloopt zes staten (ruw → geformuleerd → verkleind → gegroepeerd/geprioriteerd →
uitgevoerd). In dit prototype wordt de staat handmatig door de beheerder (Website Developer)
gezet; de Noochie-hulp bij formuleren en prioriteren volgt in een latere laag.
"""
from __future__ import annotations
import os
import time
import uuid
from dataclasses import dataclass, asdict

from nooch_village.util import atomic_write_json, read_json

TYPES = ("bug", "wens", "idee")
DOMEINEN = ("website", "village")
STATEN = ("ruw", "geformuleerd", "verkleind", "geprioriteerd", "uitgevoerd")
IMPACTS = ("hoog", "medium", "laag")
EFFORTS = ("1u", "1d", "2d", "1w")


@dataclass
class BacklogItem:
    id: str
    titel: str
    beschrijving: str
    type: str                        # bug | wens | idee
    domein: str                      # website | village
    staat: str                       # ruw | geformuleerd | verkleind | geprioriteerd | uitgevoerd
    inbrenger_id: str                # person-id van de indiener ("" bij guest/onbekend)
    aangemaakt_at: float
    impact: str | None = None        # hoog | medium | laag | None
    effort: str | None = None        # 1u | 1d | 2d | 1w | None
    acceptatiecriteria: str = ""      # Definition of Done (optioneel; Noochie vult later)


class BacklogStore:
    """Store: id -> item. data/backlog.json."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, titel: str, beschrijving: str, type_: str, domein: str,
            inbrenger_id: str) -> BacklogItem | None:
        titel = (titel or "").strip()
        if not titel:
            return None
        it = BacklogItem(
            id=uuid.uuid4().hex[:12],
            titel=titel[:200],
            beschrijving=(beschrijving or "").strip()[:2000],
            type=type_ if type_ in TYPES else "idee",
            domein=domein if domein in DOMEINEN else "village",
            staat="ruw",
            inbrenger_id=(inbrenger_id or ""),
            aangemaakt_at=time.time(),
        )
        self._items[it.id] = asdict(it)
        self._save()
        return it

    def get(self, bid: str) -> BacklogItem | None:
        d = self._items.get(bid)
        return BacklogItem(**d) if d else None

    def all(self) -> list[BacklogItem]:
        return [BacklogItem(**d) for d in self._items.values()]

    def update_staat(self, bid: str, staat: str) -> bool:
        if staat not in STATEN or bid not in self._items:
            return False
        self._items[bid]["staat"] = staat
        self._save()
        return True

    def update_prioriteit(self, bid: str, impact: str | None, effort: str | None) -> bool:
        """Zet impact- en effort-label. Lege/ongeldige waarde wist het betreffende label (None)."""
        if bid not in self._items:
            return False
        self._items[bid]["impact"] = impact if impact in IMPACTS else None
        self._items[bid]["effort"] = effort if effort in EFFORTS else None
        self._save()
        return True
