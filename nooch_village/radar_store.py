"""RadarStore — de Radar-tool per rol: door mensen goed te keuren signalen uit een Inoreader-feed.

Een Radar is een tool die een rol krijgt (config: feed → rol → modus). De Inoreader-ingest schrijft
gevonden signalen hierheen met status 'wacht'. Op de rolpagina (Tools-tab) keurt de mens ze goed of
klikt ze weg; goedgekeurde signalen vormen het groeiende archief dat de rol als context meeleest.

Opslag: data/radar.json ({"items": {id: {...}}, "seen": [link, ...]}). `seen` ontdubbelt op de
artikel-URL, zodat hetzelfde artikel niet twee keer een signaal wordt. Atomic write (geen locking; de
ingest draait handmatig, de cockpit-toggle is interactief — botsing is onwaarschijnlijk, v1)."""
from __future__ import annotations

import json
import os
import time
import uuid

from nooch_village.util import JsonStore

_STATUSES = ("wacht", "goedgekeurd", "afgewezen")


def _radar_default() -> dict:
    return {"items": {}, "seen": []}

# Feed → rol → modus. De env-var houdt de (niet-geheime, deployment-specifieke) JSON-URL. Overschrijfbaar
# via data/feeds.json. 'precisie' = per-item naar de radar (Competitor, Legal). 'recall' = latere
# synthese-staart (Materials), nog niet in deze stap verwerkt.
_DEFAULT_FEEDS = [
    {"env": "INOREADER_COMPETITOR_JSON_URL", "role": "concurrent_scout",
     "mode": "precisie", "label": "Competitor Watch"},
    {"env": "INOREADER_LEGAL_JSON_URL", "role": "mother_earth__nooch__strategic_lead_founder_steward",
     "mode": "precisie", "label": "Legal & Green Claims"},
    {"env": "INOREADER_MATERIALS_JSON_URL", "role": "harry_hemp",
     "mode": "recall", "label": "Material Innovation"},
]


def load_feeds(data_dir: str) -> list:
    """De feed→rol-config: data/feeds.json als die bestaat, anders de ingebouwde default."""
    p = os.path.join(data_dir, "feeds.json")
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return list(_DEFAULT_FEEDS)


def feeds_for_role(role: str, data_dir: str) -> list:
    """De feeds die aan deze rol hangen (voor de UI: heeft deze rol een radar?)."""
    return [f for f in load_feeds(data_dir) if f.get("role") == role]


class RadarStore(JsonStore):
    """Schrijft via de JsonStore-basis (flock + verse _load onder het slot); geen directe
    atomic_write_json. State: {"items": {id: {...}}, "seen": [link, ...]}."""

    _WRITE_METHODS = ("mark_seen", "add", "set_status")
    _STATE = "_data"
    _default = staticmethod(_radar_default)
    _EXPECT = dict

    def _load(self) -> None:
        super()._load()                                          # verse read → self._data
        self._data.setdefault("items", {})                       # backfill: oud/partieel bestand
        self._data.setdefault("seen", [])

    def seen(self, link: str) -> bool:
        return bool(link) and link in self._data["seen"]

    def mark_seen(self, link: str) -> None:
        if link and link not in self._data["seen"]:
            self._data["seen"].append(link)
            self._save()

    def add(self, *, role: str, feed: str, kind: str, content: str, rationale: str = "",
            source: str = "", link: str = "") -> str | None:
        """Voeg een signaal toe (status 'wacht'). Dedup op (rol, kind, inhoud) over niet-afgewezen items."""
        content = (content or "").strip()
        if not role or not content:
            return None
        cl = content.lower()
        for it in self._data["items"].values():
            if (it["role"] == role and it["kind"] == kind and it["content"].lower() == cl
                    and it["status"] != "afgewezen"):
                return it["id"]
        rid = uuid.uuid4().hex[:12]
        self._data["items"][rid] = {
            "id": rid, "role": role, "feed": feed, "kind": kind, "content": content[:200],
            "rationale": (rationale or "")[:300], "source": source, "link": link,
            "status": "wacht", "at": time.time()}
        self._save()
        return rid

    def get(self, item_id: str) -> dict | None:
        return self._data["items"].get(item_id)

    def for_role(self, role: str) -> list:
        return [it for it in self._data["items"].values() if it["role"] == role]

    def _by_status(self, role: str, status: str) -> list:
        return sorted((it for it in self._data["items"].values()
                       if it["role"] == role and it["status"] == status),
                      key=lambda it: it["at"], reverse=True)

    def pending(self, role: str) -> list:
        return self._by_status(role, "wacht")

    def approved(self, role: str) -> list:
        return self._by_status(role, "goedgekeurd")

    def set_status(self, item_id: str, status: str) -> bool:
        if status not in _STATUSES:
            return False
        it = self._data["items"].get(item_id)
        if it is None:
            return False
        it["status"] = status
        self._save()
        return True
