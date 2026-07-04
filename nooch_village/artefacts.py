"""Artefacten — de domein-logica bovenop de AttachmentStore (geen aparte opslag!).

Een *artefact* is een attachment van soort note | policy | tool. Dit module beantwoordt de twee
vragen die opslag niet hoort te weten:

1. **Wie mag schrijven?** — `can_write_artefact`: alleen de huidige vervuller van de eigenaar-rol,
   of de Circle Lead van de omvattende cirkel. Identiek voor mens (person) en AI-vervuller
   (persona): de `Filler`-abstractie maakt ze niet te onderscheiden — dát is precies waarom
   "AI mag hetzelfde als een mens" gratis klopt.
2. **Wat erft een rol?** — `own_and_inherited`: eigen artefacten + die van alle voorouders langs
   de breadcrumb waar `inherit=True` en `status="active"`, elk getagd met hun herkomst.

De data leeft op één plek (attachments.json via AttachmentStore); dit is puur leeslogica +
autorisatie, geen tweede waarheid.
"""
from __future__ import annotations

from nooch_village import org


def _name(rec) -> str:
    """Weergavenaam van een record voor het herkomst-pad; valt terug op de id."""
    if rec is None:
        return ""
    d = getattr(rec, "definition", None)
    return (getattr(d, "name", "") or "").strip() or getattr(rec, "id", "")


def _circle_of(owner_role_id: str, records) -> str | None:
    """De omvattende cirkel van een eigenaar: een cirkel → zichzelf; een rol → zijn ouder.
    Spiegelt `resolve_circle_id` maar zonder de "ii:"-prefix (een artefact-eigenaar is altijd
    een echt rol-/cirkel-record)."""
    rec = records.get(owner_role_id)
    if rec is None:
        return None
    return owner_role_id if org.is_circle(rec) else getattr(rec, "parent", None)


def requires_governance_ref(owner_role_id: str, records) -> bool:
    """True als de eigenaar de anchor-cirkel is (parent is None). Elke schrijfactie op de anchor
    vereist een niet-lege governance_ref (audittrail naar het governance-besluit)."""
    rec = records.get(owner_role_id)
    return rec is not None and not getattr(rec, "parent", None)


def can_write_artefact(actor_type: str, actor_id: str, owner_role_id: str,
                       records, assignments) -> bool:
    """Mag deze actor artefacten van `owner_role_id` aanmaken/bewerken/archiveren?

    Regel (identiek voor person en persona): actor is huidige filler van de eigenaar-rol, OF
    filler van de Circle Lead-rol van de omvattende cirkel. Geërfde artefacten zijn nooit
    schrijfbaar — daar is `owner_role_id` niet de eigen rol, dus valt de check vanzelf weg.
    """
    if actor_type not in ("person", "persona") or not actor_id or not owner_role_id:
        return False
    rec = records.get(owner_role_id)
    if rec is None:
        return False
    if any(f.type == actor_type and f.id == actor_id
           for f in assignments.fillers_of(owner_role_id, rec)):
        return True
    circle_id = _circle_of(owner_role_id, records)
    if circle_id:
        lead_role = f"{circle_id}__circle_lead"
        if any(f.type == actor_type and f.id == actor_id
               for f in assignments.fillers_of(lead_role, records.get(lead_role))):
            return True
    return False


def own_and_inherited(role_id: str, kind: str, records, store) -> dict:
    """Eigen + geërfde artefacten van één soort voor een rol/cirkel.

    Retour: {"own": [Attachment, ...], "inherited": [{"artefact", "origin_id", "origin_name"}, ...]}.
    'own' = actieve artefacten op de rol zelf. 'inherited' = actieve, inherit=True artefacten van
    elke voorouder langs de breadcrumb (wortel eerst), getagd met de herkomst-rol.
    """
    own = store.list(role_id, kind)  # list() laat archief al weg
    chain = org.breadcrumb(records.all(), role_id)  # [wortel, ..., role_id]
    inherited: list[dict] = []
    for anc_id in chain[:-1]:  # alle voorouders (niet de rol zelf)
        rec = records.get(anc_id)
        origin_name = _name(rec)
        for a in store.list(anc_id, kind):
            if a.inherit:
                inherited.append({"artefact": a, "origin_id": anc_id, "origin_name": origin_name})
    return {"own": own, "inherited": inherited}
