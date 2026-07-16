"""Persistente belofte-grafen: per belofte de constituenten en hun (groeiende) oordelen.

De ontleding (welke constituenten) komt van een domein-adapter (compositie.ontleed_bom voor
een product, ontleed_voorwaarden voor een dienst). Het gronden (oordeel per constituent) doet
de scientist later, één component tegelijk. Deze store bewaart de graaf tussen die stappen door,
zodat je 'm van kaal (alles onbekend) naar rijp (alles gegrond) ziet worden. De weeg-logica
zelf zit in belofte_graaf.weeg_belofte en blijft puur en domein-agnostisch.
"""
from __future__ import annotations

from datetime import datetime

from nooch_village.util import JsonStore
from nooch_village.belofte_graaf import Constituent, Oordeel, Weging, weeg_belofte

_GELDIG = {o.value for o in Oordeel}


class BelofteStore(JsonStore):
    """Concurrency-veilig via JsonStore: seed (bootstrap) en gronden (scientist/actie) kunnen
    uit verschillende processen komen, dus schrijven loopt onder het bestandsslot."""
    _STATE = "_data"
    _default = dict
    _EXPECT = dict
    _WRITE_METHODS = ("zet_graaf", "grond")

    def all(self) -> dict:
        return self._data

    def get(self, belofte_id: str) -> dict | None:
        return self._data.get(belofte_id)

    def zet_graaf(self, belofte_id: str, belofte: str, constituenten: list[Constituent],
                  *, concept_id: str | None = None, word: str | None = None) -> dict:
        """Leg de ontleding vast (of ver-ontleed). Bestaande oordelen op gelijknamige
        constituenten blijven behouden: opnieuw ontleden gooit geen bewijs weg."""
        bestaand = self._data.get(belofte_id, {})
        oud = {c["naam"]: c for c in bestaand.get("constituenten", [])}
        rows = []
        for c in constituenten:
            prev = oud.get(c.naam, {})
            rows.append({
                "naam": c.naam,
                "realisatie": c.realisatie,
                "alternatieven": list(c.alternatieven),
                "bron": c.bron,
                "oordeel": prev.get("oordeel", Oordeel.ONBEKEND.value),
                "grounds": prev.get("grounds", ""),
                "by": prev.get("by", ""),
                "date": prev.get("date", ""),
            })
        entry = {
            "belofte": belofte,
            "concept_id": concept_id if concept_id is not None else bestaand.get("concept_id"),
            "word": word if word is not None else bestaand.get("word"),
            "constituenten": rows,
            "created": bestaand.get("created") or datetime.now().strftime("%Y-%m-%d"),
            "updated": datetime.now().strftime("%Y-%m-%d"),
        }
        self._data[belofte_id] = entry
        self._save()
        return entry

    def grond(self, belofte_id: str, naam: str, oordeel, grounds: str = "",
              by: str = "Scientist") -> dict | None:
        """Zet het oordeel van één constituent (stap 2: de scientist grondt). Fail-closed:
        een ongeldig oordeel valt terug op ONBEKEND, nooit op een valse HOUDT."""
        entry = self._data.get(belofte_id)
        if entry is None:
            return None
        o = oordeel.value if isinstance(oordeel, Oordeel) else str(oordeel)
        if o not in _GELDIG:
            o = Oordeel.ONBEKEND.value
        for row in entry["constituenten"]:
            if row["naam"] == naam:
                row.update(oordeel=o, grounds=grounds, by=by,
                           date=datetime.now().strftime("%Y-%m-%d"))
                entry["updated"] = datetime.now().strftime("%Y-%m-%d")
                self._save()
                return row
        return None

    def weeg(self, belofte_id: str) -> Weging | None:
        """Reconstrueer de belofte uit de opgeslagen oordelen (weakest link)."""
        entry = self._data.get(belofte_id)
        if entry is None:
            return None
        oordelen = {
            r["naam"]: Oordeel(r["oordeel"]) if r["oordeel"] in _GELDIG else Oordeel.ONBEKEND
            for r in entry["constituenten"]
        }
        return weeg_belofte(oordelen)


def seed_schoen_graaf(store: BelofteStore) -> bool:
    """Zet eenmalig de belofte-graaf van de Nooch-schoen uit de aangeleverde BOM. Idempotent:
    doet niets als de graaf er al is (zodat gedane grondingen niet worden overschreven).
    Geeft True als er iets is gezet."""
    from nooch_village.compositie import ontleed_bom
    from nooch_village.data_bom import (
        NOOCH_SCHOEN_BOM, SCHOEN_BELOFTE_ID, SCHOEN_BELOFTE,
    )
    if store.get(SCHOEN_BELOFTE_ID) is not None:
        return False
    constituenten = ontleed_bom(NOOCH_SCHOEN_BOM)
    store.zet_graaf(SCHOEN_BELOFTE_ID, SCHOEN_BELOFTE, constituenten,
                    word="sustainable shoes")
    return True
