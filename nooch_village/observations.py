"""ObservationStore — append-only tijdreeks van operationele metingen.

Opslag: data/observations.jsonl. Elke regel is één JSON-object:
  {role_id, metric, value, ts, datum, bron, meta}
Append-only: het bestand wordt nooit herschreven.

`datum` (YYYY-MM-DD, UTC) en `bron` maken elke observatie zelf-beschrijvend: bij welke dag hoort
de waarde en welke bron heeft 'm geleverd. `record_daily` bewaakt "één datapunt per bron per dag"
(idempotent), zodat een tweede puls op dezelfde dag niet dubbel schrijft.
"""
from __future__ import annotations
import json, os, time
from datetime import datetime, timezone


def _utc_date(ts: float) -> str:
    """De UTC-dag (YYYY-MM-DD) waarin een timestamp valt."""
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


class ObservationStore:

    def __init__(self, path: str):
        self.path = path

    def record(self, role_id: str, metric: str, value,
               ts: float | None = None, meta: dict | None = None,
               bron: str = "", datum: str | None = None) -> None:
        """Voeg één observatie toe aan het einde van het bestand."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        ts = ts if ts is not None else time.time()
        row = {
            "role_id": role_id,
            "metric":  metric,
            "value":   value,
            "ts":      ts,
            "datum":   datum or _utc_date(ts),
            "bron":    bron,
            "meta":    meta or {},
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def rename_metric(self, old_metric: str, new_metric: str, bron: str | None = None) -> int:
        """Hernoem een metric-sleutel in alle bestaande rijen (optioneel per bron); herschrijft het
        bestand. Idempotent: geen rijen met old_metric → 0 wijzigingen. Voor migratie van legacy-
        sleutels naar het canonieke <source>_<field>_day-schema."""
        rows = self._read_all()
        n = 0
        for r in rows:
            if r.get("metric") == old_metric and (bron is None or r.get("bron") == bron):
                r["metric"] = new_metric
                n += 1
        if n:
            with open(self.path, "w") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        return n

    def normalize_source_role_ids(self) -> dict:
        """Canoniek: voor een collector-dagmetric `<bron>_<veld>_day` is `role_id == bron`. Legacy-rijen
        met een andere role_id (bv. `website_watcher` van vóór de generieke collector) worden
        genormaliseerd:
          - botst met een canonieke (role_id==bron) rij met DEZELFDE waarde → oude rij droppen (dedup)
          - geen canonieke rij → role_id hernoemen naar bron (wordt daarmee zelf canoniek)
          - botst met een ANDERE waarde → laten staan (mens beslist; nooit data verliezen)
        Precisie-guard: alleen rijen waar `role_id != bron` ÉN `metric == f"{bron}_*_day"` ÉN bron
        niet-leeg — dat sluit werkoverleg (`werk_*` ≠ `werkoverleg_*`, role_id=cirkel) en de
        `visitors_via_*`-familie structureel uit. Herschrijft het bestand alleen als er iets verandert;
        idempotent (niets te doen → geen herschrijf). Geeft {dropped, renamed, conflicts} terug."""
        rows = self._read_all()
        canon = {}          # (metric, bron, datum) -> value voor role_id==bron (groeit mee bij rename)
        for r in rows:
            if r.get("role_id") == r.get("bron"):
                canon[(r.get("metric"), r.get("bron"), r.get("datum"))] = r.get("value")
        kept, dropped, renamed, conflicts = [], 0, 0, 0
        for r in rows:
            m, b, rid = r.get("metric"), r.get("bron"), r.get("role_id")
            in_scope = (bool(b) and rid != b and isinstance(m, str)
                        and m.startswith(f"{b}_") and m.endswith("_day"))
            if not in_scope:
                kept.append(r)
                continue
            key = (m, b, r.get("datum"))
            if key in canon:
                if canon[key] == r.get("value"):
                    dropped += 1                       # canonieke rij heeft dezelfde waarde → oude weg
                else:
                    conflicts += 1                     # andere waarde → niet aanraken
                    kept.append(r)
            else:
                r["role_id"] = b                       # geen canonieke rij → hernoemen (wordt canoniek)
                canon[key] = r.get("value")
                renamed += 1
                kept.append(r)
        if dropped or renamed:
            with open(self.path, "w") as f:
                for r in kept:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        return {"dropped": dropped, "renamed": renamed, "conflicts": conflicts}

    def record_daily(self, role_id: str, metric: str, value, bron: str,
                     datum: str | None = None, ts: float | None = None) -> bool:
        """Schrijf hoogstens één datapunt per (role_id, metric, bron, datum). Bestaat er al een voor
        die dag+bron, dan niets doen (append-only, idempotent). Geeft True als er geschreven is."""
        ts = ts if ts is not None else time.time()
        datum = datum or _utc_date(ts)
        for row in self._read_all():
            if (row.get("role_id") == role_id and row.get("metric") == metric
                    and row.get("bron") == bron and row.get("datum") == datum):
                return False
        self.record(role_id, metric, value, ts=ts, bron=bron, datum=datum)
        return True

    def _read_all(self) -> list[dict]:
        """Alle regels als dicts (ongefilterd, ongesorteerd). Lege regels worden overgeslagen."""
        if not os.path.exists(self.path):
            return []
        rows = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def series(self, role_id: str, metric: str) -> list[dict]:
        """Alle observaties voor role_id + metric, oplopend op ts."""
        rows = [r for r in self._read_all()
                if r.get("role_id") == role_id and r.get("metric") == metric]
        rows.sort(key=lambda r: r["ts"])
        return rows

    def latest(self, role_id: str, metric: str) -> dict | None:
        """Laatste observatie voor role_id + metric, of None."""
        rows = self.series(role_id, metric)
        return rows[-1] if rows else None

    def _actueel(self, metric: str, bron: str | None = None):
        """De laatste bekende dagwaarde voor een metric (bron), of None. Voor 'Actueel' op het
        dashboard: dezelfde betekenis als bij Plausible — de meest recente dag-observatie."""
        rows = self.daily_series(metric, bron=bron)
        return rows[-1]["value"] if rows else None

    def daily_series(self, metric: str, bron: str | None = None,
                     role_id: str | None = None) -> list[dict]:
        """De dagreeks van een metric (optioneel op bron en/of rol gefilterd), oplopend op ts.
        De één-per-dag-garantie komt van `record_daily`; hier wordt alleen gelezen. Site-brede
        metrics (bv. bezoekers) laat je role_id weg — dan telt de reeks over alle rollen."""
        rows = [r for r in self._read_all()
                if r.get("metric") == metric
                and (bron is None or r.get("bron") == bron)
                and (role_id is None or r.get("role_id") == role_id)]
        rows.sort(key=lambda r: r["ts"])
        return rows


# ── dag-observaties per bron (uitrol van de Plausible-aanpak, scope 2) ──────────
# Metric-namen: <bron>_<measure>_day. record_daily blijft idempotent op rol/metric/bron/dag.
WERK_DAILY = {"tevredenheid": "werk_tevredenheid_day", "duur": "werk_duur_day"}
SHOPIFY_DAILY = {m: f"shopify_{m}_day" for m in ("pairs_sold", "orders", "revenue", "aov")}


def record_werk_daily(store: "ObservationStore", circle: str, snap: dict) -> None:
    """Dagwaarden (tevredenheid + duur) van een gesloten werkoverleg → observatie-store, idempotent
    per dag. NAAST de bestaande all-time aggregaten in de werk-log (niet ter vervanging)."""
    if not snap:
        return
    datum = _utc_date(snap.get("at") or time.time())
    if snap.get("tevredenheid") is not None:
        store.record_daily(circle, WERK_DAILY["tevredenheid"], snap["tevredenheid"],
                           bron="werkoverleg", datum=datum)
    if snap.get("duur_min") is not None:
        store.record_daily(circle, WERK_DAILY["duur"], snap["duur_min"], bron="werkoverleg", datum=datum)

# NB: de Shopify-dagwaarden lopen nu via de generieke collector (DataSourceSkill.daily_values →
# record_daily onder shopify_<field>_day). SHOPIFY_DAILY blijft de sleutel-map voor de tegel-lezer.
