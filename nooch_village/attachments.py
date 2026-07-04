"""Attachments — generieke primitieven die aan een rol of cirkel hangen.

Eén store bedient de GlassFrog-tabs: Notes, Metrics, Checklists, Policies — en (nieuw) Tools.
Een attachment hangt aan een *anchor* (elke record-id: rol óf cirkel; nesting-agnostisch). Onze
Nooch-specifieke dingen vouwen hierin: concurrenten = notes op de scout-rol, zoekwoord-volume =
metrics op een rol.

`meta` is een vrije dict per soort, bijv. {"frequency": "weekly"} voor een checklist/metric of
{"value": "210", "unit": "zoekvolume"} voor een metric.

## Artefacten (note | policy | tool)

Drie soorten zijn "artefacten" in de zin van de artefact-opdracht: een rol (mens én AI-vervuller)
kan ze binnen zijn eigen domein toevoegen, bewerken en archiveren; onderliggende rollen erven ze
read-only (zie `nooch_village.artefacts`). Voor die soorten geldt extra:

- **Mens-leesbare id** `{TYPE}-{ROLSLUG}-{NNN}` (bv. `POL-CREATO-007`) i.p.v. een uuid.
- **status** `draft | active | archived` — nooit hard verwijderen; archiveren behoudt de historie.
- **inherit** — of het artefact geldt voor onderliggende rollen (erf-query).
- **scope** — vrije tekst, puur informatief, NIET om op te filteren.
  TODO: later `scope_tags: list[str]` toevoegen voor querybare scope.
- **url** — alleen zinvol voor kind="tool".
- **versions** — append-only historie; elke mutatie legt een snapshot vast (wie, wanneer,
  change_note, en bij anchor-mutaties een verplichte governance_ref).

De autorisatie ("wie mag schrijven") en de erf-query leven bewust in `nooch_village.artefacts`,
zodat deze store puur opslag blijft (geen kennis van de org-boom of van vervullers).
"""
from __future__ import annotations
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict

from nooch_village.util import atomic_write_json, read_json, file_lock

# ── Schrijf-serialisatie ─────────────────────────────────────────────────────
# De cockpit draait als ThreadingHTTPServer en bouwt per request een verse store die het hele
# bestand inleest, muteert en terugschrijft. Zonder slot is dat een read-modify-write race:
# twee gelijktijdige schrijvers (bv. mens + AI-persona) berekenen hetzelfde NNN-volgnummer en
# de laatste-schrijver-wint gooit de andere edit weg. `atomic_write_json` voorkomt een corrupt
# bestand, maar niet verloren updates. Daarom serialiseren we elke mutatie per bestandspad met
# `util.file_lock` (het proces-brede, gedeelde slot), en her-lezen we binnen het slot vers van
# schijf zodat NNN/edits de laatste toestand zien.

# Alle soorten die de store kent. metric/checklist zijn géén artefacten (geen erf/versie-eisen).
KINDS = ("note", "metric", "checklist", "policy", "tool")
# De drie artefact-soorten (mens-leesbare id, status, inherit, scope, url, versies).
ARTEFACT_KINDS = ("note", "policy", "tool")
# Geldige statussen voor een artefact.
STATUSES = ("draft", "active", "archived")

# id-prefix per artefact-soort → {TYPE}-{ROLSLUG}-{NNN}
_TYPE_PREFIX = {"policy": "POL", "note": "NOTE", "tool": "TOOL"}
# Filler-vocabulaire (person|persona) → versie-vocabulaire (human|ai) uit de opdracht.
_ACTOR_KIND = {"person": "human", "persona": "ai"}


def _rolslug(anchor: str) -> str:
    """Korte, mens-leesbare rol-afkorting voor in een artefact-id. Laatste pad-segment van de
    record-id, hoofdletters, alleen letters/cijfers, max 6 tekens. `mother_earth__nooch__creator_of_shoes`
    → `CREATO`. Puur cosmetisch; uniciteit komt van het NNN-volgnummer."""
    seg = (anchor or "").split("__")[-1]
    s = re.sub(r"[^A-Z0-9]+", "", seg.upper())
    return s[:6] or "ROL"


def _actor_kind(filler_type: str) -> str:
    """person→human, persona→ai; onbekend/leeg → "" (bv. migratie)."""
    return _ACTOR_KIND.get(filler_type, "")


