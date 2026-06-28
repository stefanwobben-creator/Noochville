"""Gedeelde indicator-definities — de 'metrics-database' die de Librarian cureert.

Een definitie is de grondslag van een indicator (wat telt mee, eenheid, richting, drempel,
meetmoment), losgekoppeld van een specifieke KPI zodat meerdere KPI's dezelfde definitie kunnen
delen. Eén bron, dus vergelijkbaarheid (GAAP/IRIS-idee). De Librarian cureert; anderen lezen vrij,
hetzelfde domein-eigenaarschap als bij het Lexicon en de Library.

Versionering (kern van het migratiebeleid):
- Een definitie wordt NOOIT in-place gewijzigd. `amend()` maakt een nieuwe versie.
- Elke versie legt vast hoe de overgang is gedaan (`migration`):
    'clarify'  = alleen de tekst is verduidelijkt; de reeks blijft één geheel (geen breuk).
    'backcast' = de historie is herrekend op de nieuwe grondslag; de reeks blijft vergelijkbaar.
    'break'    = reeksbreuk: de oude versie is bevroren, de nieuwe versie start vers.
- Samples in de MetricStore dragen de versie waaronder ze gemeten zijn (`defv`), zodat
  back-casten of een breuk tonen later altijd mogelijk is zonder data te verliezen.

Opslag: data/definitions.json. Pure datalaag; migratie-uitvoering en governance leven elders.
"""
from __future__ import annotations

import json
import os
import time
import uuid

from nooch_village.metric_schema import normalize as _norm
from nooch_village.util import atomic_write_json

MIGRATIONS = ("clarify", "backcast", "break")

# de velden die een versie van een definitie vastlegt (subset van het indicator-schema)
_FIELDS = ("name", "unit", "definition", "source", "direction",
           "threshold", "cadence", "meettype", "window")


class DefinitionStore:
    def __init__(self, path: str):
        self.path = path
        self._d: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                x = json.load(open(path))
                if isinstance(x, dict):
                    self._d = x
            except Exception:
                self._d = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._d)

    # ── toevoegen (Librarian cureert) ──────────────────────────────────────────
    def add(self, name: str, owner: str = "", source: str = "seed", **grondslag) -> dict | None:
        spec = _norm(name=name, **grondslag)
        if spec is None:                       # ongeldig (lege naam)
            return None
        did = uuid.uuid4().hex[:12]
        v1 = {"version": 1, "at": time.time(), "migration": "", **spec}
        self._d[did] = {"id": did, "owner": owner, "current": 1,
                        "src": source, "versions": [v1], "created_at": time.time()}
        self._save()
        return self._d[did]

    # ── lezen ──────────────────────────────────────────────────────────────────
    def get(self, did: str) -> dict | None:
        return self._d.get(did)

    def all(self) -> list[dict]:
        return list(self._d.values())

    def current(self, did: str) -> dict | None:
        """De huidige versie-velden van een definitie (of None)."""
        d = self._d.get(did)
        if not d:
            return None
        return next((v for v in d["versions"] if v["version"] == d["current"]), None)

    def version(self, did: str, n: int) -> dict | None:
        d = self._d.get(did)
        if not d:
            return None
        return next((v for v in d["versions"] if v["version"] == n), None)

    def current_version_no(self, did: str) -> int:
        d = self._d.get(did)
        return d["current"] if d else 0

    # ── wijzigen = nieuwe versie (nooit in-place) ──────────────────────────────
    def amend(self, did: str, migration: str, **fields) -> dict | None:
        """Maak een nieuwe versie van een bestaande definitie.

        `migration` ∈ MIGRATIONS bepaalt hoe met de historie is omgegaan. Velden die niet
        worden meegegeven, erven van de huidige versie. Geeft de nieuwe versie terug, of None
        bij een onbekende definitie/migratie of een ongeldige grondslag."""
        d = self._d.get(did)
        if not d or migration not in MIGRATIONS:
            return None
        base = self.current(did) or {}
        merged = {k: base.get(k) for k in _FIELDS}
        merged.update({k: v for k, v in fields.items() if v is not None})
        spec = _norm(**merged)
        if spec is None:
            return None
        n = max(v["version"] for v in d["versions"]) + 1
        ver = {"version": n, "at": time.time(), "migration": migration, **spec}
        d["versions"].append(ver)
        d["current"] = n
        self._save()
        return ver
