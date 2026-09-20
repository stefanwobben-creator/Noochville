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


def levende_rollen(records) -> list:
    """De rollen die meedoen: levend, geen cirkel. Een cirkel heeft geen handen (harde regel 7),
    dus hij senst ook niet en hij voert ook niets uit — zijn leden doen dat.

    Stond tot 20 september 2026 in `villageraad.py` als `rollen()`. Die module is opgeheven; deze
    twee helpers niet, want ze gaan over de ORG-boom en niet over een council-pass. `waarde_audit`
    en `views/vangst` waren altijd al hun andere lezers."""
    return [r for r in _live(records) if not _is_circle(r)]


def naam_van(rec) -> str:
    """De weergavenaam van een record: zijn `definition.name`, anders zijn id."""
    return getattr(getattr(rec, "definition", None), "name", "") or getattr(rec, "id", "")


def unieke_namen(recs: list, alle: list) -> dict:
    """Rol-id → leesbare naam, uniek gemaakt. Drie Circle Leads die allemaal "Circle Lead" heten
    zijn in een verslag of een autocomplete niet uit elkaar te houden; een dubbele naam krijgt
    daarom de cirkel erachter.

    `alle` is de VOLLEDIGE recordlijst en niet alleen `recs`: de ouder van een rol is een cirkel,
    en cirkels zitten per definitie niet in `recs`."""
    per_id = {getattr(r, "id", ""): r for r in alle}
    namen = [naam_van(r) for r in recs]
    uit = {}
    for rec, naam in zip(recs, namen):
        if namen.count(naam) > 1:
            ouder = per_id.get(getattr(rec, "parent", "") or "")
            if ouder is not None:
                naam = f"{naam} ({naam_van(ouder)})"
        uit[getattr(rec, "id", "")] = naam
    return uit


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


def role_with_skill(records, skill: str):
    """De LEVENDE rol die dit MIDDEL houdt, of None.

    Het zusje van `role_for_domain`, en om dezelfde reden: een rol-id is een naam die verhuist of
    verdwijnt, het middel is wat governance in het DNA vastlegt. Waar een domein zegt wie ergens
    OVER gaat, zegt een skill wie iets KAN — en voor werk dat moet worden uitgevoerd is dat de
    juiste vraag.

    Gearchiveerd en slapend tellen allebei niet mee. Gearchiveerd is weg; een slapende rol staat er
    nog wel, maar draait geen thread en pakt niets op, dus werk dat je hem geeft blijft liggen.

    Geen houder → None, en de aanroeper besluit wat dat betekent. Werk toewijzen aan een rol die
    het niet kan is erger dan zichtbaar zeggen dat er niemand is."""
    doel = " ".join((skill or "").split()).lower()
    if not doel:
        return None
    for r in _live(records):
        if getattr(r, "slaapt", False):
            continue
        for s in (getattr(getattr(r, "definition", None), "skills", None) or []):
            if " ".join(str(s).split()).lower() == doel:
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
