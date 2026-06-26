"""Attachments — generieke primitieven die aan een rol of cirkel hangen.

Eén store bedient vier GlassFrog-tabs: Notes, Metrics, Checklists, Policies. Een attachment hangt
aan een *anchor* (elke record-id: rol óf cirkel; nesting-agnostisch). Onze Nooch-specifieke dingen
vouwen hierin: concurrenten = notes op de scout-rol, zoekwoord-volume = metrics op een rol.

`meta` is een vrije dict per soort, bijv. {"frequency": "weekly"} voor een checklist/metric of
{"value": "210", "unit": "zoekvolume"} voor een metric.
"""
from __future__ import annotations
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict

from nooch_village.util import atomic_write_json

KINDS = ("note", "metric", "checklist", "policy")


@dataclass
class Attachment:
    id: str
    anchor: str          # record-id van de rol of cirkel waar dit aan hangt
    kind: str            # note | metric | checklist | policy
    title: str = ""
    body: str = ""
    meta: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class AttachmentStore:
    """JSON-store voor attachments (data/attachments.json)."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._items = d
            except Exception:
                self._items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, anchor: str, kind: str, title: str = "", body: str = "",
            meta: dict | None = None) -> Attachment | None:
        if kind not in KINDS or not anchor:
            return None
        aid = uuid.uuid4().hex[:12]
        a = Attachment(id=aid, anchor=anchor, kind=kind, title=(title or "").strip()[:200],
                       body=(body or "").strip()[:4000], meta=dict(meta or {}))
        self._items[aid] = asdict(a)
        self._save()
        return a

    def get(self, aid: str | None) -> Attachment | None:
        if not aid:
            return None
        d = self._items.get(aid)
        return Attachment(**d) if d else None

    def list(self, anchor: str, kind: str | None = None) -> list[Attachment]:
        """Attachments van een anchor, optioneel gefilterd op soort. Nieuwste eerst."""
        out = [Attachment(**d) for d in self._items.values()
               if d.get("anchor") == anchor and (kind is None or d.get("kind") == kind)]
        return sorted(out, key=lambda a: a.created_at, reverse=True)

    def counts(self, anchor: str) -> dict:
        """Aantal per soort voor een anchor (handig voor de tab-badges)."""
        c = {k: 0 for k in KINDS}
        for d in self._items.values():
            if d.get("anchor") == anchor and d.get("kind") in c:
                c[d["kind"]] += 1
        return c

    def update(self, aid: str, *, title: str | None = None, body: str | None = None,
               meta: dict | None = None) -> Attachment | None:
        d = self._items.get(aid)
        if d is None:
            return None
        if title is not None:
            d["title"] = title.strip()[:200]
        if body is not None:
            d["body"] = body.strip()[:4000]
        if meta is not None:
            d["meta"] = dict(meta)
        d["updated_at"] = time.time()
        self._save()
        return Attachment(**d)

    def remove(self, aid: str) -> bool:
        if aid in self._items:
            del self._items[aid]
            self._save()
            return True
        return False
