"""DeliverableStore — skill-resultaten overleven het project als gestructureerde, queryabele records.

De wall-note (de 📎-rendering) blijft de wéérgave; deze store wordt de brón. Additief en nooit
blokkerend: valt de store weg of faalt een schrijf, dan draait alles als voorheen (de wall-note is
op dat moment al geschreven). Op de JsonStore-basis → flock + verse read onder het slot, geen
uitzondering op de ratchet.

Opslagvorm: **lichte index + write-once sidecars.**
- Index-record in `data/deliverables.json` (op id):
  {id, project_id, role, skill, checklist_item, title, summary, wall_note_id, created_at}.
  `checklist_item` = het adresseerbare item-id; `title` = de leesbare item-tekst.
- Volledige content per record in `data/deliverables/<id>.json` (sidecar, write-once, géén lock nodig).
  `content` = het VOLLEDIGE skill-resultaat (JSON-serialiseerbaar), begrensd op een config-max met een
  LUIDE logregel bij afkap: bij overschrijding wordt de sidecar een GELDIGE stand-in
  ({_truncated,_bytes,_cap,preview}), nooit stille truncatie (les van schuld-item #2).
- `summary` = de bestaande 📎-rendering; hierop scoort gather_deliverable_context (niet op content).
- `wall_note_id` = het id van de bijbehorende wall-note (add_role_message).

Schrijfvolgorde in `add`: EERST de sidecar, DAN het index-record. Een wees-sidecar bij een crash is
onschadelijk (niets verwijst ernaar); een index-record zonder sidecar — de kapotte staat — is zo
structureel onmogelijk. Sidecars onder `data/deliverables/` vallen binnen het bestaande
`tar czf … data/`-backup-tarball-pad.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from nooch_village.util import JsonStore, atomic_write_json

log = logging.getLogger("village.deliverables")

_DEFAULT_MAX_BYTES = 100_000


def _cap_content(content, max_bytes: int, *, ctx: str = ""):
    """content ≤ max_bytes → onveranderd terug; anders een geldige stand-in + een LUIDE logregel.
    Geeft (sidecar_payload, truncated_bool). De stand-in is de sidecar-inhoud bij overschrijding."""
    try:
        blob = json.dumps(content, ensure_ascii=False, default=str)
    except Exception:
        content = blob = str(content)                       # niet-serialiseerbaar → als string bewaren
    n = len(blob.encode("utf-8"))
    if n <= max_bytes:
        return content, False
    log.warning("DELIVERABLE_CAP: content %d bytes > max %d — sidecar krijgt een stand-in (preview) | %s",
                n, max_bytes, ctx)
    return {"_truncated": True, "_bytes": n, "_cap": max_bytes, "preview": blob[:max_bytes]}, True


class DeliverableStore(JsonStore):
    """Lichte index in data/deliverables.json (records op id); volledige content write-once in
    data/deliverables/<id>.json. De index loopt via de JsonStore-flock; sidecars zijn write-once en
    lock-vrij (elk id is uniek → geen gelijktijdige schrijf op hetzelfde bestand)."""

    _WRITE_METHODS = ("add", "delete_for_project")
    _STATE = "_items"
    _default = dict
    _EXPECT = dict

    @property
    def _sidecar_dir(self) -> str:
        # .../deliverables.json → .../deliverables/  (naast het index-bestand, onder data/ → backup dekt het)
        base, _ext = os.path.splitext(self.path)
        return base

    def _sidecar_path(self, rid: str) -> str:
        return os.path.join(self._sidecar_dir, f"{rid}.json")

    def add(self, *, project_id: str, role: str, skill: str, checklist_item: str,
            title: str, content, summary: str, wall_note_id: str = "",
            max_bytes: int = _DEFAULT_MAX_BYTES) -> dict:
        """Schrijf één deliverable. Volgorde: EERST de sidecar (volledige content, evt. cap-stand-in),
        DAN het index-record. `content` wordt fail-loud begrensd (zie _cap_content)."""
        rid = uuid.uuid4().hex[:12]
        payload, _tr = _cap_content(content, max_bytes, ctx=f"project={project_id} skill={skill}")
        # 1) sidecar eerst — atomic + crash-veilig (os.replace); write-once, lock-vrij
        atomic_write_json(self._sidecar_path(rid), payload)
        # 2) dan pas het lichte index-record (onder de JsonStore-flock; content zit NIET in de index)
        rec = {"id": rid, "project_id": project_id, "role": role, "skill": skill,
               "checklist_item": checklist_item, "title": (title or "")[:300],
               "summary": summary, "wall_note_id": wall_note_id or "",
               "created_at": time.time()}
        # Een herdraai van HETZELFDE checklist-item vervangt zijn voorganger. Zonder dit stapelde
        # elke retry een nieuwe set: op productie stonden er 30 deliverables bij één project waarvan
        # 5 uniek. De synthese betaalde daardoor zeven keer voor dezelfde bevinding en zag er nog
        # zes van de dertig, en het bewijsvenster van de critic zat vol duplicaten — precies waarom
        # hij 'Compliance Score 88/100' ongegrond noemde terwijl claims_check dat cijfer teruggaf.
        #
        # VERVANGEN, NIET WISSEN. De Kroniek (evidence_ledger.jsonl) verwijst via `result_ref` naar
        # een deliverable-id; dat weggooien maakt de audit-trail kapot. Het oude record blijft dus
        # staan mét zijn sidecar, gemarkeerd als vervangen, en verdwijnt alleen uit de leesweg die
        # "wat geldt er nu?" vraagt.
        if checklist_item:
            for oud in self._items.values():
                if (oud.get("project_id") == project_id
                        and oud.get("checklist_item") == checklist_item
                        and not oud.get("vervangen_door")):
                    oud["vervangen_door"] = rid
        self._items[rid] = rec
        self._save()
        return rec

    def migrate_vervangen(self) -> int:
        """Markeer bestaande duplicaat-stapels alsnog: per (project, checklist_item) blijft de
        jongste gelden, de rest krijgt `vervangen_door`.

        Zonder deze migratie geldt de ontdubbeling alleen voor NIEUWE runs, en houdt elk project dat
        nooit meer herdraait zijn stapel — op productie stond er één met 30 records waarvan 5 uniek.
        Idempotent, en wist niets: de records en hun sidecars blijven staan voor de Kroniek."""
        per: dict[tuple, list] = {}
        for r in self._items.values():
            if r.get("checklist_item"):
                per.setdefault((r.get("project_id"), r.get("checklist_item")), []).append(r)
        n = 0
        for groep in per.values():
            if len(groep) < 2:
                continue
            groep.sort(key=lambda r: r.get("created_at") or 0)
            jongste = groep[-1]["id"]
            for oud in groep[:-1]:
                if not oud.get("vervangen_door"):
                    oud["vervangen_door"] = jongste
                    n += 1
        if n:
            self._save()
            log.info("deliverables ontdubbeld: %d records gemarkeerd als vervangen (niets gewist)", n)
        return n

    def delete_for_project(self, project_id: str) -> int:
        """Cascade bij DEFINITIEVE project-delete: verwijder index-records ÉN sidecars van dit project,
        met één logregel die beide aantallen noemt. Statusovergangen (done/archief/heropening) roepen dit
        NOOIT aan — die laten records met rust. Geeft het aantal verwijderde INDEX-records terug."""
        ids = [rid for rid, r in self._items.items() if r.get("project_id") == project_id]
        sidecars = 0
        for rid in ids:
            sp = self._sidecar_path(rid)
            try:
                os.remove(sp)
                sidecars += 1
            except FileNotFoundError:
                pass                                        # index zonder sidecar zou niet mogen; breek niet
            except OSError as e:
                log.warning("DELIVERABLE_CASCADE: sidecar %s niet verwijderd: %s", sp, e)
            del self._items[rid]
        if ids:
            self._save()
            log.info("cascade: verwijderd: %d index-records, %d sidecars (project %s)",
                     len(ids), sidecars, project_id)
        return len(ids)

    # ── lezen (lock-vrij) ──────────────────────────────────────────────────────
    def for_project(self, project_id: str, *, inclusief_vervangen: bool = False) -> list[dict]:
        """De deliverables van dit project — standaard alleen de GELDENDE.

        Een herdraai van hetzelfde checklist-item markeert zijn voorganger als vervangen. Die blijft
        bestaan (de Kroniek verwijst ernaar), maar hoort niet in de synthese of het critic-venster:
        daar is de vraag "wat geldt er nu?". `inclusief_vervangen=True` geeft de volle historie,
        voor audit."""
        uit = [r for r in self._items.values() if r.get("project_id") == project_id]
        return uit if inclusief_vervangen else [r for r in uit if not r.get("vervangen_door")]

    def by_ids(self, ids) -> list[dict]:
        want = set(ids or [])
        return [r for r in self._items.values() if r.get("id") in want]

    def all_records(self) -> list[dict]:
        return list(self._items.values())

    def content_for(self, rid: str):
        """De volledige content uit de sidecar (of de {_truncated,…}-stand-in bij overschrijding).
        Sidecar weg/onleesbaar → fail-loud logregel + None, nooit crash."""
        sp = self._sidecar_path(rid)
        try:
            with open(sp, encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            log.warning("DELIVERABLE_SIDECAR_MISSING: geen content-bestand voor %s (%s)", rid, sp)
            return None
        except (OSError, ValueError) as e:
            log.warning("DELIVERABLE_SIDECAR_UNREADABLE: %s onleesbaar: %s", sp, e)
            return None
