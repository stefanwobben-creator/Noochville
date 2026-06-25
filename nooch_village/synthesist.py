"""Synthesist-runner: laat de kennisgraaf ademen.

Pakt het sterkste nog-niet-verbonden bridge-paar, vraagt de synthese-skill om de emergente
hypothese, en schrijft die als nieuw kaartje weg dat naar beide ouders linkt. Zo ontstaan
creatieve verbanden tussen losse inzichten. Mens-gedraaid (LLM-kosten), via `village synthesize`.
"""
from __future__ import annotations
import uuid

from nooch_village.card_synthesis import bridge_pairs, graph_density
from nooch_village.insight import Insight, GroundingStatus


def _cards(notes) -> list[dict]:
    out = []
    for n in notes.all():
        out.append({"id": n.id, "text": (n.claim or "") + " " + (n.grounds or ""),
                    "links_to": list(n.links_to or [])})
    return out


def _already_bridged(notes, a: str, b: str) -> bool:
    """Bestaat er al een synthese-kaartje dat zowel a als b verbindt?"""
    for n in notes.all():
        lt = set(n.links_to or [])
        if a in lt and b in lt:
            return True
    return False


def synthesize_once(notes, context, *, lo: float = 0.10, hi: float = 0.35) -> dict | None:
    """Eén creatieve link. Retourneert {id, synthese, parents} of None (geen paar/geen LLM)."""
    from nooch_village.skills_impl.synthesize import SynthesizeCardsSkill
    cards = _cards(notes)
    by_id = {c["id"]: c for c in cards}
    for _sim, a, b in bridge_pairs(cards, lo=lo, hi=hi):
        if _already_bridged(notes, a, b):
            continue
        res = SynthesizeCardsSkill().run(
            {"card_a": by_id[a]["text"], "card_b": by_id[b]["text"]}, context)
        if not isinstance(res, dict) or "error" in res:
            return None                                   # fail-closed: geen LLM → stop
        nid = "syn_" + uuid.uuid4().hex[:9]
        notes.add(Insight(
            id=nid, claim=res["synthese"], source="synthesist",
            grounds=res.get("waarom") or None, status=GroundingStatus.UNRESOLVED,
            tags=["synthese"], links_to=[a, b]))
        return {"id": nid, "synthese": res["synthese"], "parents": [a, b]}
    return None


def synthesize_round(notes, context, n: int = 3) -> list[dict]:
    """Tot n creatieve links in één ronde."""
    made = []
    for _ in range(max(1, n)):
        r = synthesize_once(notes, context)
        if not r:
            break
        made.append(r)
    return made


def density(notes) -> dict:
    return graph_density(_cards(notes))
