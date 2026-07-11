"""Configureerbare zoek-sets voor community_listening (Billy Buzz).

Een set bundelt per PLATFORM de queries/kanalen/subreddits die de community-luister-skill afzoekt.
Zo is de onderwerp- én bron-keuze data, geen code.

v2-schema (per set):
  {
    "id": ..., "label": ..., "active": true,
    "platforms": {
      "reddit":  {"active": false, "subreddits": [...], "queries": [...]},
      "youtube": {"active": true,  "channel_ids": [...], "queries": [...]},
      "bluesky": {"active": true,  "queries": [...]}
    }
  }

Achter de JsonStore-basis: elke schrijf neemt het gedeelde bestandsslot (fcntl flock) en leest
vers van schijf ONDER het slot. De mens (of de seed) cureert; de skill leest vrij.
"""
from __future__ import annotations

from nooch_village.util import JsonStore

# Library-koppeling (v2.1): naast de handmatige queries óók research-approved Library-termen.
# 'exclude' is het mens-wint-mechanisme: verwijder je een gesyncte term handmatig uit de effectieve
# queries, zet 'm dan hier — anders walst de volgende sync eroverheen. YouTube krijgt BEWUST GEEN
# library_link: library-termen draaien alleen op gratis platforms (quota-kader). Reddit krijgt het blok
# alvast op active=True; het vuurt pas als het reddit-PLATFORM actief wordt (geen vergeten tweede flip).
def _library_link_seed() -> dict:
    return {"active": True,
            "filter": {"status": "research_approved", "tags": [], "locale": ["nl", "en"]},
            "max_queries": 10,
            "exclude": []}


# Zaad-set uit de briefing. Reddit staat BEWUST inactief (wacht op API-approval) maar houdt zijn
# volledige config (subreddits + queries) zodat reactivering later niet stil kapot is.
_SEED_SETS: dict[str, dict] = {
    "barefoot_ervaringen": {
        "id": "barefoot_ervaringen",
        "label": "Barefoot-ervaringen",
        "active": True,
        "platforms": {
            "reddit": {
                "active": False,
                "subreddits": ["BarefootRunning", "barefootshoestalk", "vegan", "veganfashion"],
                "queries": ["barefoot shoes experience", "barefoot shoes review", "vegan barefoot"],
                "library_link": _library_link_seed(),   # vuurt zodra het reddit-platform live gaat
            },
            "youtube": {
                "active": True,
                # Geresolved via channels.list?forHandle= (eenmalig, geverifieerd tegen de API-titel):
                #   UCCJOX9b_oojDzit600t3ORA = Anya's Reviews (@anyasreviews)
                #   UCId9g4zlQ9BOn6fLKIt1Y0A = Rose Anvil (@roseanvil)
                # 'The Barefoot Shoe Guy' was niet resolvebaar via forHandle → bewust weggelaten (niet gokken).
                "channel_ids": ["UCCJOX9b_oojDzit600t3ORA", "UCId9g4zlQ9BOn6fLKIt1Y0A"],
                "queries": ["barefoot shoes review", "barefoot shoes 1 year"],
            },
            "bluesky": {
                "active": True,
                "queries": ["barefoot shoes", "vegan shoes", "barefoot schoenen"],
                "library_link": _library_link_seed(),
            },
        },
    }
}

# Volgorde waarin de skill de platforms afwerkt (kanaal-modus/quota van YouTube eerst is niet nodig,
# maar deze volgorde houdt de per-platform samenvatting stabiel).
PLATFORM_ORDER = ("youtube", "bluesky", "reddit")


class BuzzQuerySets(JsonStore):
    """JSON-store van zoek-sets (data/buzz_query_sets.json). Sleutel = set-id."""

    _WRITE_METHODS = ("add", "set_active", "upsert")
    _STATE = "_items"
    _default = dict
    _EXPECT = dict

    def add(self, set_id: str, label: str, platforms: dict | None = None,
            active: bool = True) -> dict | None:
        """Voeg een set toe of overschrijf 'm met een volledig platforms-object."""
        set_id = (set_id or "").strip()
        if not set_id:
            return None
        rec = {"id": set_id, "label": (label or set_id).strip()[:120],
               "active": bool(active), "platforms": _clean_platforms(platforms or {})}
        self._items[set_id] = rec
        self._save()
        return rec

    def set_active(self, set_id: str, active: bool) -> dict | None:
        rec = self._items.get(set_id)
        if rec is None:
            return None
        rec["active"] = bool(active)
        self._save()
        return rec

    def upsert(self, set_id: str, rec: dict) -> dict | None:
        """Schrijf een volledig set-record (voor seed/migratie). Onder het slot, verse read vooraf."""
        set_id = (set_id or "").strip()
        if not set_id:
            return None
        self._items[set_id] = rec
        self._save()
        return rec

    def get(self, set_id: str | None) -> dict | None:
        return self._items.get(set_id) if set_id else None

    def all(self) -> list[dict]:
        return list(self._items.values())

    def active(self) -> list[dict]:
        return [s for s in self._items.values() if s.get("active")]

    def platform_cfg(self, set_id: str, platform: str) -> dict | None:
        """De config van één platform binnen een set, of None als het platform ontbreekt."""
        rec = self._items.get(set_id) or {}
        return (rec.get("platforms") or {}).get(platform)


