"""Notificaties — een rol of persoon weet dat er een @-mention voor hem/haar is.

Lichtgewicht store (data/notifications.json). Een notificatie heeft een doel (rol of persoon),
verwijst naar het project + de feed-entry, en draagt een snippet voor de weergave.
"""
from __future__ import annotations
import logging
import os
import time
import uuid

from nooch_village.util import atomic_write_json, read_json

log = logging.getLogger("village.notificaties")


class NotifStore:
    """Notificaties, plus de haak bij het ONTSTAAN.

    Elke nieuwe spanning gaat door `add`: de enige trechter waar ze allemaal doorheen komen. De
    store blijft dom — hij roept alleen een haak aan die de aanroeper zet — zodat hier geen
    model-aanroep in de opslaglaag belandt.

    De haak zit op de INSTANTIE en niet op de module. Een globale versie lekte naar elke test die
    de cockpit opstartte: die zette hem, en daarna deed elke `add` in elke andere test stilletjes
    een model-aanroep. Een haak die verder reikt dan het object dat hem draagt, is geen haak maar
    een verrassing."""

    def __init__(self, path: str, verrijker=None):
        self.path = path
        self._verrijker = verrijker
        self._items: list[dict] = read_json(path, [], expect=list)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, target_type: str, target_id: str, project_id: str, entry_id: str = "",
            by: str = "", snippet: str = "") -> dict:
        n = {
            "id": uuid.uuid4().hex[:10],
            "target_type": target_type, "target_id": target_id,
            "project_id": project_id, "entry_id": entry_id,
            "by": by, "snippet": (snippet or "")[:160],
            "at": time.time(), "read": False,
        }
        self._items.append(n)
        self._save()
        if self._verrijker is not None:
            try:
                extra = self._verrijker(dict(n)) or {}
                if extra:
                    n.update(extra)
                    self._save()
            except Exception as e:                   # noqa: BLE001 — verrijken mag nooit een
                log.warning("verrijken van notificatie %s faalde: %s", n.get("id"), e)
        return n

    def set_verrijker(self, fn) -> None:
        """Zet (of wis) de haak op déze store."""
        self._verrijker = fn

    def for_targets(self, targets) -> list[dict]:
        """Notificaties voor een set (type, id)-doelen, nieuwste eerst."""
        s = {(t, i) for t, i in targets}
        out = [n for n in self._items if (n.get("target_type"), n.get("target_id")) in s]
        return sorted(out, key=lambda n: -(n.get("at") or 0))

    def unread_count(self, targets) -> int:
        return sum(1 for n in self.for_targets(targets) if not n.get("read"))

    def mark_read(self, targets) -> None:
        s = {(t, i) for t, i in targets}
        changed = False
        for n in self._items:
            if (n.get("target_type"), n.get("target_id")) in s and not n.get("read"):
                n["read"] = True; changed = True
        if changed:
            self._save()

    # ── inbox-levenscyclus: nieuw → gelezen → verwerkt (+ archiveren) ─────────────
    @staticmethod
    def status_of(n: dict) -> str:
        """De inbox-status van één notificatie: 'verwerkt' (mens is klaar), 'gelezen' (geopend, nog te
        doen), of 'nieuw' (nog niet bekeken). Afgeleid van de vlaggen, backward-compat met oude items."""
        if n.get("processed"):
            return "verwerkt"
        return "gelezen" if n.get("read") else "nieuw"

    def open_for_targets(self, targets) -> list[dict]:
        """De inbox-wachtrij: NIET-gearchiveerde, NIET-weggegooide notificaties voor deze doelen, nieuwste
        eerst."""
        return [n for n in self.for_targets(targets)
                if not n.get("archived") and not n.get("deleted")]

    def _find(self, notif_id: str) -> dict | None:
        return next((n for n in self._items if n.get("id") == notif_id), None)

    def mark_item_read(self, notif_id: str) -> bool:
        """Nieuw → gelezen (geopend, maar nog te verwerken). Idempotent; verandert 'verwerkt' niet."""
        n = self._find(notif_id)
        if n is None or n.get("read"):
            return False
        n["read"] = True
        self._save()
        return True

    def mark_item_processed(self, notif_id: str, outcome: str = "", by: str = "") -> bool:
        """Markeer als verwerkt (bron afgehandeld). Handmatig door de mens, of autonoom door de rol zelf.
        `outcome` (welke uitkomst) en `by` (wie verwerkte) worden vastgelegd als historie, zodat je later
        kunt terugkijken hoe een signaal is afgehandeld. Beide optioneel (backward-compat)."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["read"] = True
        n["processed"] = True
        if outcome:
            n["outcome"] = str(outcome)[:200]
        if by:
            n["processed_by"] = str(by)[:80]
        self._save()
        return True

    def set_poort(self, notif_id: str, verdict: dict) -> bool:
        """Leg het oordeel van de tensie-poort op het item vast.

        Op het item en niet in een aparte store, om dezelfde reden als `result_ref` bij de Kroniek:
        het oordeel hoort bij het ding waarover het gaat. Zo kan de weergave groeperen zonder de
        poort (en dus een LLM-call) opnieuw te draaien bij elke pageload."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["poort"] = dict(verdict or {})
        self._save()
        return True

    def archive_item(self, notif_id: str) -> bool:
        """Verwerkt item uit de wachtrij halen. Alleen wat verwerkt is mag weg (schone regie)."""
        n = self._find(notif_id)
        if n is None or not n.get("processed"):
            return False
        n["archived"] = True
        self._save()
        return True

    # ── verwerk-record: stapelbare uitkomsten per spanning (mens én AI) ─────────────
    def add_outcome(self, notif_id: str, intent: str = "", otype: str = "", ref: str = "",
                    label: str = "", by: str = "") -> dict | None:
        """Voeg een uitkomst toe aan het verwerk-record van een item ZONDER het te sluiten. Zo kun je
        meerdere uitkomsten op één spanning stapelen (het item blijft open) tot je expliciet 'klaar' bent.
        Elke entry legt intentie, uitkomst-type, een verwijzing, een leesbaar label, wie en wanneer vast:
        het gedrag-record dat je later op een raadsvergadering kunt bespreken (stopt een rol bij de eerste
        uitkomst of haalt hij er meer uit?). Zet het item op 'gelezen'. Onbekend id → None."""
        n = self._find(notif_id)
        if n is None:
            return None
        entry = {"intent": str(intent)[:40], "otype": str(otype)[:40], "ref": str(ref)[:120],
                 "label": str(label)[:200], "by": str(by)[:80], "at": time.time()}
        n.setdefault("verwerkingen", []).append(entry)
        n["read"] = True
        self._save()
        return entry

    def mark_done(self, notif_id: str, by: str = "") -> bool:
        """Sluit een item ('klaar'): het is verwerkt. De gestapelde uitkomsten in `verwerkingen` blijven
        als record staan. Gebruik na add_outcome(s), of direct voor een FYI zonder uitkomst."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["read"] = True
        n["processed"] = True
        if by:
            n["processed_by"] = str(by)[:80]
        self._save()
        return True

    @staticmethod
    def verwerkingen_of(n: dict) -> list[dict]:
        """Het verwerk-record van een item, oudste eerst. Backward-compat: een oud item met alleen een
        enkel `outcome`-veld wordt als één entry getoond."""
        vs = list(n.get("verwerkingen") or [])
        if vs:
            return vs
        if n.get("outcome"):
            return [{"intent": "", "otype": "", "ref": "", "label": n.get("outcome"),
                     "by": n.get("processed_by", ""), "at": n.get("at")}]
        return []

    def delete_item(self, notif_id: str) -> bool:
        """Prullenbak: haal ruis die je niet wilt verwerken uit de wachtrij. Anders dan archiveren mag dit
        ook op een nog-niet-verwerkt item. Zacht (dismissed-vlag), zodat de data niet echt verdwijnt."""
        n = self._find(notif_id)
        if n is None:
            return False
        n["deleted"] = True
        self._save()
        return True

    def all(self) -> list[dict]:
        return list(self._items)
