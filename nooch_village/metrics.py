"""Metrics — een dashboard van KPI's en links per rol/cirkel.

Twee soorten, in dezelfde tab:
- link: naam + URL naar een extern bestand/dashboard (zoals GlassFrog).
- kpi: naam + eenheid + een reeks metingen over tijd. Een KPI is óf handmatig (samples in de store,
  ook door agents/AI te schrijven) óf bron-gebaseerd (`source`, bijv. de bezoekers uit pulse_history).

Een KPI hoort bij een node (meestal een rol: die 'levert de data'). Op cirkelniveau stelt de Lead Link
het dashboard samen door KPI's te PINNEN (uit alle KPI's onder de cirkel). Opslag: data/metrics.json.
"""
from __future__ import annotations
import json
import os
import time
import uuid

from nooch_village.metric_schema import normalize as _normalize_indicator
from nooch_village.util import atomic_write_json


class MetricStore:
    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        self._pins: dict[str, list] = {}
        self._tiles: dict[str, list] = {}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._items = d.get("items", {}) if "items" in d else {}
                    self._pins = d.get("pins", {})
                    self._tiles = d.get("tiles", {})
            except Exception:
                self._items, self._pins, self._tiles = {}, {}, {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, {"items": self._items, "pins": self._pins, "tiles": self._tiles})

    # ── tegels (dashboard-compositie: bron + measure + dimensie + vorm) ────────
    def add_tile(self, node: str, source: str, measure: str, dim: str, form: str,
                 target=None, goal_pid: str = "") -> dict | None:
        if not node or not source or not measure:
            return None
        try:
            tgt = float(target) if str(target or "").strip() not in ("", "None") else None
        except (TypeError, ValueError):
            tgt = None
        tid = uuid.uuid4().hex[:12]
        # goal_pid koppelt de indicator aan een doel (project = outcome + deadline). De indicator
        # geeft informatie; het doel is het project, niet de meter.
        tile = {"id": tid, "node": node, "source": source, "measure": measure,
                "dim": dim or "none", "form": form or "getal", "target": tgt,
                "goal_pid": (goal_pid or "").strip()}
        self._tiles.setdefault(node, []).append(tile)
        self._save()
        return tile

    def tiles_of(self, node: str) -> list[dict]:
        return list(self._tiles.get(node, []))

    def remove_tile(self, node: str, tid: str) -> bool:
        before = self._tiles.get(node, [])
        after = [t for t in before if t.get("id") != tid]
        if len(after) != len(before):
            self._tiles[node] = after
            self._save()
            return True
        return False

    # ── toevoegen ────────────────────────────────────────────────────────────
    def add_link(self, node: str, name: str, url: str) -> dict | None:
        name, url = (name or "").strip(), (url or "").strip()
        if not node or not name or not url:
            return None
        mid = uuid.uuid4().hex[:12]
        it = {"id": mid, "kind": "link", "node": node, "name": name[:120], "url": url[:400],
              "created_at": time.time()}
        self._items[mid] = it
        self._save()
        return it

    def add_kpi(self, node: str, name: str, unit: str = "", source: str = "",
                definition: str = "", direction: str = "", threshold=None,
                cadence: str = "ad-hoc", meettype: str = "snapshot", window: str = "",
                def_id: str = "", def_version: int = 0, origin: str = "",
                auto: bool = False, meetwijze: str = "") -> dict | None:
        if not node:
            return None
        # grondslag + meetmoment worden gevalideerd/genormaliseerd door het indicator-schema
        # (GAAP/IRIS: wat telt mee, eenheid, richting, drempel; meetmoment: cadans + meettype).
        spec = _normalize_indicator(name=name, unit=unit, source=source, definition=definition,
                                    direction=direction, threshold=threshold, cadence=cadence,
                                    meettype=meettype, window=window)
        if spec is None:                       # ongeldig (lege naam): KPI niet aanmaken
            return None
        mid = uuid.uuid4().hex[:12]
        # def_id/def_version koppelen de KPI aan een gedeelde catalogus-definitie (Librarian).
        # Leeg = een losse, niet-gedeelde KPI (de toegestane uitzondering).
        it = {"id": mid, "kind": "kpi", "node": node, **spec, "samples": [],
              "def_id": (def_id or "").strip(), "def_version": int(def_version or 0),
              "origin": (origin or "").strip(), "auto": bool(auto),
              "meetwijze": (meetwijze or "").strip(), "created_at": time.time()}
        self._items[mid] = it
        self._save()
        return it

    def add_sample(self, mid: str, value, at: float | None = None) -> bool:
        it = self._items.get(mid)
        if it is None or it.get("kind") != "kpi" or it.get("source") or it.get("auto"):
            return False                       # bron-/systeem-KPI's worden gevoed; geen handmatige sample
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        # defv = de definitie-versie waaronder gemeten is; nodig om later te back-casten of een
        # reeksbreuk te tonen. 0 voor een losse KPI zonder catalogus-definitie.
        it.setdefault("samples", []).append({"at": at or time.time(), "value": v,
                                             "defv": int(it.get("def_version", 0))})
        self._save()
        return True

    def remove(self, mid: str) -> bool:
        if mid not in self._items:
            return False
        del self._items[mid]
        for c, ids in list(self._pins.items()):
            if mid in ids:
                self._pins[c] = [i for i in ids if i != mid]
        self._save()
        return True

    # ── lezen ────────────────────────────────────────────────────────────────
    def get(self, mid: str) -> dict | None:
        return self._items.get(mid)

    def for_node(self, node: str) -> list[dict]:
        return [i for i in self._items.values() if i.get("node") == node]

    def kpis_for_def(self, did: str) -> list[dict]:
        return [i for i in self._items.values() if i.get("kind") == "kpi" and i.get("def_id") == did]

    def retune_kpis_to_def(self, did: str, version: int, fields: dict, migration: str) -> int:
        """Pas alle KPI's die naar deze definitie verwijzen aan op een nieuwe definitie-versie.

        - clarify : grondslag bijwerken, def_version ophogen; samples blijven één doorlopende reeks.
        - backcast: idem, plus alle bestaande samples herstempelen op de nieuwe versie (de mens
                    stelt dat de historie vergelijkbaar blijft) → nog steeds één reeks.
        - break   : grondslag bijwerken, def_version ophogen; oude samples houden hun oude defv en
                    de nieuwe versie wordt als breukpunt vastgelegd (sparkline tekent een lijn)."""
        copy = ("name", "unit", "definition", "direction", "threshold", "cadence", "meettype",
                "window", "meetwijze")
        n = 0
        for it in self.kpis_for_def(did):
            for k in copy:
                if k in fields:
                    it[k] = fields[k]
            if "meetwijze" in fields:            # meetwijze bepaalt of handmatig invoeren mag
                it["auto"] = fields["meetwijze"] == "systeem"
            it["def_version"] = int(version)
            if migration == "backcast":
                for s in it.get("samples", []):
                    s["defv"] = int(version)
            elif migration == "break":
                it.setdefault("breaks", []).append(int(version))
            n += 1
        if n:
            self._save()
        return n

    def kpis_for_nodes(self, node_ids) -> list[dict]:
        s = set(node_ids)
        return [i for i in self._items.values() if i.get("kind") == "kpi" and i.get("node") in s]

    def links_for(self, node: str) -> list[dict]:
        return [i for i in self._items.values() if i.get("kind") == "link" and i.get("node") == node]

    # ── cirkel-pins (Lead Link kiest het dashboard) ───────────────────────────
    def pin(self, circle: str, mid: str) -> None:
        ids = self._pins.setdefault(circle, [])
        if mid not in ids:
            ids.append(mid)
            self._save()

    def unpin(self, circle: str, mid: str) -> None:
        if mid in self._pins.get(circle, []):
            self._pins[circle] = [i for i in self._pins[circle] if i != mid]
            self._save()

    def is_pinned(self, circle: str, mid: str) -> bool:
        return mid in self._pins.get(circle, [])

    def pins_of(self, circle: str) -> list[str]:
        return list(self._pins.get(circle, []))


def window_cutoff(win: str, now: float | None = None) -> float | None:
    """Begin-timestamp voor een tijdvenster; None = alles."""
    now = now or time.time()
    day = 86400
    return {"vandaag": now - day, "7d": now - 7 * day, "week": now - 7 * day,
            "maand": now - 30 * day, "kwartaal": now - 91 * day}.get(win)


def filter_samples(samples, cutoff: float | None):
    """(at, value)-paren binnen het venster, op tijd gesorteerd."""
    pts = [(s["at"], s["value"]) for s in samples if "at" in s]
    if cutoff is not None:
        pts = [p for p in pts if p[0] >= cutoff]
    return sorted(pts, key=lambda p: p[0])
