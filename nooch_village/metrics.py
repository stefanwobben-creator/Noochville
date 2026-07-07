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

from nooch_village.metric_schema import normalize as _normalize_indicator, SCHEMA_FIELDS as _SCHEMA_FIELDS
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
                 target=None, goal_pid: str = "", ref_kind: str = "",
                 extra: dict | None = None) -> dict | None:
        if not node or not source or not measure:
            return None
        try:
            tgt = float(target) if str(target or "").strip() not in ("", "None") else None
        except (TypeError, ValueError):
            tgt = None
        tid = uuid.uuid4().hex[:12]
        # Een KPI = indicator (source/measure) + referentie + vorm. ref_kind maakt de referentie
        # expliciet: "" geen, "benchmark" (vergelijkwaarde = target), "doel" (project = goal_pid).
        # `extra` draagt optionele extra velden (bv. een formule: f_a/f_op/f_b/aggregatie).
        tile = {"id": tid, "node": node, "source": source, "measure": measure,
                "dim": dim or "none", "form": form or "getal", "target": tgt,
                "goal_pid": (goal_pid or "").strip(),
                "ref_kind": ref_kind if ref_kind in ("benchmark", "doel") else ""}
        if extra:
            tile.update({k: v for k, v in extra.items() if k not in tile})
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

    def migrate_metric_bindings(self, defs) -> dict:
        """Wezen-sweep (idempotent): systeem-KPI's met ontbrekende `veld`/`categorie` krijgen die alsnog
        uit hun catalogus-def (alleen lege velden vullen; niet-afleidbare → rapporteren, niet gokken).
        Plus: kpi:-tegels die naar een reeks-KPI wijzen maar dim='none' hebben → dim='time' (grafiek i.p.v.
        los getal). Geeft {repaired, unresolved, tiles_fixed} en schrijft alleen bij een echte wijziging."""
        repaired, unresolved, tiles_fixed = [], [], []
        changed = False
        for mid, it in list(self._items.items()):
            if it.get("kind") != "kpi":
                continue
            # systeem = door een bron/auto/meetwijze gevoed (NIET alleen `source`: een pre-fix KPI heeft
            # source='' maar auto=True). Zie ook _is_system_kpi in views/metrics.py (één criterium).
            is_sys = bool(it.get("source") or it.get("origin") or it.get("auto")
                          or it.get("meetwijze") == "systeem")
            if not is_sys or (it.get("veld") and it.get("categorie")):
                continue
            cur = defs.current(it.get("def_id")) if it.get("def_id") else None
            if not cur:
                if not it.get("veld"):
                    unresolved.append({"id": mid, "name": it.get("name"),
                                       "reason": "geen catalogus-def om veld af te leiden"})
                continue
            for f in ("veld", "categorie", "aard"):
                if not it.get(f) and cur.get(f):
                    it[f] = cur[f]
                    changed = True
            if it.get("veld"):
                repaired.append({"id": mid, "name": it.get("name"),
                                 "veld": it.get("veld"), "categorie": it.get("categorie")})
            else:
                unresolved.append({"id": mid, "name": it.get("name"), "reason": "def draagt zelf geen veld"})
        for node, tl in self._tiles.items():
            for t in tl:
                src = t.get("source", "")
                if src.startswith("kpi:") and t.get("dim") == "none":
                    k = self._items.get(src[4:])
                    if k and k.get("aard") == "reeks":
                        t["dim"] = "time"
                        tiles_fixed.append({"node": node, "tile": t.get("id"), "kpi": src[4:]})
                        changed = True
        if changed:
            self._save()
        return {"repaired": repaired, "unresolved": unresolved, "tiles_fixed": tiles_fixed}

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
                auto: bool = False, meetwijze: str = "", benchmark: str = "",
                bron_url: str = "", verificatie: str = "", tijd: str = "", bruikbaar: str = "",
                standaard: str = "", waarde=None, veld: str = "", categorie: str = "",
                aard: str = "") -> dict | None:
        if not node:
            return None
        # grondslag + meetmoment worden gevalideerd/genormaliseerd door het indicator-schema
        # (GAAP/IRIS: wat telt mee, eenheid, richting, drempel; meetmoment: cadans + meettype).
        # veld/categorie/aard komen mee uit de catalogus-def (create-flow): zonder `veld` kan geen enkel
        # pad de bron-dagreeks (<source>_<veld>_day) reconstrueren. `aard` alleen doorgeven als gezet;
        # anders leidt het schema 'm af uit het meettype.
        extra = {"veld": veld, "categorie": categorie}
        if aard:
            extra["aard"] = aard
        spec = _normalize_indicator(name=name, unit=unit, source=source, definition=definition,
                                    direction=direction, threshold=threshold, cadence=cadence,
                                    meettype=meettype, window=window, **extra)
        if spec is None:                       # ongeldig (lege naam): KPI niet aanmaken
            return None
        mid = uuid.uuid4().hex[:12]
        # def_id/def_version koppelen de KPI aan een gedeelde catalogus-definitie (Librarian).
        # Leeg = een losse, niet-gedeelde KPI (de toegestane uitzondering).
        it = {"id": mid, "kind": "kpi", "node": node, **spec, "samples": [],
              "def_id": (def_id or "").strip(), "def_version": int(def_version or 0),
              "origin": (origin or "").strip(), "auto": bool(auto),
              "meetwijze": (meetwijze or "").strip(), "benchmark": (benchmark or "").strip(),
              "bron_url": (bron_url or "").strip(), "verificatie": (verificatie or "").strip(),
              "tijd": (tijd or "").strip(), "bruikbaar": (bruikbaar or "").strip(),
              "standaard": (standaard or "").strip(), "waarde": waarde,
              "created_at": time.time()}
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
        # alle definitievelden behalve `source` (de KPI bewaart herkomst als `origin`); afgeleid uit
        # het schema zodat de lijst niet uit de pas loopt (reference, don't copy / één bron).
        copy = tuple(f for f in _SCHEMA_FIELDS if f != "source")
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
    """Begin-timestamp voor een tijdvenster; None = alles. (Legacy; nieuwe code gebruikt window_range.)"""
    now = now or time.time()
    day = 86400
    return {"vandaag": now - day, "7d": now - 7 * day, "week": now - 7 * day,
            "maand": now - 30 * day, "kwartaal": now - 91 * day}.get(win)


