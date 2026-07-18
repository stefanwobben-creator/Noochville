"""De skills-catalogus: wat kan het dorp al, en waarvoor moet er tooling komen?

Leeswerk op bestaande bronnen — deze module schrijft nooit. Drie blokken:

1. **Uitvoerbaar** — skills met een implementatie in de registry: mensentaal-label, of ze een
   sleutel nodig hebben, welke rollen/accountabilities ze voeren (DNA én koppelingen), en de
   domein-/zwaar-markering uit `skill_meta`.
2. **Genoemd maar niet gedekt** — capabilities die in rol-DNA of in een koppeling staan zonder
   implementatie, plus de dode-capability-audit: in code aangeroepen zonder grant.
3. **Gewenst** — means-gaps uit de human inbox: de bouwlijst voor nieuwe tooling.

De dode-capability-audit draait hier STATISCH (broncode-analyse over de klasse-MRO), niet op
levende inwoners: het cockpit-proces start geen threads. Zelfde regex als
`Inhabitant.referenced_capabilities`, maar zonder instantie.
"""
from __future__ import annotations

import inspect
import logging
import re

from nooch_village import acc_ids, skill_labels, skill_meta, skill_links

log = logging.getLogger("village.skills_catalog")

_USE_SKILL_RE = re.compile(r'use_skill\(\s*["\']([^"\']+)["\']')


# ── Bronnen ──────────────────────────────────────────────────────────────────

def _registry():
    from nooch_village.registry_factory import shared_registry
    return shared_registry()


def _class_map() -> dict:
    """CLASS_MAP uit village.py — fail-soft: zonder deze map vervalt alleen de dode-audit."""
    try:
        from nooch_village.village import CLASS_MAP
        return dict(CLASS_MAP)
    except Exception as exc:
        log.warning("skills_catalog: CLASS_MAP niet beschikbaar (%s); dode-audit overgeslagen", exc)
        return {}


def referenced_capabilities(cls) -> set[str]:
    """Welke skills roept deze inwoner-klasse met een letterlijke naam aan?

    Statisch afgeleid uit de broncode van de hele MRO — dezelfde afleiding als
    `Inhabitant.referenced_capabilities`, maar zonder een levende inwoner.
    """
    found: set[str] = set()
    for base in getattr(cls, "__mro__", ()):
        if getattr(base, "__module__", "") == "builtins":
            continue
        try:
            found.update(_USE_SKILL_RE.findall(inspect.getsource(base)))
        except (OSError, TypeError):
            continue
    return found


# ── Wie voert welk middel ────────────────────────────────────────────────────

def gebruikers(records, ai) -> dict[str, list[dict]]:
    """Per capability: welke rollen voeren hem, via welke route.

    route = "dna" (grant via governance) of "koppeling" (operationeel, op een belofte).
    Bij een koppeling staat de accountability-tekst erbij — dát is waar het middel voor dient.
    """
    out: dict[str, list[dict]] = {}
    for rec in records:
        if getattr(rec, "archived", False):
            continue
        for skill in (rec.definition.skills or []):
            out.setdefault(skill, []).append(
                {"role": rec.id, "route": "dna", "acc": "", "acc_id": ""})
        for link in skill_links.links_for_role(ai, rec.id):
            out.setdefault(link.skill, []).append({
                "role": rec.id, "route": "koppeling",
                "acc": acc_ids.text_for(rec.definition, link.acc_id),
                "acc_id": link.acc_id,
            })
    return out


def _sleutels(skill) -> dict:
    """Welke env-sleutels heeft deze skill nodig? (Waarden nooit tonen — alleen de namen.)"""
    return {
        "verplicht": sorted(getattr(skill, "required_env", ()) or ()),
        "optioneel": sorted(getattr(skill, "optional_env", ()) or ()),
    }


# ── De drie blokken ──────────────────────────────────────────────────────────

def uitvoerbaar(records, ai) -> list[dict]:
    """Blok 1: registry-skills met een implementatie."""
    reg = _registry()
    door = gebruikers(records, ai)
    rows = []
    for naam in sorted(reg.names()):
        skill = reg.get(naam)
        rows.append({
            "skill": naam,
            "label": skill_labels.label(naam, reg),
            "sleutels": _sleutels(skill),
            "domein": skill_meta.schrijft_in_domein(naam),
            "zwaar": skill_meta.is_zwaar(naam),
            "suggestie_tegenhanger": skill_meta.suggestie_tegenhanger(naam),
            "suggestie_van": skill_meta.suggestie_van(naam),
            "gebruikers": door.get(naam, []),
        })
    return rows


def niet_gedekt(records, ai) -> dict:
    """Blok 2: genoemd zonder implementatie, plus de dode-capability-audit.

    - `zonder_implementatie`: staat in DNA of in een koppeling, maar de registry kent hem niet.
    - `dood`: de klasse roept hem aan, maar de rol heeft hem niet in zijn effectieve set —
      de aanroep faalt closed. Grant via governance óf koppel hem op de accountability.
    """
    reg = _registry()
    bekend = set(reg.names())
    door = gebruikers(records, ai)

    zonder = [{"skill": s, "gebruikers": g} for s, g in sorted(door.items()) if s not in bekend]

    dood = []
    cmap = _class_map()
    for rec in records:
        if getattr(rec, "archived", False):
            continue
        cls = cmap.get(rec.id)
        if cls is None:
            continue
        effectief = skill_links.effectief(rec, ai)
        for cap in sorted(referenced_capabilities(cls) - effectief):
            dood.append({"role": rec.id, "skill": cap,
                         "label": skill_labels.label(cap, reg)})
    return {"zonder_implementatie": zonder, "dood": dood}


def gewenst(human_inbox) -> list[dict]:
    """Blok 3: means-gaps uit de human inbox — de bouwlijst voor nieuwe tooling."""
    if human_inbox is None:
        return []
    try:
        items = human_inbox.pending()
    except Exception as exc:
        log.warning("skills_catalog: human inbox niet leesbaar: %s", exc)
        return []
    out = []
    for it in items:
        if it.get("type") != "means_gap":
            continue
        ctx = it.get("context") or {}
        out.append({
            "id": it.get("id", ""),
            "gap_key": ctx.get("gap_key") or it.get("subject", ""),
            "beschrijving": ctx.get("description", ""),
            "role": ctx.get("role_id") or "",
            "gevoeld_door": ctx.get("sensed_by") or "",
            "created_at": it.get("created_at", 0),
        })
    return out


def catalogus(records, ai, human_inbox=None) -> dict:
    """Alle drie de blokken in één keer — de datalaag onder /skills."""
    recs = list(records)
    return {
        "uitvoerbaar": uitvoerbaar(recs, ai),
        "niet_gedekt": niet_gedekt(recs, ai),
        "gewenst": gewenst(human_inbox),
    }
