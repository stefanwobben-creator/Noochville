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

# Feed → rol → modus + focus. De env-var houdt de (niet-geheime, deployment-specifieke) JSON-URL.
# Overschrijfbaar via data/feeds.json. 'precisie' = per-item naar de radar. 'focus' kiest de distill-bril:
# 'competitor' (default: concurrent-zetten/markt) of 'materials' (nieuwe materialen, afbreekbaarheids-
# bewijs, certificeringen — voor de wetenschapper). 'recall' (synthese-staart) volgt later.
_DEFAULT_FEEDS = [
    {"env": "INOREADER_COMPETITOR_JSON_URL", "role": "concurrent_scout",
     "mode": "precisie", "label": "Competitor Watch"},
    {"env": "INOREADER_LEGAL_JSON_URL", "role": "mother_earth__nooch__strategic_lead_founder_steward",
     "mode": "precisie", "label": "Legal & Green Claims"},
    {"env": "INOREADER_MATERIALS_JSON_URL", "role": "harry_hemp",
     "mode": "precisie", "focus": "materials", "label": "Material Innovation"},
    {"env": "INOREADER_INDUSTRY_JSON_URL", "role": "mother_earth__nooch__strategic_lead_founder_steward",
     "mode": "precisie", "label": "Industry Watch"},
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

    _WRITE_METHODS = ("mark_seen", "add", "set_status", "mark_promoted")
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
            source: str = "", link: str = "", published_at: str = "") -> str | None:
        """Voeg een signaal toe (status 'wacht'). Dedup op (rol, kind, inhoud) over niet-afgewezen items.
        `published_at` = de publicatiedatum van het artikel (uit de feed), los van `at` (moment van
        ingest): een oud artikel is historisch bewijs, geen vers nieuws."""
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
            "published_at": (published_at or "")[:40],
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

    def all_approved(self) -> list:
        """Alle goedgekeurde signalen over álle rollen, nieuwste eerst — de dorp-brede Signals-lijst
        (het startpunt voor inzichten). Read-only aggregatie, geen nieuwe opslag."""
        return sorted((it for it in self._data["items"].values() if it["status"] == "goedgekeurd"),
                      key=lambda it: it["at"], reverse=True)

    def mark_promoted(self, item_id: str, atom_id: str) -> bool:
        """Marker na promotie naar de kennisbank: onthoud op het signaal WELK atoom eruit
        ontstond (of waarmee het samenging). Idempotentie-anker: een gemarkeerd item wordt
        nooit een tweede keer gepromoveerd, en de UI toont een chip i.p.v. de knop."""
        it = self._data["items"].get(item_id)
        if it is None or not atom_id:
            return False
        it["promoted_atom_id"] = atom_id
        self._save()
        return True

    def set_status(self, item_id: str, status: str) -> bool:
        if status not in _STATUSES:
            return False
        it = self._data["items"].get(item_id)
        if it is None:
            return False
        it["status"] = status
        self._save()
        return True
