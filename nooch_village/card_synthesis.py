"""Synthese-engine voor de kennisgraaf — puur, geen I/O.

Vindt twee soorten kaart-paren via TF-IDF-cosinus over de tekst:
- bridge-paren: verwant maar niet hetzelfde (gelijkenis in een middenband) → de creatieve link
  waar een niet-voor-de-hand-liggende hypothese uit ontstaat.
- duplicaat-paren: bijna identiek (hoge gelijkenis) → kandidaat om samen te voegen.

Werkt op kaartjes als dicts: {"id", "text", "links_to"}.
"""
from __future__ import annotations
import math
import re
from collections import Counter


def _toks(t: str) -> list[str]:
    return re.findall(r"[a-z]{4,}", (t or "").lower())


def _vectors(texts: list[str]) -> list[dict]:
    docs = [_toks(t) for t in texts]
    df: Counter = Counter()
    for doc in docs:
        for w in set(doc):
            df[w] += 1
    n = max(1, len(docs))
    vecs = []
    for doc in docs:
        tf = Counter(doc)
        ln = len(doc) or 1
        # gesmoothede idf (sklearn-stijl): + 1 zodat termen die in meerdere kaartjes voorkomen
        # niet op nul vallen — cruciaal bij een kleine kennisgraaf.
        vecs.append({w: (c / ln) * (math.log((1 + n) / (1 + df[w])) + 1) for w, c in tf.items()})
    return vecs


def _cos(a: dict, b: dict) -> float:
    keys = set(a) & set(b)
    num = sum(a[k] * b[k] for k in keys)
    da = math.sqrt(sum(x * x for x in a.values()))
    db = math.sqrt(sum(x * x for x in b.values()))
    return num / (da * db) if da and db else 0.0


def _pairs(cards: list[dict]) -> list[tuple]:
    vecs = _vectors([c.get("text", "") for c in cards])
    out = []
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            out.append((round(_cos(vecs[i], vecs[j]), 3), cards[i]["id"], cards[j]["id"]))
    out.sort(reverse=True)
    return out


def _already_linked(cards: list[dict], a: str, b: str) -> bool:
    by_id = {c["id"]: set(c.get("links_to") or []) for c in cards}
    return b in by_id.get(a, set()) or a in by_id.get(b, set())


def bridge_pairs(cards: list[dict], *, lo: float = 0.10, hi: float = 0.35) -> list[tuple]:
    """Verwante-maar-niet-gelijke paren (sim in [lo, hi]) die nog niet verbonden zijn.
    Sterkste verwantschap eerst. Elk: (sim, id_a, id_b)."""
    return [(s, a, b) for s, a, b in _pairs(cards)
            if lo <= s <= hi and not _already_linked(cards, a, b)]


def duplicate_pairs(cards: list[dict], *, threshold: float = 0.55) -> list[tuple]:
    """Bijna-identieke paren (sim >= threshold): kandidaat om samen te voegen."""
    return [(s, a, b) for s, a, b in _pairs(cards) if s >= threshold]


def graph_density(cards: list[dict]) -> dict:
    """Vitaliteit van de graaf: aantal kaartjes, links en gemiddelde gelijkenis."""
    n = len(cards)
    links = sum(len(c.get("links_to") or []) for c in cards)
    sims = [s for s, _, _ in _pairs(cards)] if n > 1 else []
    return {"cards": n, "links": links,
            "avg_similarity": round(sum(sims) / len(sims), 3) if sims else 0.0}
