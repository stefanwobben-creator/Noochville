"""Merkenstore voor de Concurrent-scout: ontdekte concurrenten met hun status.

Spiegelt de Library-gedachte: kandidaten worden voorgesteld, de mens bevestigt of negeert
(in de cockpit), en bevestigde merken worden vanaf dan meegenomen in de monitoring. De
ontdekking (regex op koppen) is ruizig, dus de poort is bewust mens-gated.

  candidates : {brand: {article, link, first_seen}}  — wacht op jouw oordeel
  confirmed  : [brand, ...]                           — meegenomen in de analyse
  rejected   : [brand, ...]                           — ruis, niet opnieuw voorstellen

Dedup is hoofdletter-ongevoelig zodat 'Cariuma' en 'cariuma' niet dubbel binnenkomen.
"""
from __future__ import annotations
import json
import os
from datetime import date

from nooch_village.util import atomic_write_json


class CompetitorBrands:
    def __init__(self, path: str):
        self.path = path
        self._data = {"candidates": {}, "confirmed": [], "rejected": []}
        if os.path.exists(path):
            try:
                loaded = json.load(open(path))
                self._data.update({k: loaded.get(k, self._data[k]) for k in self._data})
            except Exception:
                pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._data)

    def _known_lower(self) -> set:
        lower = {b.lower() for b in self._data["confirmed"]}
        lower |= {b.lower() for b in self._data["rejected"]}
        lower |= {b.lower() for b in self._data["candidates"]}
        return lower

    def status(self, brand: str) -> str | None:
        b = (brand or "").lower()
        if b in {x.lower() for x in self._data["confirmed"]}:
            return "confirmed"
        if b in {x.lower() for x in self._data["rejected"]}:
            return "rejected"
        if b in {x.lower() for x in self._data["candidates"]}:
            return "candidate"
        return None

    def confirmed(self) -> list[str]:
        return list(self._data["confirmed"])

    def candidates(self) -> list[dict]:
        return [{"brand": b, **meta} for b, meta in self._data["candidates"].items()]

    def add_candidate(self, brand: str, article: str = "", link: str = "") -> bool:
        """Nieuwe kandidaat (alleen als nog onbekend in welke status dan ook). True = toegevoegd."""
        brand = (brand or "").strip()
        if not brand or brand.lower() in self._known_lower():
            return False
        self._data["candidates"][brand] = {
            "article": article, "link": link, "first_seen": date.today().isoformat()}
        self._save()
        return True

    def confirm(self, brand: str) -> bool:
        """Bevestig een merk → meegenomen in de monitoring. Werkt vanuit kandidaat of rejected."""
        match = self._find(brand)
        if match is None:
            return False
        self._data["candidates"].pop(match, None)
        self._data["rejected"] = [b for b in self._data["rejected"] if b.lower() != match.lower()]
        if match.lower() not in {b.lower() for b in self._data["confirmed"]}:
            self._data["confirmed"].append(match)
        self._save()
        return True

    def reject(self, brand: str) -> bool:
        """Negeer een merk (ruis) → niet opnieuw voorstellen."""
        match = self._find(brand)
        if match is None:
            return False
        self._data["candidates"].pop(match, None)
        self._data["confirmed"] = [b for b in self._data["confirmed"] if b.lower() != match.lower()]
        if match.lower() not in {b.lower() for b in self._data["rejected"]}:
            self._data["rejected"].append(match)
        self._save()
        return True

    def _find(self, brand: str) -> str | None:
        """Vind de opgeslagen schrijfwijze van een merk (hoofdletter-ongevoelig)."""
        b = (brand or "").lower()
        for store in (self._data["candidates"], self._data["confirmed"], self._data["rejected"]):
            for known in store:
                if known.lower() == b:
                    return known
        return None
