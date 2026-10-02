"""Wat een component anders heeft dan de stuklijst — per model, per variant (BOM Correctie 3C + Stuk 4).

De stuklijst (`data_bom.MODELLEN[model]["master"]`) is een hardcoded Python-bron. Deze store houdt
de AFWIJKINGEN daarop, bewerkbaar op `/bom`:

    sleutel = (model, variant, component)
    variant ""  = een afwijking op de MASTER (geldt voor elke variant, tenzij die zelf afwijkt)
    waarde      = materiaal en/of gewicht in gram; `toegevoegd` = een rij die in de master niet
                  bestaat (Hemp naast HyphaLite bij de Hi)

VOORRANG: variant > master-afwijking > stuklijst. Leeg zetten haalt de afwijking weg; dan geldt
het niveau eronder weer.

PER COMPONENT, niet per materiaal (anders dan `bom_leveranciers`): het materiaal varieert legitiem
per rij. De LEVERANCIER blijft per materiaal: wijzig je het materiaal, dan volgt de leverancier.

COMPAT: sleutels van vóór Stuk 4 waren alleen de component ('vamp'). Die lezen als
(standaardmodel, "", component) — een master-afwijking, wat ze ook waren.

De poort is dezelfde als bij de leverancier: houder van het domein `Materials` of Circle Lead.
"""
from __future__ import annotations

import time

from nooch_village.util import JsonStore

_NAAM_MAX = 120
_SEP = "|"


def sleutel(part: str) -> str:
    """De componentnaam genormaliseerd: hoofdletter- en spatie-ongevoelig."""
    return " ".join((part or "").split()).lower()


def _standaard_model() -> str:
    from nooch_village.data_bom import STANDAARD_MODEL
    return STANDAARD_MODEL


def _gram(waarde) -> float | None:
    """Een gewicht ≥ 0, of None (leeg / onleesbaar = geen gewicht-afwijking)."""
    if waarde is None or str(waarde).strip() == "":
        return None
    try:
        g = float(str(waarde).strip().replace(",", "."))
    except ValueError:
        return None
    return g if g == g and g >= 0 else None


class BomMateriaalStore(JsonStore):
    """`{"model|variant|part": {"model", "variant", "part", "materiaal", "gram", "toegevoegd",
    "door", "op"}}`, plus oude sleutels zonder `|` (zie COMPAT)."""

    _STATE = "_d"
    _WRITE_METHODS = ("zet", "wis")

    # ── lezen ──────────────────────────────────────────────────────────────

    def _regels(self) -> list[dict]:
        uit = []
        for k, v in self._d.items():
            if not isinstance(v, dict):
                continue
            if _SEP in k:
                model, variant, part = k.split(_SEP, 2)
            else:                                    # COMPAT: alleen een component
                model, variant, part = _standaard_model(), "", k
            uit.append({**v, "model": model, "variant": variant, "sleutel": part,
                        "part": v.get("part") or part})
        return uit

    def afwijkingen(self, model: str, variant: str = "") -> list[dict]:
        """Wat er op dit niveau afwijkt: eerst de master-afwijkingen, dan die van de variant —
        in die volgorde, zodat een variant de master overschrijft."""
        niveaus = ("",) if not variant else ("", variant)
        regels = [r for r in self._regels() if r["model"] == model and r["variant"] in niveaus]
        return sorted(regels, key=lambda r: niveaus.index(r["variant"]))

    def van(self, part: str, *, model: str = "", variant: str = "") -> str:
        """Het afwijkende materiaal van een component op PRECIES dit niveau, of ""."""
        r = self._regel(model or _standaard_model(), variant, part)
        return str((r or {}).get("materiaal") or "")

    def alle(self, model: str = "", variant: str = "") -> dict[str, str]:
        """{partsleutel: materiaal} na voorrang — wat `wiki_seed` en oudere aanroepers lezen."""
        uit: dict[str, str] = {}
        for r in self.afwijkingen(model or _standaard_model(), variant):
            if r.get("materiaal"):
                uit[r["sleutel"]] = str(r["materiaal"])
        return uit

    def per_variant(self, model: str = "") -> dict[str, list[dict]]:
        """{variant: [regels]} voor één model, master als "". Voor de materiaalpagina's."""
        uit: dict[str, list[dict]] = {}
        for r in self._regels():
            if r["model"] == (model or _standaard_model()):
                uit.setdefault(r["variant"], []).append(r)
        return uit

    def regel(self, part: str, *, model: str = "", variant: str = "") -> dict:
        """De afwijking op PRECIES dit niveau ({} als er geen is)."""
        return dict(self._regel(model or _standaard_model(), variant, part) or {})

    def _regel(self, model: str, variant: str, part: str) -> dict | None:
        k = sleutel(part)
        v = self._d.get(_SEP.join((model, variant, k)))
        if v is None and not variant and model == _standaard_model():
            v = self._d.get(k)                       # COMPAT
        return v if isinstance(v, dict) else None

    # ── schrijven ──────────────────────────────────────────────────────────

    def zet(self, part: str, materiaal: str = "", *, door: str = "", model: str = "",
            variant: str = "", gram=None, toegevoegd: bool = False) -> bool:
        """Zet een afwijking. Materiaal en gewicht zijn elk optioneel; zijn ze allebei leeg en is
        het geen toegevoegde rij, dan is dit gelijk aan `wis`. Een TOEGEVOEGDE rij heeft een
        materiaal nodig — een component zonder materiaal is geen component. False als er niets te
        zetten valt."""
        k = sleutel(part)
        model = model or _standaard_model()
        if not k:
            return False
        naam = " ".join((materiaal or "").split())[:_NAAM_MAX]
        g = _gram(gram)
        if toegevoegd and not naam:
            return False
        sl = _SEP.join((model, variant, k))
        if not variant and model == _standaard_model():
            self._d.pop(k, None)                     # COMPAT: oude sleutel gaat op in de nieuwe
        if not naam and g is None and not toegevoegd:
            self._d.pop(sl, None)
        else:
            self._d[sl] = {"part": " ".join(part.split()), "materiaal": naam, "gram": g,
                           "toegevoegd": bool(toegevoegd), "door": door or "", "op": time.time()}
        self._save()
        return True

    def wis(self, part: str, *, model: str = "", variant: str = "") -> bool:
        """Haal de afwijking op dit niveau weg (ook een toegevoegde rij)."""
        k = sleutel(part)
        model = model or _standaard_model()
        weg = self._d.pop(_SEP.join((model, variant, k)), None)
        if not variant and model == _standaard_model():
            weg = self._d.pop(k, None) or weg
        if weg is None:
            return False
        self._save()
        return True
