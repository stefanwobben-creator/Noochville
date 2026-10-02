"""Welke varianten een model heeft, en hun foto (BOM Stuk 4, 2 oktober 2026).

ALLEEN WAT ER ECHT IS. Geen kruistabel van kleur × hoogte: THE '269' heeft 10 kleuren in normaal
en 5 in Hi, en alleen de combinaties die als Shopify-product bestaan horen hier. Een variant komt
erbij via het formulier op `/bom` (dezelfde poort als materiaal en leverancier).

DE SLEUTEL IS DE SHOPIFY-HANDLE (`the-269-hi-black`), platte tekst, geen live koppeling. Bewust
geen kunstmatige kleur/hoogte-enum: wordt dit ooit de basis voor een materiaalplanning over
bestelvolumes, dan is de handle de naad naar de orders.

WAT EEN VARIANT ANDERS DOET staat niet hier maar in `bom_materialen` (per model, variant,
component). Deze store kent alleen het bestaan, de naam en de foto.

De foto kan per variant, en per model als terugval (sleutel `""` = het model zelf): een URL of een
geüpload bestand (`foto`: een eigen bestand onder `cockpit2_util.EIGEN_BESTAND`, of `https://`).
"""
from __future__ import annotations

import re
import time

from nooch_village.util import JsonStore

#: Een Shopify-handle: kleine letters, cijfers en koppeltekens. Strenger dan nodig mag niet (dan
#: weigert hij een echte handle), losser ook niet (dan is het geen sleutel meer om op te koppelen).
HANDLE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NAAM_MAX = 120
_FOTO_MAX = 500
#: Waar een GEÜPLOADE productfoto staat (`/bom-foto/<model>/<bestand>`). De constante zelf woont in
#: `cockpit2_util`, naast `EIGEN_BESTAND`, omdat `_embed_html` hem moet kennen; hier alleen verwezen.
from nooch_village.cockpit2_util import BOM_FOTO  # noqa: E402


def geldige_handle(h: str) -> bool:
    return bool(HANDLE_RE.match(h or "")) and len(h) <= 120


def geldige_foto(url: str) -> bool:
    """Alleen een eigen bestand (`EIGEN_BESTAND`, hetzelfde voorvoegsel als de wiki-bijlagen) of een
    https-adres — nooit `javascript:` of `data:`."""
    from nooch_village.cockpit2_util import EIGEN_BESTAND
    u = (url or "").strip()
    return len(u) <= _FOTO_MAX and u.startswith((EIGEN_BESTAND, BOM_FOTO, "https://"))


class BomVariantStore(JsonStore):
    """`{model: {handle: {"naam", "foto", "door", "op"}}}`; handle `""` = het model zelf (foto)."""

    _STATE = "_d"
    _WRITE_METHODS = ("voeg_toe", "verwijder", "zet_foto")

    def varianten(self, model: str) -> list[dict]:
        """De varianten van een model, op naam gesorteerd, zonder de model-eigen regel."""
        rij = self._d.get(model) or {}
        uit = [{"handle": h, **v} for h, v in rij.items() if h and isinstance(v, dict)]
        return sorted(uit, key=lambda v: (str(v.get("naam") or v["handle"]).lower(), v["handle"]))

    def get(self, model: str, handle: str) -> dict | None:
        v = (self._d.get(model) or {}).get(handle)
        return {"handle": handle, **v} if isinstance(v, dict) and handle else None

    def foto(self, model: str, handle: str = "") -> str:
        """De foto van de variant, anders die van het model, anders ""."""
        rij = self._d.get(model) or {}
        for k in ((handle, "") if handle else ("",)):
            f = str((rij.get(k) or {}).get("foto") or "")
            if f:
                return f
        return ""

    def heeft_foto(self, model: str, bestand: str) -> bool:
        """Staat dit geüploade bestand als foto bij dit model (of een variant ervan)? De leesroute
        serveert alleen wat hier geregistreerd is."""
        doel = f"{BOM_FOTO}{model}/{bestand}"
        return any(isinstance(v, dict) and v.get("foto") == doel
                   for v in (self._d.get(model) or {}).values())

    def voeg_toe(self, model: str, handle: str, naam: str = "", *, door: str = "") -> bool:
        """Een variant erbij. False bij een ongeldige handle of als hij al bestaat (dan verandert
        er niets: een tweede keer aanmaken mag een bestaande niet overschrijven)."""
        handle = (handle or "").strip().lower()
        if not model or not geldige_handle(handle):
            return False
        rij = self._d.setdefault(model, {})
        if handle in rij:
            return False
        rij[handle] = {"naam": " ".join((naam or handle).split())[:_NAAM_MAX], "foto": "",
                       "door": door or "", "op": time.time()}
        self._save()
        return True

    def verwijder(self, model: str, handle: str) -> bool:
        rij = self._d.get(model) or {}
        if not handle or handle not in rij:
            return False
        del rij[handle]
        self._save()
        return True

    def zet_foto(self, model: str, handle: str, foto: str, *, door: str = "") -> bool:
        """Zet (of wis, bij leeg) de foto van een variant, of van het model bij handle `""`.
        False bij een ongeldig adres of een onbekende variant."""
        foto = (foto or "").strip()
        if foto and not geldige_foto(foto):
            return False
        rij = self._d.setdefault(model, {})
        if handle and handle not in rij:
            return False
        regel = rij.setdefault(handle, {})
        regel.update({"foto": foto, "door": door or "", "op": time.time()})
        self._save()
        return True