@dataclass
class Attachment:
    id: str
    anchor: str          # record-id van de rol of cirkel waar dit aan hangt (= owner_role_id)
    kind: str            # note | metric | checklist | policy | tool
    title: str = ""
    body: str = ""
    subtype: str = ""    # legacy voor kind="note": "tool" | "doc". Migratie tilt "tool" → kind="tool".
    meta: dict = field(default_factory=dict)
    # ── artefact-velden (note | policy | tool) ──────────────────────────────
    status: str = "active"       # draft | active | archived
    inherit: bool = True         # geldt voor onderliggende rollen (erf-query)
    scope: str = ""              # vrije tekst, informatief, NIET filteren
    url: str = ""                # alleen zinvol voor kind="tool"
    versions: list = field(default_factory=list)  # append-only historie (zie _version)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def _version(nr: int, actor_id: str, actor_type: str, body_snapshot: str,
             change_note: str = "", governance_ref: str = "", ts: float | None = None) -> dict:
    """Eén historie-entry (komt overeen met de opdracht-tabel artefact_versions). `actor_type`
    hier in het opdracht-vocabulaire human|ai."""
    return {
        "version_nr": nr,
        "ts": time.time() if ts is None else ts,
        "actor_id": actor_id or "",
        "actor_type": _actor_kind(actor_type) if actor_type in _ACTOR_KIND else (actor_type or ""),
        "body_snapshot": body_snapshot or "",
        "change_note": change_note or "",
        "governance_ref": governance_ref or "",
    }


