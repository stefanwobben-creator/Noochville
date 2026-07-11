"""BuzzObservationStore — append-only tijdreeks van community-observaties (v1: Reddit).

Opslag: data/buzz_observations.jsonl. Elke regel is één observatie-rij:
  {id, platform, subreddit, permalink, title, fragment, score, num_comments,
   created_utc, fetched_at, query, query_set_id}

Zelfde patroon als ObservationStore: append-only (het bestand wordt nooit herschreven) met een
lazy in-memory index. De index (alle rijen + een dedup-set op de canonieke `permalink`) wordt
éénmaal per instance uit het bestand opgebouwd en incrementeel bijgewerkt bij `record_observation`.
Zo is de dedup O(1) i.p.v. een lineaire scan per write.

Bewust GEEN sentiment- of insight-veld: dit is een grounded ophaal-store, geen oordeel. Aanname
(zoals ObservationStore): één schrijvende instance per proces.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from nooch_village.util import JsonStore, refuse

log = logging.getLogger(__name__)


class BuzzCache(JsonStore):
    """6u-response-cache per (platform, query/kanaal) zodat een dubbele puls geen dubbele requests
    doet. Achter de JsonStore-basis: flock + verse read onder het slot, zoals elke store. Sleutel =
    fetcher-specifiek (bv. "reddit::<sub>::<query>", "youtube::q::<query>"), waarde =
    {"ts": laatste-fetch, "n": aantal resultaten}.

    Additief (v2): een dag-quotateller onder een EIGEN namespaced sleutel `quota:<platform>:<datum>`
    voor de YouTube-quota-guard. De 6u-ts/mark-logica blijft ongewijzigd; de teller deelt alleen het
    bestand + slot."""

    _WRITE_METHODS = ("mark", "quota_add", "set_sync_terms")
    _STATE = "_items"
    _default = dict
    _EXPECT = dict

    def ts(self, key: str) -> float:
        return float((self._items.get(key) or {}).get("ts", 0) or 0)

    def mark(self, key: str, ts: float, n: int = 0) -> None:
        self._items[key] = {"ts": ts, "n": int(n)}
        self._save()

    # ── library-sync-stand (v2.1: vorige gesyncte term-set per set/platform) ────
    # Bewust in de cache, NIET in de query-set: die blijft mens-bewerkbaar zonder machine-writes.
    def sync_terms(self, key: str) -> list:
        return list((self._items.get(key) or {}).get("terms") or [])

    def set_sync_terms(self, key: str, terms) -> None:
        self._items[key] = {"terms": list(terms)}
        self._save()

    # ── quota-teller (YouTube) ────────────────────────────────────────────────
    @staticmethod
    def _quota_key(platform: str, day: str) -> str:
        return f"quota:{platform}:{day}"

    def quota_used(self, platform: str, day: str) -> int:
        return int((self._items.get(self._quota_key(platform, day)) or {}).get("units", 0) or 0)

    def quota_add(self, platform: str, day: str, units: int) -> int:
        k = self._quota_key(platform, day)
        total = int((self._items.get(k) or {}).get("units", 0) or 0) + int(units)
        self._items[k] = {"units": total}
        self._save()
        return total

# De velden die een observatie-rij draagt (self-documenting; ook de test leunt hierop).
# v2: context_id/context_title (nullable) duiden een comment aan zijn video/post — tegen het
# frame-effect. Oude rijen zonder deze velden blijven geldig (append-only, geen herschrijf).
FIELDS = ("id", "platform", "subreddit", "permalink", "title", "fragment",
          "score", "num_comments", "created_utc", "fetched_at", "query", "query_set_id",
          "context_id", "context_title")


class BuzzObservationStore:
    """Append-only JSONL met lazy dedup-index op `permalink` (de canonieke bron-sleutel)."""

    def __init__(self, path: str):
        self.path = path
        self._rows: list[dict] | None = None       # lazy cache: alle rijen
        self._seen: set[str] | None = None         # set van permalinks → O(1) dedup

    def _ensure_cache(self) -> None:
        if self._rows is not None:
            return
        self._rows, self._seen = [], set()
        if os.path.exists(self.path):
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._index(json.loads(line))

    def _index(self, r: dict) -> None:
        self._rows.append(r)
        pl = r.get("permalink")
        if pl:
            self._seen.add(pl)

    def has(self, permalink: str) -> bool:
        """Is deze permalink al gezien? O(1) via de index."""
        if not permalink:
            return False
        self._ensure_cache()
        return permalink in self._seen

    def record_observation(self, row: dict) -> bool:
        """Voeg één observatie-rij toe. Fail-closed:
          - geen `permalink` → refuse(BUZZ_NO_SOURCE) + False (rij geweigerd);
          - permalink al gezien → False (idempotent, geen dubbel);
          - anders append aan het bestand + index-update → True.
        Ontbrekende velden worden met een lege default aangevuld zodat elke regel het volledige
        schema draagt."""
        permalink = (row.get("permalink") or "").strip()
        if not permalink:
            return refuse("BUZZ_NO_SOURCE", "observatie zonder permalink geweigerd",
                          subreddit=row.get("subreddit"), query=row.get("query"))
        self._ensure_cache()
        if permalink in self._seen:
            return False
        clean = {k: row.get(k) for k in FIELDS}
        clean["permalink"] = permalink
        clean["id"] = clean.get("id") or uuid.uuid4().hex[:12]
        clean["platform"] = clean.get("platform") or "reddit"
        clean["fetched_at"] = clean.get("fetched_at") or time.time()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(clean, ensure_ascii=False, default=str) + "\n")
        self._index(clean)
        return True

    def all(self) -> list[dict]:
        """Alle rijen (kopie van de index), oudste eerst (schrijfvolgorde)."""
        self._ensure_cache()
        return list(self._rows)

    def for_set(self, query_set_id: str) -> list[dict]:
        """Alle rijen van één zoek-set."""
        return [r for r in self.all() if r.get("query_set_id") == query_set_id]

    def top_by_score(self, query_set_id: str, limit: int = 5, platform: str | None = None) -> list[dict]:
        """De hoogst scorende rijen van een set (voor de wall-samenvatting van Billy Buzz),
        optioneel gefilterd op platform. Score-vergelijking tússen platforms is appels/peren
        (YT-likes vs Bluesky-likes) — daarom filtert de wall per platform en normaliseert niet."""
        rows = [r for r in self.for_set(query_set_id)
                if platform is None or r.get("platform") == platform]
        rows.sort(key=lambda r: (r.get("score") or 0), reverse=True)
        return rows[:limit]
