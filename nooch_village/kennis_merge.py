"""kennis_merge — de merge-lus: ruim de al bestaande dubbele kaartjes op (founder 23 jul).

De voorkant-poort (kennis_dedup) voorkomt NIEUWE dubbelingen; deze lus ruimt de bestaande op. Gemeten:
15 tot 23 samenvoegbare clusters over de 337 kaartjes (bijna-woordelijke duo's zoals "EU Ecolabel koppelt
textiel aan de circulaire economie" x2). Werkwijze, met nul extra embedding-calls (de vectoren staan al in
de index):
  1. kandidaat-paren: lexicaal (woord-overlap >= lex_drempel) OF semantisch (cosinus over de opgeslagen
     embeddings >= sem_drempel).
  2. elk uniek paar langs de LLM-oordeler ('zelfde inzicht?') — dezelfde streng-check als de poort.
  3. bevestigde paren → clusters (union-find); per cluster wint de kaart met de meeste grounding (tie:
     de oudste) als TARGET, de rest gaat er append-only in op via NotesStore.merge_into (omkeerbaar: de
     bron wordt gearchiveerd met superseded_by, herkomst stapelt).

Pure kandidaat-/cluster-logica + injecteerbare reason_fn (testbaar zonder netwerk). Toepassen loopt
uitsluitend via merge_into. `max_oordeel` begrenst het aantal LLM-calls per run (de rest wordt gemeld,
niet stil afgekapt)."""
from __future__ import annotations

import itertools
import re

from nooch_village.kennis_dedup import _llm_zelfde

_STOP = frozenset(
    "de het een en of in op te van voor met is dat die dit zijn niet ook al maar aan als je we ze "
    "the a an of to and is are for with that this on in at be by as we they it their our not no than "
    "geen bij naar uit over onder tussen wordt worden om dan want dus nog wel zo per via schoen schoenen "
    "nooch".split())


def _tok(claim: str) -> frozenset:
    return frozenset(w for w in re.split(r"[\W_]+", (claim or "").lower())
                     if len(w) > 3 and w not in _STOP)


def _jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def kandidaat_paren(actief: list, vecs: dict, *, lex_drempel: float, sem_drempel: float) -> list[tuple]:
    """Alle unieke kandidaat-paren (id_a, id_b, reden) op lexicale OF semantische gelijkenis."""
    from nooch_village.kennis_embeddings import cosine
    toks = {a.id: _tok(a.claim) for a in actief}
    ids = [a.id for a in actief]
    paren: dict[frozenset, str] = {}
    for i, j in itertools.combinations(range(len(ids)), 2):
        ia, ib = ids[i], ids[j]
        lex = _jaccard(toks[ia], toks[ib])
        if lex >= lex_drempel:
            paren[frozenset((ia, ib))] = f"lexicaal {lex:.2f}"
            continue
        va, vb = vecs.get(ia), vecs.get(ib)
        if va and vb:
            sem = cosine(va, vb)
            if sem >= sem_drempel:
                paren[frozenset((ia, ib))] = f"semantisch {sem:.2f}"
    return [(tuple(p)[0], tuple(p)[1], reden) for p, reden in paren.items()]


def _target(cluster_ids: list[str], byid: dict) -> str:
    """Wie wint de merge: meeste grounding (aflopend), bij gelijkspel de oudste kaart (created_at
    oplopend) als stabiel anker."""
    return sorted(
        cluster_ids,
        key=lambda nid: (-int(getattr(byid[nid], "grounding_count", 0) or 0),
                         str(getattr(byid[nid], "created_at", "") or "")),
    )[0]


def vind_clusters(notes, *, reason_fn=None, data_dir: str = "data",
                  lex_drempel: float = 0.5, sem_drempel: float = 0.82,
                  max_oordeel: int = 80) -> dict:
    """Vind bevestigde merge-clusters. Geeft {clusters: [{target, target_claim, sources:[{id,claim}],
    reden}], kandidaat_paren, beoordeeld, afgekapt}. Past niets toe."""
    actief = [a for a in notes.all() if not a.archived]
    byid = {a.id: a for a in actief}

    # Opgeslagen vectoren (nul nieuwe API-calls); ontbreekt de index, dan puur lexicaal.
    vecs: dict = {}
    try:
        from nooch_village.kennis_embeddings import EmbeddingStore
        st = EmbeddingStore(f"{data_dir}/kennis_embeddings.json")
        vecs = {nid: rec.get("v") for nid, rec in st.items() if rec.get("v") and nid in byid}
    except Exception:
        vecs = {}

    paren = kandidaat_paren(actief, vecs, lex_drempel=lex_drempel, sem_drempel=sem_drempel)
    afgekapt = max(0, len(paren) - max_oordeel)
    paren = paren[:max_oordeel]

    # Union-find over de door de LLM bevestigde paren.
    par: dict[str, str] = {}

    def vind(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    beoordeeld = 0
    for ia, ib, _reden in paren:
        beoordeeld += 1
        if _llm_zelfde(byid[ia].claim, byid[ib].claim, reason_fn) == "zelfde":
            par[vind(ia)] = vind(ib)

    groepen: dict[str, list[str]] = {}
    for nid in list(par):
        groepen.setdefault(vind(nid), []).append(nid)

    clusters = []
    for leden in groepen.values():
        if len(leden) < 2:
            continue
        tgt = _target(leden, byid)
        clusters.append({
            "target": tgt,
            "target_claim": byid[tgt].claim,
            "sources": [{"id": nid, "claim": byid[nid].claim} for nid in leden if nid != tgt],
            "reden": "LLM-bevestigd zelfde",
        })
    return {"clusters": clusters, "kandidaat_paren": len(paren) + afgekapt,
            "beoordeeld": beoordeeld, "afgekapt": afgekapt}


def pas_merge_toe(notes, clusters: list[dict], *, by: str = "kennis-onderhoud") -> dict:
    """Voer de merges uit via NotesStore.merge_into (omkeerbaar spoor). Geeft stats terug."""
    gemerged = kaarten_weg = 0
    for c in clusters:
        tgt = c["target"]
        doel = notes.get(tgt)
        if doel is None:
            continue
        for s in c.get("sources", []):
            try:
                if notes.merge_into(tgt, s["id"], doel.claim, by=by) is not None:
                    kaarten_weg += 1
            except Exception:
                pass
        gemerged += 1
    return {"clusters_gemerged": gemerged, "kaarten_opgeruimd": kaarten_weg}
