"""Werkoverleg (tactical meeting) — de operationele bijeenkomst van een cirkel.

Vaste volgorde: check-in, checklist, metrics, projecten, agenda (spanningen), check-out, sluiten.
Alleen de secretaris opent en sluit. De inhoud per stap hergebruikt de BESTAANDE schermen
(members, checklists, metrics, projecten); er is geen tweede versie.

Deze store houdt alleen de overleg-staat bij (status, tijd, aanwezigheid, agenda, check-out,
samenvatting). De rest leeft in de bestaande stores. Opslag: data/werkoverleg.json.
"""
from __future__ import annotations
import json
import os
import time

from nooch_village.util import atomic_write_json

STEPS = [("checkin", "Check-in"), ("checklist", "Checklist"), ("metrics", "Metrics"),
         ("projecten", "Projecten"), ("agenda", "Agenda"), ("checkout", "Check-out"),
         ("sluiten", "Sluiten")]


class WerkoverlegStore:
    def __init__(self, path: str):
        self.path = path
        self._m: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                d = json.load(open(path))
                if isinstance(d, dict):
                    self._m = d
            except Exception:
                self._m = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._m)

    def get(self, circle: str) -> dict | None:
        return self._m.get(circle)

    def is_open(self, circle: str) -> bool:
        return (self._m.get(circle) or {}).get("status") == "open"

    def open(self, circle: str) -> dict:
        """Start een overleg (idempotent zolang het open is)."""
        st = self._m.get(circle)
        if not st or st.get("status") != "open":
            st = {"status": "open", "started_at": time.time(), "ended_at": None,
                  "presence": {}, "agenda": [], "checkout": {}}
            self._m[circle] = st
            self._save()
        return st

    def close(self, circle: str) -> dict | None:
        st = self._m.get(circle)
        if not st or st.get("status") != "open":
            return None
        st["status"] = "closed"
        st["ended_at"] = time.time()
        self._save()
        return st

    def duration_min(self, circle: str) -> int:
        st = self._m.get(circle) or {}
        start, end = st.get("started_at"), st.get("ended_at") or time.time()
        return int((end - start) / 60) if start else 0

    # ── stap 1: aanwezigheid (✗ = op verlof; taken pauzeren) ───────────────────
    def set_presence(self, circle: str, pid: str, present: bool) -> None:
        st = self._m.get(circle)
        if st is None:
            return
        st.setdefault("presence", {})[pid] = bool(present)
        self._save()

    def presence(self, circle: str) -> dict:
        return (self._m.get(circle) or {}).get("presence", {})

    def is_present(self, circle: str, pid: str) -> bool:
        # default aanwezig totdat iemand op ✗ klikt
        return self.presence(circle).get(pid, True)

    # ── stap 5: agenda (spanningen + triage-uitkomst) ──────────────────────────
    def agenda(self, circle: str) -> list:
        return (self._m.get(circle) or {}).get("agenda", [])

    def agenda_get(self, circle: str, iid: str) -> dict | None:
        return next((i for i in self.agenda(circle) if i["id"] == iid), None)

    def agenda_add(self, circle: str, title: str, by: str = "") -> dict | None:
        st = self._m.get(circle)
        if st is None or not (title or "").strip():
            return None
        import uuid
        it = {"id": uuid.uuid4().hex[:10], "title": title.strip()[:140], "by": by or "",
              "status": "open", "note": {"spanning": "", "role": "", "need": ""},
              "outcome": None, "created_at": time.time()}
        st.setdefault("agenda", []).append(it)
        self._save()
        return it

    def agenda_remove(self, circle: str, iid: str) -> None:
        st = self._m.get(circle)
        if st is None:
            return
        st["agenda"] = [i for i in self.agenda(circle) if i["id"] != iid]
        self._save()

    def agenda_set_note(self, circle: str, iid: str, **fields) -> None:
        it = self.agenda_get(circle, iid)
        if it is None:
            return
        it.setdefault("note", {}).update({k: v for k, v in fields.items() if v is not None})
        self._save()

    def agenda_resolve(self, circle: str, iid: str, otype: str, detail: str = "") -> None:
        """Sluit een spanning af met een uitkomst: info / project / roloverleg / nevermind."""
        it = self.agenda_get(circle, iid)
        if it is None:
            return
        it["outcome"] = {"type": otype, "detail": (detail or "").strip()}
        it["status"] = "done"
        self._save()

    # ── stap 6: check-out (tevredenheid 0-10) ──────────────────────────────────
    def set_checkout(self, circle: str, pid: str, score) -> None:
        st = self._m.get(circle)
        if st is None:
            return
        try:
            s = max(0, min(10, int(score)))
        except (TypeError, ValueError):
            return
        st.setdefault("checkout", {})[pid] = s
        self._save()

    def checkout(self, circle: str) -> dict:
        return (self._m.get(circle) or {}).get("checkout", {})

    # ── stap 7: samenvatting ───────────────────────────────────────────────────
    def summary(self, circle: str) -> dict:
        st = self._m.get(circle) or {}
        ag = st.get("agenda", [])
        done = [i for i in ag if i.get("status") == "done"]
        out = [i.get("outcome", {}).get("type") for i in done]
        scores = list(st.get("checkout", {}).values())
        pres = st.get("presence", {})
        return {
            "behandeld": len(done),
            "info": out.count("info"),
            "projecten": out.count("project"),
            "roloverleg": out.count("roloverleg"),
            "nevermind": out.count("nevermind"),
            "afwezig": [p for p, v in pres.items() if v is False],
            "tevredenheid": round(sum(scores) / len(scores), 1) if scores else None,
            "duur_min": self.duration_min(circle),
        }
