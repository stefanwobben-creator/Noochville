"""Matcher: past een AI-skill bij een accountability? Voedt het cadeau-icoon op de rolpagina.

Drie lagen, goedkoop-eerst en fail-closed:
  1. lexicaal      — tokenoverlap of substring (altijd aan, deterministisch).
  2. concept       — gedeeld concept-cluster (offline 'semantiek', bv. code ~ feature ~ bouwen).
  3. semantisch    — een LLM-oordeel, vooraf berekend en gecachet (data/ai_match_cache.json).
                     Geen key → laag 3 doet niets; we vallen terug op 1+2.

De render leest alleen de cache (snel, geen netwerk in de request). `refresh_semantic` vult de
cache op de achtergrond met een geinjecteerde `ask`-callable, zodat dit niets weet van llm.py.
"""
from __future__ import annotations
import json
import os
import re

from nooch_village.util import atomic_write_json

_STOP = {"the", "a", "an", "of", "and", "to", "for", "in", "on", "new", "with", "your",
         "de", "het", "een", "van", "en", "te", "met", "der", "die", "dat", "ai"}

# Concept-clusters: woorden die naar hetzelfde werk verwijzen, over NL/EN heen. Bewust klein en
# domein-gericht; de echte breedte komt later van de semantische laag.
_CONCEPTS: list[set[str]] = [
    {"code", "coding", "coderen", "programmeren", "develop", "development", "ontwikkelen",
     "feature", "features", "functie", "functionaliteit", "build", "building", "bouwen", "software"},
    {"bug", "bugs", "fix", "fixing", "repareren", "debug", "debuggen", "test", "tests", "testing",
     "testscript", "testscripts", "rootcause", "rootcauses", "oorzaak", "qa", "quality", "kwaliteit"},
    {"performance", "performant", "snelheid", "speed", "optimize", "optimizing", "optimization",
     "optimaliseren", "optimalisatie", "load", "caching"},
    {"content", "copy", "tekst", "teksten", "text", "write", "writing", "schrijven", "schrijft",
     "artikel", "blog", "redactie", "redactioneel"},
    {"plan", "planning", "plannen", "schedule", "scheduling", "roadmap", "backlog", "prioriteren"},
    {"design", "ontwerp", "ontwerpen", "ux", "ui", "visual", "vormgeving", "wireframe"},
    {"seo", "keyword", "keywords", "zoekwoord", "zoekwoorden", "search", "ranking", "vindbaarheid"},
    {"data", "analyse", "analytics", "analysis", "meten", "metrics", "rapportage", "report", "dashboard"},
]


def _toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z]+", (s or "").lower()) if len(w) > 2 and w not in _STOP}


def lexical_match(acc: str, skill: str) -> bool:
    at, sk = _toks(acc), _toks(skill)
    if at & sk:
        return True
    return bool(skill) and skill.lower() in (acc or "").lower()


def concept_match(acc: str, skill: str) -> bool:
    at, sk = _toks(acc), _toks(skill)
    for cluster in _CONCEPTS:
        if (at & cluster) and (sk & cluster):
            return True
    return False


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _key(acc: str, skill: str) -> str:
    return f"{_norm(acc)}|{_norm(skill)}"


class MatchCache:
    """Vooraf-berekende semantische oordelen. Ontbreekt een paar, dan val je terug op lexicaal+concept."""

    def __init__(self, path: str):
        self.path = path
        self._d: dict[str, bool] = {}
        if os.path.exists(path):
            try:
                self._d = {k: bool(v) for k, v in json.load(open(path)).items()}
            except Exception:
                self._d = {}

    def get(self, acc: str, skill: str):
        return self._d.get(_key(acc, skill))

    def set(self, acc: str, skill: str, value: bool) -> None:
        self._d[_key(acc, skill)] = bool(value)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._d)


def is_match(acc: str, skill: str, cache: MatchCache | None = None) -> bool:
    """Eindoordeel. Een gecachet semantisch oordeel wint (ook een expliciete 'nee'); anders
    lexicaal of concept."""
    if cache is not None:
        v = cache.get(acc, skill)
        if v is not None:
            return v
    return lexical_match(acc, skill) or concept_match(acc, skill)


def suggest(personas, acc_text: str, attached: set, cache: MatchCache | None = None):
    """(persona, skill)-paren die bij deze accountability passen en nog niet gekoppeld zijn."""
    out = []
    for p in personas:
        for sk in (getattr(p, "skills", None) or []):
            if (p.id, sk) in attached:
                continue
            if is_match(acc_text, sk, cache):
                out.append((p, sk))
    return out


def refresh_semantic(pairs, ask, cache: MatchCache, *, skip_cached: bool = False,
                     progress=None) -> int:
    """Vul de cache met semantische oordelen. `pairs` = iterable van (acc_text, skill);
    `ask(acc, skill) -> bool|None` is een geinjecteerd LLM-poortje (None = onbeslist, niet cachen).
    `skip_cached` slaat al beoordeelde paren over (resumable). `progress(i, total, acc, skill)`
    wordt vóór elke beoordeling aangeroepen. Geeft het aantal nieuw bepaalde paren terug."""
    pairs = list(pairs)
    total = len(pairs)
    n = 0
    for i, (acc, skill) in enumerate(pairs, 1):
        if progress:
            progress(i, total, acc, skill)
        if skip_cached and cache.get(acc, skill) is not None:
            continue
        verdict = ask(acc, skill)
        if verdict is None:
            continue
        cache.set(acc, skill, bool(verdict))
        n += 1
    if n:
        cache.save()
    return n
