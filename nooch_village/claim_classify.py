"""Eerste-pas classificatie van een kaartje naar zijn SOORT (ClaimKind).

Heuristiek, geen LLM (fail-closed bruikbaar zonder netwerk). Geeft None als het niet eenduidig is
→ die kaartjes gaan naar mens-review (de mens beslist, geen ja-knikker). Definities horen NIET in de
kennislaag maar in het Lexicon; `looks_like_definition` markeert ze zodat de migratie ze apart legt.

Bewust conservatief: liever None (mens beslist) dan een verkeerde soort stil toekennen.
Zie docs/ONDERZOEK_kennismodel.md en tools/knowledge_model_experiment.py (waar deze logica is getest).
"""
from __future__ import annotations
import re

from nooch_village.insight import ClaimKind, EvidenceType

_KADER = re.compile(r"\b(directive|richtlijn|wet|wetgeving|verplicht|mag niet|verboden|"
                    r"certific|iso\s?\d|astm|en\s?\d{3,}|gots|brl|norm(en)?|standaard|"
                    r"green claims|reglement|compliance|aansprakelijk|keurmerk)\b", re.I)
_SIGNAAL = re.compile(r"\b(zoekvolume|zoekterm|trend|stijg|daal|populair|viral|sentiment|opinie|"
                      r"mensen (vinden|zeggen|denken|willen)|reddit|nieuws|artikel|"
                      r"waitlist|survey|enqu|respondent|geïnteresseerd|interesse|"
                      r"volgers|linkedin|piek|aandacht|wint aan)\b", re.I)
_BEVINDING = re.compile(r"\b(studie|onderzoek|meta-?analyse|rct|gerandomiseerd|cohort|"
                        r"data toont|gemeten|meet|degradeer|correlat|proefpersonen|n=|"
                        r"peer-?review|wetenschappelijk|aangetoond|experiment|%|procent|"
                        r"dagen|weken|maanden)\b", re.I)
_STANDPUNT = re.compile(r"\b(wij|we|onze|nooch|ik geloof|wij vinden|onze missie|hoort|"
                        r"zou moeten|beter|moreel|verantwoord)\b", re.I)
_DEFINITIE = re.compile(r"\b(is per definitie|betekent|wordt gedefinieerd|definieert|"
                        r"verwijst naar|is een soort|valt onder|staat voor)\b", re.I)


def looks_like_definition(text: str) -> bool:
    """Definitie/taalafspraak → hoort in het Lexicon, niet in de kennislaag."""
    return bool(_DEFINITIE.search(text or ""))


def classify_kind(claim: str, evidence_type: str | None = None,
                  source: str | None = None) -> ClaimKind | None:
    """Bepaal de soort. Geeft None bij twijfel (ambigu, of past nergens) → mens-review.
    evidence_type is een sterk hulpsignaal: measured/peer_reviewed → bevinding; claimed → standpunt;
    'reported' is bewust geen soort (een bron meldt iets, maar welke soort?) → val terug op de tekst."""
    t = claim or ""
    et = (evidence_type or "").lower()
    src = (source or "")

    # evidence_type-hints (sterk, maar niet allesbepalend)
    et_hint: ClaimKind | None = None
    if et in (EvidenceType.MEASURED, EvidenceType.PEER_REVIEWED, EvidenceType.CERTIFIED):
        et_hint = ClaimKind.BEVINDING
    elif et == EvidenceType.CLAIMED:
        et_hint = ClaimKind.STANDPUNT          # let op: alleen als de tekst dat niet tegenspreekt

    hits: set[ClaimKind] = set()
    if _KADER.search(t) or re.search(r"\b(EN|ISO|ASTM|GOTS|BRL)\b", src):
        hits.add(ClaimKind.KADER)
    if _BEVINDING.search(t):
        hits.add(ClaimKind.BEVINDING)
    if _SIGNAAL.search(t):
        hits.add(ClaimKind.SIGNAAL)
    if _STANDPUNT.search(t):
        hits.add(ClaimKind.STANDPUNT)

    # Kader is het sterkste, eenduidige signaal (een norm is een norm).
    if hits == {ClaimKind.KADER}:
        return ClaimKind.KADER
    if ClaimKind.KADER in hits and len(hits) > 1:
        hits.discard(ClaimKind.KADER)          # 'voldoet aan EN13432' = standpunt/bevinding óver een norm

    # evidence_type breekt een gelijkspel of beslist als de tekst zwijgt.
    if not hits and et_hint:
        return et_hint
    if len(hits) == 1:
        return next(iter(hits))
    if et_hint in hits:
        return et_hint
    # ambigu (meerdere, geen et-hint die kiest) of leeg → onbeslist
    return None
