"""EvidenceLedger — De Kroniek: het append-only bewijsregister van het dorp (fase 1: onthouden).

Elke skill-run — feit, leegte ÓF fout — landt als één getypte regel. `leeg` en `fout` zijn eersteklas
resultaten, geen stilte: hierop leert de skill-ladder (dode route → alternatief pad) en escaleert de
mens pas als láátste tree. Het register is het geheugen dat leren, interpreteren en ontdekken mogelijk
maakt.

Opslag: append-only `data/evidence_ledger.jsonl`, elke regel één JSON-object:
  {id, role_id, skill, query, source, status, result_ref, ts}
- `status` ∈ {"bevestigd", "leeg", "fout"} — bevestigd = bruikbaar resultaat; leeg = bron gaf niets
  terug (no_data, geen fout); fout = de bron/aanroep faalde (HTTP, timeout, config).
- `result_ref` = optionele verwijzing naar het volledige resultaat elders (bv. een deliverable-id),
  zodat de ledger licht blijft.

Concurrency: append onder `util.file_lock` (fcntl-flock op `<pad>.lock`), zodat daemon en cockpit veilig
naast elkaar schrijven — conform de conventie "fcntl-flock op alle JSON-stores". Lezen is lock-vrij
(verse read per instance, incrementeel bijgewerkt bij record). Eén schrijvende instance per proces.

Eigenaarschap (governance): de Librarian is hoeder/curator van dit register (bibliotheek-domein van
woorden → bewijs); harry_hemp is de zwaarste vuller en zet de waarheidslat; alle rollen voeden, lezen
is vrij.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from nooch_village.util import file_lock

log = logging.getLogger("village.evidence")

# De drie eersteklas uitkomsten. leeg ≠ fout: een lege bron is een echt (no_data-)feit, geen mislukking.
STATUSES = ("bevestigd", "leeg", "fout")


class EvidenceLedger:
    def __init__(self, path: str):
        self.path = path
        self._rows: list[dict] | None = None       # lazy cache; verse read per instance

    def _ensure(self) -> None:
        if self._rows is not None:
            return
        self._rows = []
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                for ln, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._rows.append(json.loads(line))
                    except ValueError:
                        # Corrupte regel: fail-loud overslaan (nooit stil), rest blijft leesbaar.
                        log.warning("EVIDENCE_CORRUPT: regel %d in %s onleesbaar — overgeslagen", ln, self.path)

    # ── schrijven (append onder flock) ─────────────────────────────────────────
    def record(self, *, role_id: str, skill: str, query: str, source: str, status: str,
               result_ref: str = "", ts: float | None = None, meta: dict | None = None) -> dict:
        """Voeg één bewijsrecord toe. `status` moet in STATUSES zitten (fail-closed: een onbekende status
        is een programmeerfout, geen stille default). Geeft het geschreven record terug."""
        if status not in STATUSES:
            raise ValueError(f"ongeldige status {status!r} — verwacht een van {STATUSES}")
        row = {
            "id":         uuid.uuid4().hex[:12],
            "role_id":    role_id,
            "skill":      skill,
            "query":      query,
            "source":     source,
            "status":     status,
            "result_ref": result_ref or "",
            "ts":         ts if ts is not None else time.time(),
        }
        if meta:
            row["meta"] = meta
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        with file_lock(self.path):                 # procesbrede flock → veilige append naast de daemon
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        if self._rows is not None:                 # cache incrementeel bij (geen herlees van het bestand)
            self._rows.append(row)
        return row

    # ── lezen (lock-vrij) ──────────────────────────────────────────────────────
    def all_records(self) -> list[dict]:
        self._ensure()
        return list(self._rows)

    def for_skill(self, skill: str) -> list[dict]:
        return [r for r in self.all_records() if r.get("skill") == skill]

    def for_query(self, skill: str, query: str) -> list[dict]:
        return [r for r in self.all_records() if r.get("skill") == skill and r.get("query") == query]

    def last(self, skill: str, query: str, source: str | None = None) -> dict | None:
        """De meest recente run voor deze vraag (optioneel op bron), of None."""
        rows = [r for r in self.for_query(skill, query) if source is None or r.get("source") == source]
        return max(rows, key=lambda r: r.get("ts", 0)) if rows else None

    def last_good(self, skill: str, query: str) -> dict | None:
        """Geheugen-eerst: het meest recente BEVESTIGDE resultaat voor deze vraag, of None. Een rol
        raadpleegt dit vóór een dure call — 'weten we dit al?'."""
        rows = [r for r in self.for_query(skill, query) if r.get("status") == "bevestigd"]
        return max(rows, key=lambda r: r.get("ts", 0)) if rows else None

    def consecutive_failures(self, skill: str, source: str) -> int:
        """Hoe vaak op rij deze (skill, source) het laatst faalde (status='fout'), geteld vanaf de
        nieuwste terug tot de eerste niet-fout. De skill-ladder gebruikt dit om een dode route te
        snoeien of te escaleren; een bevestigd/leeg resultaat breekt de reeks."""
        rows = sorted((r for r in self.all_records()
                       if r.get("skill") == skill and r.get("source") == source),
                      key=lambda r: r.get("ts", 0), reverse=True)
        n = 0
        for r in rows:
            if r.get("status") == "fout":
                n += 1
            else:
                break
        return n


# ── skill-ladder: dode route → alternatief pad, escaleren als LÁÁTSTE tree (leren, De Kroniek) ──
def classify_result(result) -> str:
    """Standaard-classificatie van een skill-resultaat → Kroniek-status. fout = de bron faalde
    (error-veld of None); leeg = de bron werkte maar gaf niets (no_data of een lege resultaatlijst);
    bevestigd = bruikbaar resultaat. Generaliseert de huisstijl (error/no_data) van de skills."""
    if result is None:
        return "leeg"
    if isinstance(result, dict):
        if result.get("error"):
            return "fout"
        if result.get("no_data"):
            return "leeg"
        for k in ("patents", "hits", "results", "rows", "items", "works", "targets"):
            if k in result and not result[k]:
                return "leeg"
    return "bevestigd"


def run_with_ladder(ledger, *, role_id, skill, query, rungs, classify=None, escalate=None) -> dict:
    """Loop de fallback-trappen (`rungs`) af tot een BEVESTIGD resultaat; log elke uitkomst in de Kroniek.

    `rungs` = [(source, callable)]; `callable()` → resultaat (of raise = fout). De eerste bevestigde
    tree wint en stopt de ladder. Escaleren naar de mens is de LÁÁTSTE tree: alleen als geen enkele tree
    bevestigde ÉN minstens één een fout gaf (operationeel probleem, bv. bron down). Gaven alle trees
    'leeg', dan is dat een legitiem no_data — géén escalatie (B3: leeg is een echt feit, geen mislukking).

    Geeft {status, source, result, escalated, trail}."""
    classify = classify or classify_result
    trail: list[dict] = []
    for source, fn in rungs:
        try:
            result = fn()
            status = classify(result)
        except Exception as exc:
            result, status = {"error": str(exc)}, "fout"
        rec = ledger.record(role_id=role_id, skill=skill, query=query, source=source, status=status)
        trail.append({"source": source, "status": status, "result": result, "record_id": rec["id"]})
        if status == "bevestigd":
            return {"status": "bevestigd", "source": source, "result": result,
                    "escalated": False, "trail": trail}
    escalated = False
    if any(t["status"] == "fout" for t in trail) and escalate is not None:
        escalate(skill=skill, query=query, trail=trail)          # precies één keer, na uitputting
        escalated = True
    last = trail[-1] if trail else {"status": "leeg", "source": None, "result": None}
    return {"status": last["status"], "source": last["source"], "result": last.get("result"),
            "escalated": escalated, "trail": trail}
