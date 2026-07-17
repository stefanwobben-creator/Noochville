from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from typing import Self
from pydantic import BaseModel, Field, model_validator


class GroundingStatus(StrEnum):
    UNRESOLVED = "unresolved"
    SUPPORTED = "supported"
    VERIFIED = "verified"


class EvidenceType(StrEnum):
    CLAIMED = "claimed"
    REPORTED = "reported"
    MEASURED = "measured"
    CERTIFIED = "certified"
    PEER_REVIEWED = "peer_reviewed"


class ClaimKind(StrEnum):
    """De SOORT van een kaartje (verandert nooit; alleen de sterkte evolueert).
    Zie docs/ONDERZOEK_kennismodel.md.
      - SIGNAAL   : trend/mening/nieuws; gaat over aandacht/cultuur. Roept een vraag op.
      - BEVINDING : empirie; gaat over de wereld. Beantwoordt een vraag.
      - KADER     : norm/regel; bindend (draagt zijn eigen bewijsdrempel).
      - STANDPUNT : wat Nooch zelf beweert/wil claimen; beweerd, niet bewezen (erft sterkte).
    None = (nog) onbeslist → mens-review (definities horen niet hier maar in het Lexicon)."""
    SIGNAAL = "signaal"
    BEVINDING = "bevinding"
    KADER = "kader"
    STANDPUNT = "standpunt"


def _filled(value: str | None) -> bool:
    return value is not None and value.strip() != ""


class Insight(BaseModel):
    id: str
    claim: str
    source: str
    word: str | None = None
    source_date: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    grounding_count: int = 1
    last_updated_at: datetime | None = None
    links_to: list[str] = Field(default_factory=list)
    # Getypeerde bewijs-relaties (kennislaag): welke claims dit kaartje STEUNT of TEGENSPREEKT.
    # Een bevinding die een standpunt steunt zet het standpunt-id in `supports`. Sterkte wordt
    # hieruit berekend (knowledge.py), niet opgeslagen — zo kan hij niet verouderen.
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: GroundingStatus = GroundingStatus.UNRESOLVED
    kind: ClaimKind | None = None      # soort (signaal/bevinding/kader/standpunt); None = onbeslist
    grounds: str | None = None
    warrant: str | None = None
    qualifier: str | None = None
    rebuttal: str | None = None
    evidence_type: EvidenceType | None = None
    reference: str | None = None
    concept_id: str | None = None
    # Herkomst-type van de bron (kennisbank-trustladder: peer_reviewed | certificate |
    # internal_data | survey | expert_opinion | media | advocacy | internal_judgment | unknown).
    # Optioneel: oudere kaartjes vallen terug op evidence_type (zie kennisbank.atom_trust).
    provenance: str | None = None
    # Woozle-guard: expliciete onafhankelijkheidsgroep. Leeg = afgeleid uit de genormaliseerde
    # bron; alleen zetten als kaarten stiekem dezelfde onderliggende bron delen.
    independence_group: str | None = None
    # Samengestelde kaart (kennisbank-addendum A): een enumeratie/proces/tabel is ÉÉN
    # kenniseenheid — claim = de kop, body = de stappen/regels. Atomiciteit heeft een plafond.
    body: str | None = None
    # Curatie (addendum C, append-only): archiveren i.p.v. wissen (terugdraaibaar), en een
    # merge-kaart verwijst naar zijn originelen — die blijven gearchiveerd bewaard.
    archived: bool = False
    merged_from: list[str] = Field(default_factory=list)
    # Atomiser-versionering (reatomise-fix): met welke atomiser-versie dit atoom gemaakt is
    # (None = pre-versionering, dus kandidaat voor re-atomiseren). superseded_by verwijst naar
    # de nieuwe, schone atomen die dit atoom bij een migratie vervingen (append-only spoor).
    atomiser_version: int | None = None
    superseded_by: list[str] = Field(default_factory=list)
    # Bewerken-met-historie (layout PR-2, append-only): een correctie van een extractie-fout
    # overschrijft niet stil — de vorige claim/body gaat hierheen. Elk item: {claim, body, at}.
    edit_history: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_grounding(self) -> Self:
        if self.status == GroundingStatus.SUPPORTED:
            if not _filled(self.grounds):
                raise ValueError("SUPPORTED vereist een gevuld 'grounds'-veld")
        elif self.status == GroundingStatus.VERIFIED:
            missing = [
                name for name, val in [
                    ("grounds", self.grounds),
                    ("warrant", self.warrant),
                    ("rebuttal", self.rebuttal),
                ]
                if not _filled(val)
            ]
            if missing:
                raise ValueError(
                    f"VERIFIED vereist gevulde velden: {', '.join(missing)}"
                )
            if self.evidence_type is None:
                raise ValueError("VERIFIED vereist een gezet evidence_type")
            if self.evidence_type == EvidenceType.CLAIMED:
                raise ValueError(
                    "VERIFIED staat EvidenceType.CLAIMED niet toe: "
                    "een eigen claim kan nooit verified worden"
                )
        return self
