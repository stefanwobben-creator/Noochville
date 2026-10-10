"""Productieverplichtingen per batch — wat de fabriek nog krijgt (CN2 Runway, 10 oktober 2026).

Bijna al het geld op de bank is in de praktijk al toegezegd: klanten betalen bij bestelling, de
fabriek pas later. De fabriek krijgt 50% bij de batchbestelling en 50% bij oplevering. Dus:
100% verplicht zolang de batch niet besteld is, 50% na de bestelling (de eerste helft is betaald),
0 na oplevering en volledige betaling. Dat volgt vanzelf uit `totaal − betaald`, met één regel
erbij: opgeleverd én volledig betaald is 0, ook als er afgerond een cent verschilt.

Een regel: {id, batch, totaal_cents, betaald_cents, status (open | ordered | delivered), notitie,
door, op}. Bedragen in CENTEN (integers), net als het kostenregister — nooit floats.

De totale productiekosten komen NIET uit /bom: daar staat de materiaalkostprijs (prijs per kg ×
gewicht), niet de prijs per paar van de fabriek, en de gewichten zijn nog leeg. Handmatig dus, door
de Financial Controller of de anchor lead (`zicht.py`, groep `finance`).
"""
from __future__ import annotations

import time
import uuid

from nooch_village.util import JsonStore

STATUSSEN = ("open", "ordered", "delivered")


def _cents(x) -> int | None:
    """Euro's (komma of punt) → centen. None bij onleesbaar of negatief."""
    try:
        v = round(float(str(x).strip().replace(",", ".")) * 100)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def maak_regel(batch: str, totaal, betaald, status: str, notitie: str = "") -> tuple[dict | None, str]:
    naam = " ".join((batch or "").split())[:60]
    t, b = _cents(totaal), _cents(betaald if str(betaald or "").strip() else 0)
    if not naam:
        return None, "a batch name is required"
    if t is None or b is None:
        return None, "amounts must be numbers ≥ 0"
    if status not in STATUSSEN:
        return None, "unknown status"
    if b > t:
        return None, "paid cannot be more than the total"
    return {"batch": naam, "totaal_cents": t, "betaald_cents": b, "status": status,
            "notitie": " ".join((notitie or "").split())[:280]}, ""


def verplichting_cents(r: dict) -> int:
    if r.get("status") == "delivered" and r["betaald_cents"] >= r["totaal_cents"]:
        return 0
    return max(0, r["totaal_cents"] - r["betaald_cents"])


class ProductieVerplichtingStore(JsonStore):
    """`{id: regel}`, lock-veilig. Wijzigen mag (het is een stand, geen boeking)."""

    _STATE = "_d"
    _WRITE_METHODS = ("zet", "weg")

    def alle(self) -> list[dict]:
        return sorted((dict(v, id=k) for k, v in self._d.items() if isinstance(v, dict)),
                      key=lambda r: r.get("batch", "").lower())

    def totaal_cents(self) -> int:
        """De openstaande productieverplichtingen over alle batches."""
        return sum(verplichting_cents(r) for r in self.alle())

    def zet(self, regel: dict, *, rid: str = "", door: str = "") -> str:
        rid = rid or uuid.uuid4().hex[:10]
        self._d[rid] = {**regel, "door": door, "op": time.time()}
        self._save()
        return rid

    def weg(self, rid: str) -> bool:
        if rid not in self._d:
            return False
        del self._d[rid]
        self._save()
        return True