def _parse_date(s: str) -> float | None:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat((s or "").strip()[:10])
        return _dt.datetime(d.year, d.month, d.day).timestamp()
    except Exception:
        return None


def window_range(win: str, now: float | None = None, van: str = "", tot: str = ""):
    """(start_ts, end_ts) voor de centrale periode-picker. start/end None = onbegrensd aan die kant.
    Vandaag/Gisteren zijn kalenderdagen; 7d/28d/kwartaal/jaar zijn rollend; Actueel = alles (laatste
    waarde telt); Aangepast = van/tot (tot inclusief)."""
    import datetime as _dt
    now = now or time.time()
    day = 86400.0
    d = _dt.datetime.fromtimestamp(now)
    today0 = _dt.datetime(d.year, d.month, d.day).timestamp()
    table = {
        "vandaag": (today0, now),
        "gisteren": (today0 - day, today0),
        "7d": (now - 7 * day, now),
        "28d": (now - 28 * day, now),
        "kwartaal": (now - 91 * day, now),
        "jaar": (now - 365 * day, now),
        "actueel": (None, now),
    }
    if win in table:
        return table[win]
    if win == "aangepast":
        s, e = _parse_date(van), _parse_date(tot)
        return (s, (e + day) if e is not None else now)   # tot-dag inclusief
    return (None, now)                                     # 'alles' / onbekend


def filter_samples(samples, cutoff: float | None, end: float | None = None):
    """(at, value)-paren binnen [cutoff, end], op tijd gesorteerd. end None = geen bovengrens
    (backward-compatible met de oude cutoff-aanroepen)."""
    pts = [(s["at"], s["value"], s.get("datum")) for s in samples if "at" in s]
    if cutoff is not None:
        pts = [p for p in pts if p[0] >= cutoff]
    if end is not None:
        pts = [p for p in pts if p[0] <= end]
    return sorted(pts, key=lambda p: p[0])
