"""ObservationStore — append-only tijdreeks van operationele metingen.

Opslag: data/observations.jsonl. Elke regel is één JSON-object:
  {role_id, metric, value, ts, meta}
Append-only: het bestand wordt nooit herschreven.
"""
from __future__ import annotations
import json, os, time


class ObservationStore:

    def __init__(self, path: str):
        self.path = path

    def record(self, role_id: str, metric: str, value,
               ts: float | None = None, meta: dict | None = None) -> None:
        """Voeg één observatie toe aan het einde van het bestand."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        row = {
            "role_id": role_id,
            "metric":  metric,
            "value":   value,
            "ts":      ts if ts is not None else time.time(),
            "meta":    meta or {},
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def series(self, role_id: str, metric: str) -> list[dict]:
        """Alle observaties voor role_id + metric, oplopend op ts."""
        if not os.path.exists(self.path):
            return []
        rows = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row["role_id"] == role_id and row["metric"] == metric:
                    rows.append(row)
        rows.sort(key=lambda r: r["ts"])
        return rows

    def latest(self, role_id: str, metric: str) -> dict | None:
        """Laatste observatie voor role_id + metric, of None."""
        rows = self.series(role_id, metric)
        return rows[-1] if rows else None
