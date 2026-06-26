"""Kennislaag — berekende sterkte en gaten-detectie.

Sterkte is een PURE functie over het link-web, niet opgeslagen. Zo kan hij nooit verouderen:
komt er later een tegensprekend kaartje bij, dan zakt de sterkte vanzelf bij de volgende blik.
Dit realiseert "autonome promotie mét validiteitscheck, geen ja-knikker" (docs/ONDERZOEK_kennismodel.md):
de machine bepaalt de sterkte objectief uit het bewijs; de mens hoeft niets te stempelen.

Definities:
- Een "leg" (bewijspoot) van een claim = een onafhankelijke bron die de claim steunt. Onafhankelijk
  = verschillende `source`. Tien artikelen die naar één studie verwijzen blijven één leg.
- Een bevinding die zelf gemeten is, levert zijn eigen bron als leg.

Sterkte-ladder (soort verandert nooit; alleen de sterkte evolueert):
  ONBESLIST  : geen bewijspoot
  ONDERSTEUND: 1 onafhankelijke poot
  BEVESTIGD  : >=2 onafhankelijke poten, maar geen gemeten
  GEVERIFIEERD: >=2 onafhankelijke poten EN >=1 gemeten   (de validiteitscheck)
  BETWIST    : er is minstens één tegensprekend kaartje   (overrulet alles)
"""
from __future__ import annotations
from enum import StrEnum

from nooch_village.insight import Insight, ClaimKind, EvidenceType

_MEASURED = {EvidenceType.MEASURED, EvidenceType.PEER_REVIEWED, EvidenceType.CERTIFIED}


class Strength(StrEnum):
    ONBESLIST = "onbeslist"
    ONDERSTEUND = "ondersteund"
    BEVESTIGD = "bevestigd"
    GEVERIFIEERD = "geverifieerd"
    BETWIST = "betwist"


def _supporters(note: Insight, all_notes: list[Insight]) -> list[Insight]:
    """Bevinding-kaartjes die deze claim steunen (inkomend: hun `supports` bevat note.id)."""
    return [c for c in all_notes
            if note.id in (c.supports or []) and c.kind == ClaimKind.BEVINDING]


def _contradictors(note: Insight, all_notes: list[Insight]) -> list[Insight]:
    """Kaartjes die deze claim tegenspreken (inkomend: hun `contradicts` bevat note.id)."""
    return [c for c in all_notes if note.id in (c.contradicts or [])]


def _legs(note: Insight, all_notes: list[Insight]) -> tuple[set[str], bool]:
    """(onafhankelijke bronnen die de claim steunen, of er een gemeten poot bij zit).
    Een bevinding die zelf gemeten is telt zijn eigen bron mee."""
    sources: set[str] = set()
    measured = False
    legs = list(_supporters(note, all_notes))
    if note.kind == ClaimKind.BEVINDING and note.evidence_type in _MEASURED:
        legs.append(note)
    for c in legs:
        if c.source:
            sources.add(c.source.strip().lower())
        if c.evidence_type in _MEASURED:
            measured = True
    return sources, measured


def strength(note: Insight, all_notes: list[Insight]) -> Strength:
    """Bereken de sterkte van een claim uit het bewijs-web. Tegenspraak overrulet alles."""
    if _contradictors(note, all_notes):
        return Strength.BETWIST
    sources, measured = _legs(note, all_notes)
    n = len(sources)
    if n >= 2 and measured:
        return Strength.GEVERIFIEERD
    if n >= 2:
        return Strength.BEVESTIGD
    if n >= 1:
        return Strength.ONDERSTEUND
    return Strength.ONBESLIST


def is_verified(note: Insight, all_notes: list[Insight]) -> bool:
    """De validiteitscheck: mag dit autonoom naar 'geverifieerd'?
    >=2 onafhankelijke bevindingen, >=1 gemeten, geen tegenspraak. Een standpunt (eigen claim)
    kan zelf nooit geverifieerd zijn — het erft sterkte van de bevindingen die het steunen,
    maar blijft een standpunt."""
    return strength(note, all_notes) == Strength.GEVERIFIEERD


def gaps(all_notes: list[Insight]) -> dict[str, list[Insight]]:
    """De twee waardevolle gat-lijsten:
      - 'signaal_zonder_bevinding' : een trend/mening die nog geen onderzoek kreeg (onderzoekskans)
      - 'standpunt_zonder_bevinding': een claim die we (nog) niet kunnen onderbouwen (publiceer-risico)
    Een claim heeft bewijs zodra minstens één bevinding hem steunt."""
    sig, stand = [], []
    for n in all_notes:
        if n.kind not in (ClaimKind.SIGNAAL, ClaimKind.STANDPUNT):
            continue
        heeft_bewijs = bool(_supporters(n, all_notes))
        if not heeft_bewijs:
            (sig if n.kind == ClaimKind.SIGNAAL else stand).append(n)
    return {"signaal_zonder_bevinding": sig, "standpunt_zonder_bevinding": stand}


def contested(all_notes: list[Insight]) -> list[Insight]:
    """Alle betwiste claims (er is een tegensprekend kaartje)."""
    return [n for n in all_notes if _contradictors(n, all_notes)]
