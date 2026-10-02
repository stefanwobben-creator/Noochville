"""Welke leverancier levert welk materiaal — de ENE bewerkbare plek (BOM Correctie 2, 2 oktober 2026).

WAAROM EEN EIGEN STORE. De stuklijst (`data_bom.py`) is een hardcoded Python-bron: elke wijziging
vroeg een code-aanpassing. Stefan: "ik zie niet hoe ik de BOM kan bewerken". De koppeling
materiaal → leverancier hoort dus ergens waar een mens hem in het scherm kan zetten, en dat is hier.

ÉÉN BRON, TWEE PLEKKEN DIE HEM TONEN. Het BOM-scherm (Supplier-kolom, bewerkbaar) en de
materiaalpagina ("Supplied by", afgeleid in `wiki_seed`). De `Supplier`-kolom die stuk 1 aan
`data_bom.py` toevoegde is weg: twee plekken voor één feit is precies wat `reference, don't copy`
verbiedt.

PER MATERIAAL, niet per component (besluit Stefan): HyphaLite zit in zeven onderdelen en heeft één
leverancier, dus één koppeling. De sleutel is de genormaliseerde materiaalnaam — dezelfde
groepering als de materiaalpagina (`wiki_seed._materiaalnaam`, hoofdletter-ongevoelig, zonder
'(?)'), anders hoort een leverancier bij een materiaal dat niet bestaat.

DE LEVERANCIER IS EEN NAAM, geen pagina-id: hij mag er al staan vóór iemand zijn pagina schrijft.
Bestaat de pagina, dan linkt het scherm; zo niet, dan staat hij op de verlanglijst.
"""
from __future__ import annotations

import time

from nooch_village.util import JsonStore

#: Het domein dat bepaalt wie een koppeling mag zetten (de houder of de Circle Lead). ÉÉN plek;
#: de toolkaart in `views/overview._DOMAIN_TOOLS` hangt aan hetzelfde domein.
DOMEIN = "Materials"

_NAAM_MAX = 120


def sleutel(materiaal: str) -> str:
    """De groeperingssleutel van een materiaalnaam — dezelfde als die van de materiaalpagina."""
    from nooch_village.wiki_seed import _materiaalnaam
    return _materiaalnaam(materiaal)[0].lower()


class BomLeverancierStore(JsonStore):
    """`{sleutel: {"materiaal", "leverancier", "door", "op"}}`. Eén leverancier per materiaal.

    Lock-veilig via `JsonStore`: het cockpit schrijft, de zaaier (CLI) leest — twee processen."""

    _STATE = "_d"
    _WRITE_METHODS = ("zet",)

    def van(self, materiaal: str) -> str:
        """De gekoppelde leverancier, of "" als er geen is."""
        return str((self._d.get(sleutel(materiaal)) or {}).get("leverancier") or "")

    def alle(self) -> dict[str, str]:
        """{materiaalsleutel: leverancier} — wat `bom_reken` en `wiki_seed` lezen."""
        return {k: str(v.get("leverancier") or "") for k, v in self._d.items()
                if isinstance(v, dict) and v.get("leverancier")}

    def koppelingen(self) -> list[tuple[str, str]]:
        """(materiaal zoals gespeld, leverancier) — voor de leverancierpagina's in `wiki_seed`."""
        return sorted((str(v.get("materiaal") or k), str(v.get("leverancier") or ""))
                      for k, v in self._d.items() if isinstance(v, dict) and v.get("leverancier"))

    def zet(self, materiaal: str, leverancier: str, *, door: str = "") -> bool:
        """Koppel (of ontkoppel, bij een lege naam) een leverancier aan een materiaal. False bij een
        lege materiaalnaam: dan valt er niets te koppelen."""
        k = sleutel(materiaal)
        if not k:
            return False
        naam = " ".join((leverancier or "").split())[:_NAAM_MAX]
        if not naam:
            self._d.pop(k, None)
        else:
            self._d[k] = {"materiaal": " ".join(materiaal.split()), "leverancier": naam,
                          "door": door or "", "op": time.time()}
        self._save()
        return True
