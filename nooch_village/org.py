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
