"""Het prikbord — gedeeld, persistent geheugen naast de in-memory EventBus.

Rollen hangen er twee soorten briefjes op en halen eruit wat bij hen past (PULL):
  - 'request' : "ik heb hulp nodig bij X" (van/aan een tag, met done-criterium)
  - 'outcome' : "ik heb dit resultaat: Z" (consumeerbaar door een andere rol of een curator)

Verschil met de bus: de bus is vluchtig en real-time; het prikbord blijft bestaan, is zichtbaar
voor de mens en is door de tijd heen pull-baar (open → claimed → done). Zie
docs/ONTWERP_prikbord_kanban.md. Achter dezelfde JSON-bestand-interface als de andere stores.
"""
from __future__ import annotations
import json
import os
import time
import uuid

from nooch_village.util import atomic_write_json

_KINDS = ("request", "outcome")
_STATUS = ("open", "claimed", "done")


class Pinboard:
    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                self._items = json.load(open(path))
            except Exception:
                self._items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def post(self, kind: str, tag: str, title: str, *, body: str = "", by: str = "",
             links: list[str] | None = None) -> str:
        """Hang een briefje op. Dedup op (kind, tag, title) over niet-afgeronde briefjes:
        hetzelfde verzoek/uitkomst komt nooit dubbel. Geeft het (bestaande of nieuwe) id."""
        kind = (kind or "").strip().lower()
        tag = (tag or "").strip()
        title = (title or "").strip()
        if kind not in _KINDS or not tag or not title:
            raise ValueError(f"ongeldig briefje: kind={kind!r} tag={tag!r} title={title!r}")
        tl = title.lower()
        for it in self._items.values():
            if (it["kind"] == kind and it["tag"].lower() == tag.lower()
                    and it["title"].lower() == tl and it["status"] != "done"):
                return it["id"]
        bid = uuid.uuid4().hex[:12]
        self._items[bid] = {
            "id": bid, "kind": kind, "tag": tag, "title": title[:160], "body": body[:2000],
            "by": by or "", "status": "open", "claimed_by": None,
            "links": list(links or []), "created_at": time.time()}
        self._save()
        return bid

    def claim(self, bid: str, by: str) -> bool:
        """Claim een open briefje (eerste wint → dedup van werk). Alleen open → claimed."""
        it = self._items.get(bid)
        if it is None or it["status"] != "open":
            return False
        it["status"] = "claimed"
        it["claimed_by"] = by
        self._save()
        return True

    def complete(self, bid: str) -> bool:
        it = self._items.get(bid)
        if it is None or it["status"] == "done":
            return False
        it["status"] = "done"
        self._save()
        return True

    def link_project(self, bid: str, pid: str) -> bool:
        """Koppel een briefje aan een project (de keten/het gesprek)."""
        it = self._items.get(bid)
        if it is None or not pid:
            return False
        if pid not in it["links"]:
            it["links"].append(pid)
            self._save()
        return True

    def get(self, bid: str) -> dict | None:
        return self._items.get(bid)

    def all(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda i: i.get("created_at", 0))

    def open(self, tag: str | None = None) -> list[dict]:
        """Openstaande briefjes (optioneel gefilterd op tag) — wat een rol kan oppakken."""
        return [i for i in self.all() if i["status"] == "open"
                and (tag is None or i["tag"].lower() == tag.lower())]


_DEFAULT_WIP = {"board": 3, "roles": {}}


def read_wip(dd: str) -> dict:
    """WIP-limieten uit config/strategy.json ('wip': {board: N, roles: {rol: N}}). Default board=3.
    Bord-breed én per rol instelbaar — de tempo-knop van de mens."""
    path = os.path.join(dd, "..", "config", "strategy.json")
    try:
        wip = (json.load(open(path)) or {}).get("wip") or {}
    except Exception:
        wip = {}
    return {"board": int(wip.get("board", _DEFAULT_WIP["board"])),
            "roles": dict(wip.get("roles", {}))}
