"""Brok 6 — de Librarian stelt bewijs-links voor (en de mens bevestigt).

Een link leggen is een bewering ("deze bevinding bewijst dit standpunt"). Dat oordeel hoort bij de
mens (geen ja-knikker, geen valse corroboratie). De Librarian DOET de curatie-voorbereiding: hij
zoekt per claim-die-bewijs-mist de relevante bevindingen en hangt VOORSTELLEN klaar. De berekende
sterkte (knowledge.py) leeft op de BEVESTIGDE links, nooit op de voorstellen.

Pure suggester + een lichte 'beslist'-store (onthoudt bevestigd/verworpen zodat een afgewezen
voorstel nooit terugkomt). Geen LLM, geen spaced repetition — die kunnen later als laagjes erbovenop.
Zie docs/ONDERZOEK_kennismodel.md.
"""
from __future__ import annotations
import json
import os
import re

from nooch_village.insight import Insight, ClaimKind
from nooch_village.util import atomic_write_json


def _tokens(text: str) -> set[str]:
    """Inhoudswoorden (≥4 tekens) — kort genoeg ruis (de, het, een) valt vanzelf weg."""
    return {w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(w) >= 4}


def key_of(from_id: str, to_id: str) -> str:
    return f"{from_id}__{to_id}"


def suggest_links(notes: list[Insight], *, top_n: int = 3, min_overlap: int = 2) -> list[dict]:
    """Stel bewijs-links voor: welke BEVINDING zou welk STANDPUNT/SIGNAAL kunnen steunen.
    Relevantie = gedeelde inhoudswoorden, gewogen op zeldzaamheid (idf: een zeldzaam gedeeld woord
    weegt zwaarder dan 'schoenen'). Publiceer-risico (standpunt) eerst. Alleen 'supports' (tegenspraak
    leg je bewust met de hand). Geeft per voorstel {from_id, to_id, relation, reason, score}."""
    bevindingen = [n for n in notes if n.kind == ClaimKind.BEVINDING]
    targets = [n for n in notes if n.kind in (ClaimKind.STANDPUNT, ClaimKind.SIGNAAL)]
    if not bevindingen or not targets:
        return []

    # idf over alle claim-tokens (zeldzaam = informatief)
    import math
    docs = bevindingen + targets
    df: dict[str, int] = {}
    for n in docs:
        for w in _tokens(n.claim):
            df[w] = df.get(w, 0) + 1
    n_docs = len(docs)

    def idf(w: str) -> float:
        return math.log(1 + n_docs / (1 + df.get(w, 0)))

    # standpunt vóór signaal (publiceer-risico is het waardevolst)
    targets.sort(key=lambda t: 0 if t.kind == ClaimKind.STANDPUNT else 1)
    out: list[dict] = []
    for t in targets:
        tt = _tokens(t.claim)
        if not tt:
            continue
        scored = []
        for b in bevindingen:
            if t.id in (b.supports or []):
                continue                      # link bestaat al
            shared = tt & _tokens(b.claim)
            if len(shared) < min_overlap:
                continue
            score = round(sum(idf(w) for w in shared), 3)
            scored.append((score, b, shared))
        scored.sort(key=lambda x: -x[0])
        for score, b, shared in scored[:top_n]:
            woorden = ", ".join(sorted(shared)[:5])
            out.append({"from_id": b.id, "to_id": t.id, "relation": "supports",
                        "reason": f"delen: {woorden}", "score": score,
                        "from_claim": b.claim, "to_claim": t.claim})
    return out


class LinkProposals:
    """Lichte store die alleen BESLISTE voorstellen onthoudt (bevestigd/verworpen), zodat een
    afgewezen voorstel nooit terugkomt. Open voorstellen worden live berekend en hiertegen gefilterd."""

    def __init__(self, path: str):
        self.path = path
        self._decided: dict[str, str] = {}     # key -> "confirmed" | "rejected"
        if os.path.exists(path):
            try:
                self._decided = json.load(open(path))
            except Exception:
                self._decided = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._decided)

    def status(self, from_id: str, to_id: str) -> str | None:
        return self._decided.get(key_of(from_id, to_id))

    def is_decided(self, from_id: str, to_id: str) -> bool:
        return key_of(from_id, to_id) in self._decided

    def confirm(self, from_id: str, to_id: str) -> None:
        self._decided[key_of(from_id, to_id)] = "confirmed"
        self._save()

    def reject(self, from_id: str, to_id: str) -> None:
        self._decided[key_of(from_id, to_id)] = "rejected"
        self._save()


def open_proposals(notes: list[Insight], store: LinkProposals, *,
                   top_n: int = 3, limit: int = 25) -> list[dict]:
    """Live voorstellen, gefilterd tegen wat al beslist is. Sterkste relevantie eerst."""
    props = [p for p in suggest_links(notes, top_n=top_n)
             if not store.is_decided(p["from_id"], p["to_id"])]
    props.sort(key=lambda p: -p["score"])
    return props[:limit]
