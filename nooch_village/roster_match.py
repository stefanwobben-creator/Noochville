"""Hulpfuncties voor roster-analyse: term-signaturen en dekkingsberekening.

Deterministisch, geen LLM, geen I/O.
De ADD_ROLE/AMEND_ROLE-beslissing zit nu in classify_gap (gap_classifier.py).
"""
from __future__ import annotations
import re

_NL_STOP = frozenset([
    "de", "het", "een", "van", "in", "op", "te", "en", "of", "is", "zijn",
    "wordt", "aan", "voor", "met", "uit", "bij", "als", "naar", "over", "door",
    "om", "niet", "maar", "ook", "dan", "dit", "dat", "wel", "nog", "kan",
    "heeft", "hebben", "meer", "alle", "elke", "geen", "die", "er", "zo", "nu",
    "al", "tot", "wat", "wie", "hoe", "waar", "werd", "hun", "hem", "haar",
    "ons", "ze", "hij", "zij", "wij", "mij", "wil", "mag", "moet", "mogen",
    "moeten", "willen", "kunnen", "zal", "zou", "mee", "per", "net", "iets",
    "altijd", "nooit", "echt", "heel", "veel", "even", "toch", "juist",
    "omdat", "zodat", "terwijl", "daarna", "daarvoor", "worden", "via",
    "reeds", "zelf", "eigen", "huidige", "zelfde", "andere", "nieuwe",
])
_EN_STOP = frozenset([
    "the", "a", "an", "of", "in", "on", "to", "and", "or", "is", "are", "was",
    "were", "be", "been", "for", "with", "from", "by", "at", "as", "not", "but",
    "also", "than", "this", "that", "it", "its", "we", "our", "they", "their",
    "he", "she", "his", "her", "can", "will", "would", "should", "have", "has",
    "had", "do", "does", "did", "all", "each", "no", "one", "so", "now", "even",
    "just", "then", "after", "before", "while", "new", "own", "same", "other",
    "via", "per", "any", "such", "into", "more", "most", "some",
])
_STOP = _NL_STOP | _EN_STOP
_TOKEN_RE = re.compile(r"[a-z][a-z\-]+")


def gap_signature(desc: str) -> frozenset[str]:
    """Extraheer betekenisdragende termen: lowercase, min len 4, geen stopwoorden."""
    tokens = _TOKEN_RE.findall(desc.lower())
    return frozenset(t for t in tokens if len(t) >= 4 and t not in _STOP)


def role_signature(record) -> frozenset[str]:
    """Combineer purpose + accountabilities + domeinen + skills tot een termset."""
    d = record.definition
    parts = [d.purpose] + d.accountabilities + d.domains + d.skills
    tokens = _TOKEN_RE.findall(" ".join(parts).lower())
    return frozenset(t for t in tokens if len(t) >= 4 and t not in _STOP)


def best_coverage(gap: frozenset[str], records) -> float:
    """Recall van gat-termen over de best-dekkende niet-gearchiveerde rol."""
    if not gap or records is None:
        return 0.0
    best = 0.0
    for rec in records.all():
        if rec.archived:
            continue
        cov = len(gap & role_signature(rec)) / len(gap)
        if cov > best:
            best = cov
    return best


def _role_id_from_gap(gap: frozenset[str]) -> str:
    """Leesbare snake_case role_id van de top-3 gat-termen (langst eerst)."""
    terms = sorted(gap, key=lambda t: (-len(t), t))[:3]
    return "_".join(terms)


def _purpose_from_gap(gap: frozenset[str]) -> str:
    terms = sorted(gap, key=lambda t: (-len(t), t))[:4]
    return "Beheert en bewaakt " + ", ".join(terms) + "."
