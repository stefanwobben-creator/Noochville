"""Belofte-graaf — eerste-principes-ontleding van een belofte, volledig domein-agnostisch.

Een BELOFTE ("X is/doet Y") valt uiteen in CONSTITUENTEN: de noodzakelijke onderdelen
waarvan de belofte afhangt. Voor een schoen zijn dat de materialen (de BOM), voor een
papieren paperclip de functionele eisen (klemt, houdt N vellen, herbruikbaar), voor een
studie-dienst voor 65-jarigen de voorwaarden (inschrijftoegang, cognitieve aansluiting,
erkenning). Het model kent het domein NIET: het kent alleen belofte, constituenten en per
constituent een oordeel.

Eerste principes (eerst afbreken tot de atomen, dan opnieuw opbouwen):
  1. ontleden      — de belofte in haar constituenten (het domein levert de 'snede' aan)
  2. gronden       — per constituent een oordeel: houdt / houdt-niet / onbekend, met bewijs
  3. reconstrueren — de belofte is zo sterk als haar ZWAKSTE constituent (weakest link)

De reconstructie (weeg_belofte) is puur en abstract: ze weet niets van materiaal of
duurzaamheid, ze rekent alleen op oordelen. Zo klopt het model net zo goed voor een
paperclip of een dienst als voor een schoen. De 'snede' (welke constituenten) komt uit
een domein-adapter (bv. compositie.ontleed_bom); de grond-functie (welk oordeel per
constituent) wordt geïnjecteerd. De kern blijft leeg van domein.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


class Oordeel(StrEnum):
    """Het oordeel over één constituent: draagt hij de belofte?"""
    HOUDT = "houdt"             # voldoet aan wat de belofte hier eist (met bewijs)
    HOUDT_NIET = "houdt_niet"   # breekt de belofte hier (het zwakste atoom)
    ONBEKEND = "onbekend"       # (nog) niet gegrond — geen oordeel mogelijk


class Sterkte(StrEnum):
    LEEG = "leeg"                   # geen constituenten → niets te wegen
    GEBROKEN = "gebroken"           # minstens één constituent houdt niet
    ONBEWEZEN = "onbewezen"         # geen breuk, maar nog onbekende constituenten
    VERDEDIGBAAR = "verdedigbaar"   # elke constituent houdt


@dataclass(frozen=True)
class Constituent:
    """Een noodzakelijk onderdeel waarvan de belofte afhangt. Domein-agnostisch:
    'naam' is de rol in de belofte (Outsole, klemkracht, inschrijftoegang), 'realisatie'
    de huidige invulling (Pliant, gerecycled staal, online-portal), 'alternatieven' de
    kandidaat-invullingen, 'bron' waar deze snede vandaan komt (BOM, dienstontwerp, ...)."""
    naam: str
    realisatie: str = ""
    alternatieven: tuple[str, ...] = ()
    bron: str = ""


@dataclass(frozen=True)
class Weging:
    """Het gereconstrueerde oordeel over de héle belofte, plus waar hij breekt of gapt."""
    sterkte: Sterkte
    houdbaar: bool                # True alleen als elke constituent houdt
    gebroken_op: tuple[str, ...]  # constituenten met HOUDT_NIET (hier breekt de belofte)
    onbekend_op: tuple[str, ...]  # constituenten met ONBEKEND (hier ontbreekt bewijs)

    @property
    def bottleneck(self) -> tuple[str, ...]:
        """De constituenten die de belofte tegenhouden: eerst de breuken, dan de gaten.
        Dit is de R&D-prioriteit: precies hier moet aandacht heen."""
        return self.gebroken_op + self.onbekend_op


def weeg_belofte(oordelen: dict[str, Oordeel]) -> Weging:
    """Reconstrueer de belofte uit de constituent-oordelen (weakest link, puur, abstract).

    Een belofte is pas verdedigbaar als ELKE noodzakelijke constituent zelfstandig houdt.
    Eén constituent die niet houdt breekt het geheel (eerste-principes: het zwakste atoom
    bepaalt). Onbekende constituenten maken de belofte niet gebroken maar onbewezen — je
    weet het simpelweg nog niet."""
    if not oordelen:
        return Weging(Sterkte.LEEG, False, (), ())
    gebroken = tuple(n for n, o in oordelen.items() if o == Oordeel.HOUDT_NIET)
    onbekend = tuple(n for n, o in oordelen.items() if o == Oordeel.ONBEKEND)
    if gebroken:
        return Weging(Sterkte.GEBROKEN, False, gebroken, onbekend)
    if onbekend:
        return Weging(Sterkte.ONBEWEZEN, False, (), onbekend)
    return Weging(Sterkte.VERDEDIGBAAR, True, (), ())


# Een grond-functie zet één constituent om in een oordeel (+ onderbouwing). Wordt
# geïnjecteerd: een LLM-redenering, een literatuur-adapter, of in een test een stub.
GrondFn = Callable[[Constituent], "tuple[Oordeel, str]"]


def ground_constituenten(constituenten: list[Constituent], grond_fn: GrondFn) -> dict[str, Oordeel]:
    """Vel per constituent een oordeel via een injecteerbare grond-functie. Fail-closed:
    een fout, of een antwoord dat geen geldig Oordeel is, wordt ONBEKEND — nooit een valse
    HOUDT. Zonder bewijs blijft een belofte dus onbewezen, niet stiekem verdedigbaar."""
    uit: dict[str, Oordeel] = {}
    for c in constituenten:
        try:
            oordeel, _grounds = grond_fn(c)
        except Exception:
            uit[c.naam] = Oordeel.ONBEKEND
            continue
        uit[c.naam] = oordeel if isinstance(oordeel, Oordeel) else Oordeel.ONBEKEND
    return uit
