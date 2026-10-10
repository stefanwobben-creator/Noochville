"""Vaste kosten per maand — een korte lijst, GEEN boekhouding (CN2 Runway, 10 oktober 2026).

Runway in maanden = cash ÷ vaste kosten per maand (delen, niet aftrekken: de voorzichtige variant
zonder omzet). Deze store levert de noemer: een paar regels met een bedrag per maand en een looptijd.
De boekhouding zelf (grootboek, facturen, btw, boekingen) blijft bij de accountant (Dutch GAAP, RJ);
NoochVille krijgt alleen deze lijst, de cash en het quotiënt.

Een regel: {id, omschrijving, bedrag (EUR per maand), categorie, van (ISO-datum), tot (ISO of ""
= doorlopend), notitie, door, op}. Het totaal op een peildatum is de som van de regels die dan
lopen: `van ≤ peildatum` en (`tot` leeg of `tot ≥ peildatum`).

Wie mag wat staat NIET hier maar in `zicht` (lezen: Financial Controller, Business strategy, de
anchor lead; wijzigen: Financial Controller en de anchor lead). Deze store is puur opslag.
"""
from __future__ import annotations

import re
import time
import uuid

from nooch_village.util import JsonStore

_TEKST_MAX = 120
_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _datum(s) -> str:
    s = str(s or "").strip()[:10]
    if not _DATUM_RE.match(s):
        return ""
    try:
        time.strptime(s, "%Y-%m-%d")
    except ValueError:
        return ""
    return s


def _bedrag(x) -> float | None:
    try:
        v = float(str(x).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return v if v == v and v >= 0 and v != float("inf") else None


def maak_regel(omschrijving: str, bedrag, *, categorie: str = "", van: str = "", tot: str = "",
               notitie: str = "") -> tuple[dict | None, str]:
    """(regel, "") of (None, reden). Fail-closed: geen omschrijving, geen geldig bedrag, geen
    begindatum of een einde vóór het begin is geen regel."""
    oms = " ".join((omschrijving or "").split())[:_TEKST_MAX]
    b = _bedrag(bedrag)
    v, t = _datum(van), _datum(tot)
    if not oms:
        return None, "a description is required"
    if b is None:
        return None, "the amount per month must be a number ≥ 0"
    if not v:
        return None, "a start date (YYYY-MM-DD) is required"
    if str(tot or "").strip() and not t:
        return None, "the end date must be YYYY-MM-DD, or empty for ongoing"
    if t and t < v:
        return None, "the end date is before the start date"
    return {"omschrijving": oms, "bedrag": b,
            "categorie": " ".join((categorie or "").split())[:60], "van": v, "tot": t,
            "notitie": " ".join((notitie or "").split())[:280]}, ""


def loopt_op(regel: dict, peildatum: str) -> bool:
    return regel["van"] <= peildatum and (not regel.get("tot") or regel["tot"] >= peildatum)


class VasteKostenStore(JsonStore):
    """`{id: regel}`. Lock-veilig via `JsonStore`: het cockpit schrijft, de daemon kan lezen."""

    _STATE = "_d"
    _WRITE_METHODS = ("zet", "weg")

    def alle(self) -> list[dict]:
        return sorted((dict(v, id=k) for k, v in self._d.items() if isinstance(v, dict)),
                      key=lambda r: (r.get("van", ""), r.get("omschrijving", "").lower()))

    def totaal_op(self, peildatum: str = "") -> float:
        """De vaste kosten per maand op de peildatum (ISO; leeg = vandaag)."""
        p = _datum(peildatum) or time.strftime("%Y-%m-%d")
        return round(sum(r["bedrag"] for r in self.alle() if loopt_op(r, p)), 2)

    def zet(self, regel: dict, *, rid: str = "", door: str = "") -> str:
        """Voeg toe (leeg `rid`) of vervang. Geeft het id terug."""
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
