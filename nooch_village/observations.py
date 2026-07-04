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