def _clean_library_link(link: dict) -> dict:
    """Normaliseer een library_link-blok (v2.1)."""
    link = dict(link or {})
    flt = dict(link.get("filter") or {})
    return {
        "active": bool(link.get("active", False)),
        "filter": {
            "status": str(flt.get("status") or "research_approved"),
            "tags": [str(t).strip() for t in (flt.get("tags") or []) if str(t).strip()],
            "locale": [str(l).strip().lower() for l in (flt.get("locale") or []) if str(l).strip()],
        },
        "max_queries": int(link.get("max_queries") or 0),
        "exclude": [str(x).strip() for x in (link.get("exclude") or []) if str(x).strip()],
    }


def _clean_platforms(platforms: dict) -> dict:
    """Normaliseer een platforms-object licht (strings trimmen, listen schoonvegen)."""
    out: dict = {}
    for plat, cfg in (platforms or {}).items():
        cfg = dict(cfg or {})
        c = {"active": bool(cfg.get("active", False))}
        for key in ("subreddits", "queries", "channel_ids"):
            if key in cfg:
                c[key] = [str(x).strip()[:120] for x in (cfg.get(key) or []) if str(x).strip()]
        if "library_link" in cfg:
            c["library_link"] = _clean_library_link(cfg["library_link"])
        out[plat] = c
    return out


def migrate_buzz_query_sets(store: BuzzQuerySets) -> int:
    """Til elke set idempotent naar het v2-platforms-schema. Additief — nooit mens-edits overschrijven:

      1. Set zonder `platforms` → wrap legacy top-level `subreddits`/`queries` in
         `platforms.reddit` (active=False; Reddit wacht op API-approval).
      2. Seed-sets: vul ONTBREKENDE platform-keys aan uit de seed (youtube/bluesky); bestaande
         platform-config blijft ongemoeid.
      3. Klaar zodra `platforms` volledig is → tweede run doet niets.

    Geeft het aantal gemigreerde sets terug."""
    migrated = 0
    for set_id, rec in list(store._items.items()):
        rec = dict(rec)
        platforms = dict(rec.get("platforms") or {})
        changed = False
        if "platforms" not in rec:
            if rec.get("subreddits") or rec.get("queries"):
                platforms["reddit"] = {"active": False,
                                       "subreddits": rec.get("subreddits", []),
                                       "queries": rec.get("queries", [])}
            # legacy top-level velden verdwijnen uit het record (leven nu onder platforms.reddit)
            rec.pop("subreddits", None)
            rec.pop("queries", None)
            changed = True
        seed = _SEED_SETS.get(set_id)
        if seed:
            for plat, cfg in seed["platforms"].items():
                if plat not in platforms:
                    platforms[plat] = dict(cfg)
                    changed = True
                elif cfg.get("library_link") and not (platforms.get(plat) or {}).get("library_link"):
                    # v2.1: bestaand platform mist het library_link-blok → additief aanvullen uit de
                    # seed, zonder de rest van de (mens-gecureerde) platform-config te raken.
                    platforms[plat] = {**(platforms[plat] or {}),
                                       "library_link": dict(cfg["library_link"])}
                    changed = True
        if changed:
            rec["platforms"] = _clean_platforms(platforms)
            rec.setdefault("active", True)
            store.upsert(set_id, rec)
            migrated += 1
    return migrated


def seed_buzz_query_sets(store: BuzzQuerySets) -> None:
    """Laad de zaad-sets idempotent en migreer bestaande sets naar het v2-schema. Ontbrekende
    seed-sets worden toegevoegd; bestaande (mens-gecureerde) sets blijven ongemoeid op hun
    platform-config, maar krijgen wel ontbrekende platform-keys uit de seed. Zoals seed_lexicon."""
    for set_id, rec in _SEED_SETS.items():
        if store.get(set_id) is None:
            store.upsert(set_id, {"id": rec["id"], "label": rec["label"],
                                  "active": rec["active"],
                                  "platforms": _clean_platforms(rec["platforms"])})
    migrate_buzz_query_sets(store)
