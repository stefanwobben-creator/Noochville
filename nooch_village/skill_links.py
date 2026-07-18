"""Skill-links: het dorpsmiddel dat aan een belofte hangt.

De koppeling zelf leeft in `AITaskStore` (`data/ai_tasks.json`, `kind="middel"`) — één store,
één beheer-UI voor middel én autonomie. Dit module levert wat daaromheen hangt:

- `effectief(rec, ai)` — de afgeleide skillset van een rol: rol-DNA ∪ gekoppelde middelen.
  Tijdens de migratie is het rol-DNA de vloer (niets breekt), de links zijn de plus.
- `SkillLinkKroniek` — append-only logboek van elke leg/verwijder-actie.

De twee snelheden blijven gescheiden: een koppeling raakt NOOIT de tekst van een
accountability. Zodra dat nodig lijkt, is het een governance-voorstel.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from nooch_village.ai_tasks import KIND_MIDDEL
from nooch_village.util import file_lock

log = logging.getLogger("village.skill_links")


# ── De afgeleide skillset ────────────────────────────────────────────────────

def links_for_role(ai, role_id: str) -> list:
    """De middel-koppelingen van deze rol (leeg bij een ontbrekende store)."""
    if ai is None or not role_id:
        return []
    try:
        return [t for t in ai.for_role(role_id) if t.kind == KIND_MIDDEL]
    except Exception as exc:                       # een kapotte store mag niets platleggen
        log.warning("skill_links: kon koppelingen van '%s' niet lezen: %s", role_id, exc)
        return []


def links_for_acc(ai, role_id: str, acc_id: str) -> list:
    """De middel-koppelingen op één belofte."""
    if ai is None or not role_id or not acc_id:
        return []
    try:
        return [t for t in ai.for_acc(role_id, acc_id) if t.kind == KIND_MIDDEL]
    except Exception as exc:
        log.warning("skill_links: kon koppelingen van '%s' niet lezen: %s", role_id, exc)
        return []


def linked_skills(ai, role_id: str) -> set[str]:
    """Alleen de capability-ids van de gekoppelde middelen."""
    return {t.skill for t in links_for_role(ai, role_id) if t.skill}


def effectief(rec, ai) -> set[str]:
    """De effectieve skillset van een rol: DNA-grants ∪ gekoppelde middelen.

    `rec` is een Record (of None). Fail-soft: zonder record of store krijg je wat er wél is.
    """
    dna: set[str] = set()
    if rec is not None:
        defn = getattr(rec, "definition", None)
        dna = set(getattr(defn, "skills", None) or [])
    return dna | linked_skills(ai, getattr(rec, "id", "") or "")


# ── De Kroniek ───────────────────────────────────────────────────────────────

class SkillLinkKroniek:
    """Append-only logboek van koppelingen. Eén regel per leg- of verwijder-actie.

    Een koppeling is operationeel en per direct omkeerbaar — juist daarom moet terug te lezen
    zijn wie welk middel wanneer aan welke belofte hing.
    """

    ACTIONS = ("gelegd", "verwijderd")

    def __init__(self, path: str):
        self.path = path

    def record(self, *, action: str, role_id: str, acc_id: str, skill: str,
               door: str = "", reden: str = "", ts: float | None = None) -> dict:
        if action not in self.ACTIONS:
            raise ValueError(f"ongeldige action {action!r} — verwacht een van {self.ACTIONS}")
        row = {
            "id": uuid.uuid4().hex[:12],
            "action": action,
            "role_id": role_id,
            "acc_id": acc_id,
            "skill": skill,
            "door": door or "",
            "reden": reden or "",
            "ts": ts if ts is not None else time.time(),
        }
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        with file_lock(self.path):                 # veilige append naast de daemon
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        return row

    # ── lezen (lock-vrij) ──
    def all_records(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out

    def for_role(self, role_id: str) -> list[dict]:
        return [r for r in self.all_records() if r.get("role_id") == role_id]
