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

import json
import os
import time

from nooch_village import org
from nooch_village.util import file_lock


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


def erfketen(anchor: str, inherit: bool, records) -> list[str]:
    """De rollen die dit artefact 'zien': de eigenaar zelf, plus — als het erft — al zijn nazaten.
    Dit is de referentie die de seen-markering (brok 5) nodig heeft om te weten wélke rollen in de
    keten een 'gewijzigd sinds laatst gezien'-stip krijgen."""
    chain = [anchor]
    if inherit:
        chain += [r.id for r in org.descendants(records.all(), anchor)]
    return chain


def log_change(data_dir: str, *, action: str, artefact, records,
               actor_id: str = "", actor_type: str = "", governance_ref: str = "") -> dict:
    """Append-only changelog van artefact-mutaties (`data/artefact_changelog.jsonl`).

    Elke regel legt vast: tijdstip, actie (add|edit|archive), artefact-id, eigenaar (anchor),
    de erfketen-snapshot (welke rollen dit zien) en de governance_ref. Dit is de databron voor de
    'gewijzigd sinds laatst gezien'-markering in brok 5.

    De append staat bewust onder hetzelfde per-pad slot (`util.file_lock`) als de store-mutaties,
    zodat regel-atomiciteit gegarandeerd is en niet toevallig van de regellengte afhangt.
    """
    entry = {
        "ts": time.time(),
        "action": action,
        "artefact_id": getattr(artefact, "id", ""),
        "anchor": getattr(artefact, "anchor", ""),
        "kind": getattr(artefact, "kind", ""),
        "inherit": bool(getattr(artefact, "inherit", False)),
        "actor_id": actor_id or "",
        "actor_type": actor_type or "",
        "governance_ref": governance_ref or "",
        "erfketen": erfketen(getattr(artefact, "anchor", ""),
                             bool(getattr(artefact, "inherit", False)), records),
    }
    path = os.path.join(data_dir, "artefact_changelog.jsonl")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with file_lock(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _art_item(a, *, editable: bool) -> dict:
    """Eén artefact als serialisatie-dict. `editable` = mag deze rol het bewerken (eigen=True,
    geërfd=False). `mutation_path="artefact"`: te wijzigen via de artefact-routes (bij de eigenaar)."""
    d = {"id": a.id, "kind": a.kind, "title": a.title, "body": a.body,
         "status": a.status, "editable": editable, "mutation_path": "artefact",
         "updated_at": getattr(a, "updated_at", 0)}
    if a.kind == "policy":
        d["domain"] = getattr(a, "domain", "")
    if a.kind == "tool":
        d["url"] = a.url
    return d


def _art_block(role_id: str, kind: str, records, store) -> dict:
    """{"own": [...], "inherited": [...]} voor één artefact-soort; geërfde items dragen het
    herkomst-pad ("via <naam>")."""
    oi = own_and_inherited(role_id, kind, records, store)
    own = [_art_item(a, editable=True) for a in oi["own"]]
    inherited = []
    for it in oi["inherited"]:
        item = _art_item(it["artefact"], editable=False)
        item["origin_id"] = it["origin_id"]
        item["origin_name"] = it["origin_name"]
        item["origin_path"] = f"via {it['origin_name']}"
        inherited.append(item)
    return {"own": own, "inherited": inherited}


def serialize_context(role_id: str, records, store) -> dict:
    """De volledige rol-context als structuur: overview (purpose/domains/accountabilities) +
    policies (eigen + geërfd; alle domein-gescopeerd en governance-eigendom) + notes + tools.
    Bron voor het /context-endpoint (json en markdown)."""
    rec = records.get(role_id)
    if rec is None:
        return {}
    d = rec.definition
    role = {
        "id": role_id, "name": _name(rec), "purpose": getattr(d, "purpose", "") or "",
        "domains": list(getattr(d, "domains", None) or []),
        "accountabilities": list(getattr(d, "accountabilities", None) or []),
    }
    return {
        "role": role,
        "policies": _art_block(role_id, "policy", records, store),
        "notes": _art_block(role_id, "note", records, store),
        "tools": _art_block(role_id, "tool", records, store),
    }


def _md_section(block: dict, *, tool: bool = False) -> list[str]:
    """Markdown voor 'Van deze rol' + 'Geldend hier (geërfd)' van één artefact-soort."""
    def line(a: dict, inherited: bool) -> str:
        if tool and a.get("url"):
            extra = f" — {a['url']}"
        elif a.get("body"):
            extra = f" — {a['body']}"
        else:
            extra = ""
        prefix = f"`{a['id']}` " if a.get("kind") == "policy" else ""
        tag = f" _({a['origin_path']})_" if inherited else ""
        return f"- {prefix}**{a.get('title') or a['id']}**{extra}{tag}"

    out = ["### Van deze rol"]
    out += [line(a, False) for a in block["own"]] or ["- —"]
    out.append("### Geldend hier (geërfd)")
    out += [line(a, True) for a in block["inherited"]] or ["- —"]
    return out


def render_context_markdown(ctx: dict) -> str:
    """Systeemprompt-bron voor AI-vervullers (Wendy Words): de vier blokken als geldige markdown."""
    if not ctx:
        return "# Onbekende rol\n"
    role = ctx["role"]
    L = [f"# Rol-context: {role['name']}", "", "## Overzicht",
         f"**Purpose:** {role['purpose']}",
         f"**Domeinen:** {', '.join(role['domains']) or '—'}",
         "**Accountabilities:**"]
    L += [f"- {a}" for a in role["accountabilities"]] or ["- —"]
    L += ["", "## Policies", "_Alle policies zijn governance-eigendom (domein-voorwaarden): "
          "volg ze, stel wijzigingen alleen voor via de domein-eigenaar._"]
    L += _md_section(ctx["policies"])
    L += ["", "## Notes"]
    L += _md_section(ctx["notes"])
    L += ["", "## Tools"]
    L += _md_section(ctx["tools"], tool=True)
    L.append("")
    return "\n".join(L) + "\n"


def read_changelog(data_dir: str) -> list[dict]:
    """Lees de append-only artefact-changelog (`data/artefact_changelog.jsonl`) als lijst dicts.
    Corrupte regels worden overgeslagen (fail-open per regel). Bron voor de seen-markering."""
    path = os.path.join(data_dir, "artefact_changelog.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


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
