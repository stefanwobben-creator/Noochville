"""Staging-ronde voor handmatige intake (layout-brief zone 2).

Permissieve intake, strenge uitgang: een toegevoegde bron wordt eerst geatomiseerd naar een
STAGING-batch (hier), NIET meteen de bibliotheek in. De mens kijkt na — bewerken, samenvoegen,
weggooien — en pas op "Voeg set toe aan bibliotheek" landen de atomen append-only in notes.json.
Zo ruim je rommel (zoals enumeratie-broertjes) op vóór het de bibliotheek vervuilt.

Bulk/auto-ingest (backfill, re-atomiseer) heeft geen mens om na te kijken en gaat rechtstreeks
de bibliotheek in — die raakt deze staging dus niet. Uitzondering: de rapport-lus
(project_signal.report_to_staging) is wél auto-geïnitieerd maar landt bewust HIER — een
projectrapport verdient dezelfde mens-review als een handmatig toegevoegde bron.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from nooch_village.kennisbank_intake import atoom_kaart, SUBJECTS
from nooch_village.notes_store import NotesStore
from nooch_village.util import JsonStore


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class StagingStore(JsonStore):
    """Eén batch = {id, kind, source_label, tabular, by, created_at,
    atoms:[{sid, content, body, subject, provenance, source, reference, flags}]}.
    De atoom-`sid` is batch-lokaal (staging), niet de definitieve bibliotheek-id."""

    _WRITE_METHODS = ("create", "edit_atom", "remove_atom", "merge_atoms", "discard")

    def get(self, bid: str) -> dict | None:
        return self._items.get(bid)

    def open_batches(self) -> list[dict]:
        return sorted(self._items.values(), key=lambda b: b.get("created_at") or "",
                      reverse=True)

    def create(self, kind: str, source_label: str, atoms: list[dict], *,
               tabular: bool = False, by: str = "") -> str:
        bid = "stg_" + uuid.uuid4().hex[:8]
        self._items[bid] = {
            "id": bid, "kind": kind, "source_label": source_label, "tabular": tabular,
            "by": by, "created_at": _now(),
            "atoms": [{"sid": f"s{i}",
                       "content": (a.get("content") or "").strip(),
                       "body": a.get("body"),
                       "subject": a.get("subject") if a.get("subject") in SUBJECTS else "",
                       "provenance": a.get("provenance") or "unknown",
                       "source": (a.get("source") or source_label or "onbekend").strip(),
                       "reference": a.get("reference"),
                       "source_date": a.get("source_date"),
                       "flags": [f for f in (a.get("flags") or [])]}
                      for i, a in enumerate(atoms) if (a.get("content") or "").strip()],
        }
        self._save()
        return bid

    def edit_atom(self, bid: str, sid: str, *, content: str | None = None,
                  subject: str | None = None, provenance: str | None = None) -> bool:
        b = self._items.get(bid)
        if b is None:
            return False
        for a in b["atoms"]:
            if a["sid"] == sid:
                if content is not None and content.strip():
                    a["content"] = content.strip()
                if subject is not None:
                    a["subject"] = subject if subject in SUBJECTS else ""
                if provenance is not None and provenance.strip():
                    a["provenance"] = provenance.strip()
                self._save()
                return True
        return False

    def remove_atom(self, bid: str, sid: str) -> bool:
        b = self._items.get(bid)
        if b is None:
            return False
        voor = len(b["atoms"])
        b["atoms"] = [a for a in b["atoms"] if a["sid"] != sid]
        if len(b["atoms"]) == voor:
            return False
        self._save()
        return True

    def merge_atoms(self, bid: str, sids: list[str], kop: str) -> bool:
        """Voeg staging-atomen samen tot één samengestelde kaart (kop + body = de rest),
        vóór ze de bibliotheek in gaan. Bron/provenance/reference van het eerste deel."""
        b = self._items.get(bid)
        if b is None or len(sids) < 2 or not (kop or "").strip():
            return False
        delen = [a for a in b["atoms"] if a["sid"] in sids]
        if len(delen) < 2:
            return False
        regels: list[str] = []
        for d in delen:
            regels.append(f"— {d['content']}")
            if d.get("body"):
                regels.append(d["body"])
        from nooch_village.kennisbank import PROVENANCE_TRUST
        provs = [d["provenance"] for d in delen if d["provenance"] in PROVENANCE_TRUST]
        prov = max(provs, key=lambda p: PROVENANCE_TRUST[p]) if provs else "unknown"
        samengesteld = {"sid": "m" + uuid.uuid4().hex[:4], "content": kop.strip(),
                        "body": "\n".join(regels)[:4000], "subject": delen[0]["subject"],
                        "provenance": prov, "source": delen[0]["source"],
                        "reference": next((d["reference"] for d in delen if d.get("reference")), None),
                        "flags": []}
        rest = [a for a in b["atoms"] if a["sid"] not in sids]
        b["atoms"] = [samengesteld] + rest
        self._save()
        return True

    def discard(self, bid: str) -> bool:
        if bid not in self._items:
            return False
        del self._items[bid]
        self._save()
        return True


def commit_batch(store: StagingStore, bid: str, data_dir: str) -> tuple[int, int] | None:
    """Zet de (nagekeken) staging-atomen append-only in de bibliotheek. Idempotent op
    hash(content+bron): al bestaande kaarten worden overgeslagen. Geeft (nieuw, overgeslagen)
    of None als de batch niet bestaat. De batch wordt na commit opgeruimd."""
    b = store.get(bid)
    if b is None:
        return None
    notes = NotesStore(f"{data_dir}/notes.json")
    nieuw = overgeslagen = 0
    for a in b["atoms"]:
        kaart = atoom_kaart({"content": a["content"], "body": a.get("body"),
                             "subject": a["subject"], "provenance": a["provenance"],
                             "source": a["source"], "reference": a.get("reference"),
                             "source_date": a.get("source_date"),
                             "flags": a.get("flags") or [], "link_hints": []})
        if notes.get(kaart.id) is not None:
            overgeslagen += 1
            continue
        notes.add(kaart)
        nieuw += 1
    store.discard(bid)
    return nieuw, overgeslagen