class AttachmentStore:
    """JSON-store voor attachments (data/attachments.json)."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def _mint_id(self, kind: str, anchor: str) -> str:
        """Mens-leesbare id voor artefacten (`{TYPE}-{ROLSLUG}-{NNN}`), anders een uuid.
        NNN is per (soort, rol) oplopend; scant bestaande ids zodat het uniek blijft."""
        if kind not in _TYPE_PREFIX:
            return uuid.uuid4().hex[:12]
        base = f"{_TYPE_PREFIX[kind]}-{_rolslug(anchor)}-"
        hi = 0
        for k in self._items:
            m = re.match(re.escape(base) + r"(\d{3})$", k)
            if m:
                hi = max(hi, int(m.group(1)))
        n = hi + 1
        while f"{base}{n:03d}" in self._items:
            n += 1
        return f"{base}{n:03d}"

    def add(self, anchor: str, kind: str, title: str = "", body: str = "",
            meta: dict | None = None, subtype: str = "", *,
            status: str = "active", inherit: bool = True, scope: str = "", url: str = "",
            actor_id: str = "", actor_type: str = "",
            governance_ref: str = "", change_note: str = "") -> Attachment | None:
        """Maak een attachment. Voor artefact-soorten (note/policy/tool) krijgt hij een
        mens-leesbare id en versie 1. `actor_type` in filler-vocabulaire (person|persona)."""
        if kind not in KINDS or not anchor:
            return None
        if status not in STATUSES:
            status = "active"
        # subtype geldt alleen legacy voor notes; nieuwe tools hebben een eigen kind.
        subtype = subtype if (kind == "note" and subtype in ("tool", "doc")) else ""
        url = (url or "").strip()[:500] if kind == "tool" else ""
        body = (body or "").strip()[:4000]
        with file_lock(self.path):
            self._items = read_json(self.path, {})   # verse toestand onder slot → uniek NNN
            aid = self._mint_id(kind, anchor)
            a = Attachment(id=aid, anchor=anchor, kind=kind, title=(title or "").strip()[:200],
                           body=body, subtype=subtype, meta=dict(meta or {}),
                           status=status, inherit=bool(inherit),
                           scope=(scope or "").strip()[:400], url=url,
                           versions=[_version(1, actor_id, actor_type, body,
                                              change_note or "aangemaakt", governance_ref)])
            self._items[aid] = asdict(a)
            self._save()
        return a

    def get(self, aid: str | None) -> Attachment | None:
        if not aid:
            return None
        d = self._items.get(aid)
        return Attachment(**d) if d else None

    def list(self, anchor: str, kind: str | None = None, *,
             include_archived: bool = False) -> list[Attachment]:
        """Attachments van een anchor, optioneel gefilterd op soort. Nieuwste eerst.
        Gearchiveerde artefacten worden standaard weggelaten (historie blijft in de store)."""
        out = [Attachment(**d) for d in self._items.values()
               if d.get("anchor") == anchor and (kind is None or d.get("kind") == kind)
               and (include_archived or d.get("status", "active") != "archived")]
        return sorted(out, key=lambda a: a.created_at, reverse=True)

    def counts(self, anchor: str) -> dict:
        """Aantal per soort voor een anchor (handig voor de tab-badges). Telt geen archief."""
        c = {k: 0 for k in KINDS}
        for d in self._items.values():
            if (d.get("anchor") == anchor and d.get("kind") in c
                    and d.get("status", "active") != "archived"):
                c[d["kind"]] += 1
        return c

    def update(self, aid: str, *, title: str | None = None, body: str | None = None,
               meta: dict | None = None, scope: str | None = None, url: str | None = None,
               inherit: bool | None = None,
               actor_id: str = "", actor_type: str = "",
               governance_ref: str = "", change_note: str = "") -> Attachment | None:
        """Werk een attachment bij. Voor artefacten wordt een nieuwe versie-snapshot toegevoegd
        (append-only); de body-wijziging is daardoor altijd terug te lezen."""
        with file_lock(self.path):
            self._items = read_json(self.path, {})   # verse toestand onder slot → geen lost edit
            d = self._items.get(aid)
            if d is None:
                return None
            if title is not None:
                d["title"] = title.strip()[:200]
            if body is not None:
                d["body"] = body.strip()[:4000]
            if meta is not None:
                d["meta"] = dict(meta)
            if scope is not None:
                d["scope"] = scope.strip()[:400]
            if url is not None and d.get("kind") == "tool":
                d["url"] = url.strip()[:500]
            if inherit is not None:
                d["inherit"] = bool(inherit)
            d["updated_at"] = time.time()
            if d.get("kind") in ARTEFACT_KINDS:
                versions = d.setdefault("versions", [])
                nr = (versions[-1]["version_nr"] + 1) if versions else 1
                versions.append(_version(nr, actor_id, actor_type, d.get("body", ""),
                                         change_note or "bewerkt", governance_ref))
            self._save()
            return Attachment(**d)

    def archive(self, aid: str, *, actor_id: str = "", actor_type: str = "",
                governance_ref: str = "", change_note: str = "") -> Attachment | None:
        """Zet status op "archived" (nooit hard verwijderen). Legt een versie-entry vast zodat
        de archivering in de historie zichtbaar is."""
        with file_lock(self.path):
            self._items = read_json(self.path, {})   # verse toestand onder slot
            d = self._items.get(aid)
            if d is None:
                return None
            d["status"] = "archived"
            d["updated_at"] = time.time()
            if d.get("kind") in ARTEFACT_KINDS:
                versions = d.setdefault("versions", [])
                nr = (versions[-1]["version_nr"] + 1) if versions else 1
                versions.append(_version(nr, actor_id, actor_type, d.get("body", ""),
                                         change_note or "gearchiveerd", governance_ref))
            self._save()
            return Attachment(**d)

    def remove(self, aid: str) -> bool:
        """Hard verwijderen — alléén voor migratie/curatie. Voor artefacten gebruik `archive`."""
        with file_lock(self.path):
            self._items = read_json(self.path, {})
            if aid in self._items:
                del self._items[aid]
                self._save()
                return True
            return False

    def migrate(self) -> int:
        """Idempotent: tilt bestaande data naar het artefact-model.
        - note met subtype=="tool"  → kind="tool" (en subtype gewist).
        - vult ontbrekende artefact-velden (status/inherit/scope/url/versions) met defaults.
        Wijzigt nooit bestaande waarden (overwrite-veilig). Geeft het aantal gewijzigde items terug."""
        with file_lock(self.path):
            self._items = read_json(self.path, {})
            return self._migrate_locked()

    def _migrate_locked(self) -> int:
        changed = 0
        for d in self._items.values():
            touched = False
            if d.get("kind") == "note" and d.get("subtype") == "tool":
                d["kind"] = "tool"
                d["subtype"] = ""
                touched = True
            for f_, dv in (("status", "active"), ("inherit", True), ("scope", ""), ("url", "")):
                if f_ not in d:
                    d[f_] = dv
                    touched = True
            if not d.get("versions"):
                d["versions"] = [_version(1, "", "", d.get("body", ""),
                                          "migratie", "", ts=d.get("created_at"))]
                touched = True
            if touched:
                changed += 1
        if changed:
            self._save()
        return changed
