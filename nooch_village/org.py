"""Org-boom — lees-helpers over de governance-records voor de cirkel-/rolhiërarchie.

Puur lezen, nesting-proof: werkt op een lijst Record-achtige objecten (met .id, .parent, .type,
.archived). Een cirkel kan rollen én subcirkels bevatten; subcirkels nesten willekeurig diep.
De cockpit gebruikt dit voor de org-verkenner, breadcrumbs en de Roles-tab.
"""
from __future__ import annotations


def _is_circle(rec) -> bool:
    t = getattr(rec, "type", None)
    return getattr(t, "value", t) == "circle"


def _live(records) -> list:
    return [r for r in records if not getattr(r, "archived", False)]


def is_circle(rec) -> bool:
    return _is_circle(rec)


def roots(records) -> list:
    """Records zonder ouder (de wortelcirkel(s))."""
    return [r for r in _live(records) if not getattr(r, "parent", None)]


def children_of(records, parent_id: str) -> list:
    """Directe kinderen (rollen én subcirkels) van een cirkel."""
    return [r for r in _live(records) if getattr(r, "parent", None) == parent_id]


def roles_of(records, circle_id: str) -> list:
    """Directe rollen in een cirkel (geen subcirkels)."""
    return [r for r in children_of(records, circle_id) if not _is_circle(r)]


def subcircles_of(records, circle_id: str) -> list:
    """Directe subcirkels van een cirkel."""
    return [r for r in children_of(records, circle_id) if _is_circle(r)]


def descendants(records, node_id: str) -> list:
    """Alle nazaten (recursief), breadth-first. Cyclus-veilig."""
    out, seen, frontier = [], {node_id}, [node_id]
    while frontier:
        nxt = []
        for pid in frontier:
            for c in children_of(records, pid):
                if c.id in seen:
                    continue
                seen.add(c.id)
                out.append(c)
                nxt.append(c.id)
        frontier = nxt
    return out


def role_for_domain(records, domain: str):
    """De LEVENDE rol (of cirkel) die dit domein bezit, of None.

    Waarom dit bestaat: een rol-id is een naam die verhuist, een domein is het feit dat
    governance vastlegt — en G1 bewaakt dat een domein bij precies één rol ligt. Toen de
    compliance-rol van de noochville-subcirkel naar de Nooch-cirkel verhuisde, bleef overal het
    oude id `"compliance"` staan: de Tools-kaart verdween van de rol, en de wiki-zaaier zou zijn
    claimpagina's op het GEARCHIVEERDE record hebben gezet.

    Gearchiveerd telt daarom niet mee. Dat is precies het gat in `records.get(id) is None` als
    poort: een archief-record bestaat nog, dus die check zegt ja terwijl niemand de uitkomst ooit
    ziet. Vergelijken op naam, niet op aanwezigheid."""
    doel = " ".join((domain or "").split()).lower()
    if not doel:
        return None
    for r in _live(records):
        for d in (getattr(getattr(r, "definition", None), "domains", None) or []):
            if " ".join(str(d).split()).lower() == doel:
                return r
    return None


def breadcrumb(records, node_id: str) -> list[str]:
    """Pad van de wortel naar de node (lijst van ids, wortel eerst). Cyclus-veilig."""
    by_id = {r.id: r for r in records}
    chain, seen = [], set()
    cur = node_id
    while cur and cur in by_id and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = getattr(by_id[cur], "parent", None)
    return list(reversed(chain))
