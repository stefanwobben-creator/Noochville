"""Welk materiaal een component heeft — bewerkbaar op `/bom` (BOM Correctie 3, deel C, 2 oktober 2026).

De stuklijst (`data_bom.py`) is een hardcoded Python-bron; elk ander materiaal vroeg een
code-aanpassing. Deze store houdt de WIJZIGINGEN daarop: per component het materiaal dat er nu in
zit. Een component zonder wijziging volgt de stuklijst. Een lege waarde zetten haalt de wijziging
weg — dan geldt de stuklijst weer.

PER COMPONENT, niet per materiaal (anders dan `bom_leveranciers`): het materiaal varieert
legitiem per rij — de vamp kan hennep worden terwijl de tong HyphaLite blijft. De LEVERANCIER blijft
per materiaal: wijzig je het materiaal van een rij, dan toont het scherm de leverancier die bij het
nieuwe materiaal hoort.

De poort is dezelfde als bij de leverancier: houder van het domein `Materials` of Circle Lead
(`bom_leveranciers.DOMEIN` — één plek voor dat domein).
"""
from __future__ import annotations

import time

from nooch_village.util import JsonStore

_NAAM_MAX = 120


def sleutel(part: str) -> str:
    """De componentnaam genormaliseerd: hoofdletter- en spatie-ongevoelig, zodat 'Heel tab' en
    'heel  tab' één rij zijn."""
    return " ".join((part or "").split()).lower()


class BomMateriaalStore(JsonStore):
    """`{partsleutel: {"part", "materiaal", "door", "op"}}`. Alleen de wijzigingen op de stuklijst.

    Lock-veilig via `JsonStore`: het cockpit schrijft, de zaaier (CLI) leest."""

    _STATE = "_d"
    _WRITE_METHODS = ("zet",)

    def van(self, part: str) -> str:
        """Het gewijzigde materiaal van deze component, of "" (dan geldt de stuklijst)."""
        return str((self._d.get(sleutel(part)) or {}).get("materiaal") or "")

    def alle(self) -> dict[str, str]:
        """{partsleutel: materiaal} — wat `bom_reken` en `wiki_seed` lezen."""
        return {k: str(v.get("materiaal") or "") for k, v in self._d.items()
                if isinstance(v, dict) and v.get("materiaal")}

    def zet(self, part: str, materiaal: str, *, door: str = "") -> bool:
        """Zet het materiaal van een component, of haal de wijziging weg bij een lege naam. False bij
        een lege componentnaam: dan valt er niets te zetten."""
        k = sleutel(part)
        if not k:
            return False
        naam = " ".join((materiaal or "").split())[:_NAAM_MAX]
        if not naam:
            self._d.pop(k, None)
        else:
            self._d[k] = {"part": " ".join(part.split()), "materiaal": naam,
                          "door": door or "", "op": time.time()}
        self._save()
        return True
