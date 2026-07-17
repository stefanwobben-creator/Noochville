"""Puls-hartslag + watchdog — een dead man's switch op NIET-uitvoering.

De skill-escalatie vuurt als een rol DRAAIT en struikelt (bijv. pytrends 429). Ze vuurt
NIET als de puls nooit afgaat: hook niet gewired, service plat om 04:32, `dag_begint`
bereikte de rol niet. Dat is stille niet-uitvoering — precies de "alles op 0%"-faalmodus.

Twee delen, generiek op de puls-laag (niet per skill):
  1. HARTSLAG — elke rol die op `dag_begint` reageert laat via de react-laag automatisch een
     marker na (data/pulse_heartbeat.json: per rol de laatste dag + tijd). Append-only van geest.
  2. WATCHDOG — aan het begin van elke dag-cyclus (TimeKeeper, vóór de rollen reageren) checkt
     `run_watchdog` de zojuist AFGESLOTEN vorige dag: heeft elke rol uit de verwachte-set een
     hartslag voor die dag? Zo niet → zichtbare escalatie naar de founder (heads-up, geen
     approve-knop). Idempotent per rol×dag; bootstrap-vloer (`since_day`) voorkomt vals alarm
     voor een dag die vóór de watchdog bestond.
"""
from __future__ import annotations

import datetime

from nooch_village.util import JsonStore


class HeartbeatStore(JsonStore):
    """Per rol de laatste dag_begint-hartslag: {role_id: {"day": "YYYY-MM-DD", "ran_at": iso}}.
    Lock-safe (meerdere inwoner-threads schrijven concurrent); idempotent per (rol, dag)."""

    _WRITE_METHODS = ("beat",)

    def beat(self, role_id: str, day: str, ran_at: str) -> None:
        cur = self._items.get(role_id)
        if cur and cur.get("day") == day:
            return                                        # zelfde dag al gemarkeerd → niets doen
        self._items[role_id] = {"day": day, "ran_at": ran_at}
        self._save()

    def day_of(self, role_id: str) -> str | None:
        return (self._items.get(role_id) or {}).get("day")


class WatchdogState(JsonStore):
    """Watchdog-geheugen: de bootstrap-vloer (`since_day`, eerste watchdog-dag) en de al-
    geëscaleerde rol×dag-sleutels (idempotentie, geen spam). Append-only van geest."""

    _WRITE_METHODS = ("ensure_since", "mark_escalated")

    def since(self) -> str | None:
        return self._items.get("since_day")

    def ensure_since(self, day: str) -> None:
        if not self._items.get("since_day"):
            self._items["since_day"] = day
            self._save()

    def already_escalated(self, role: str, day: str) -> bool:
        return f"{role}|{day}" in (self._items.get("escalated") or [])

    def mark_escalated(self, role: str, day: str) -> None:
        self._items.setdefault("escalated", []).append(f"{role}|{day}")
        self._save()


def _yesterday(day_iso: str) -> str:
    return (datetime.date.fromisoformat(day_iso) - datetime.timedelta(days=1)).isoformat()


def run_watchdog(data_dir: str, expected_roles, today_iso: str, notify) -> list[str]:
    """Check de zojuist afgesloten vorige dag. `today_iso` = de dag die NU begint (die puls draait
    juist; die kun je niet mid-flight bevestigen — daarom de vorige, complete dag). Voor elke rol
    in `expected_roles` zonder hartslag voor gisteren → `notify(role, gisteren)` (één keer).
    Geeft de gemiste rollen terug. Bootstrap: gisteren < since_day → niets (geen vals alarm)."""
    hb = HeartbeatStore(f"{data_dir}/pulse_heartbeat.json")
    wd = WatchdogState(f"{data_dir}/pulse_watchdog.json")
    wd.ensure_since(today_iso)                            # eerste watchdog-dag = de vloer
    since = wd.since()
    gisteren = _yesterday(today_iso)
    if gisteren < (since or gisteren):
        return []                                        # dag vóór de watchdog bestond → overslaan
    gemist: list[str] = []
    for role in expected_roles:
        role = (role or "").strip()
        if not role:
            continue
        if hb.day_of(role) == gisteren:
            continue                                     # pulsde gisteren → ok
        if wd.already_escalated(role, gisteren):
            continue                                     # al gemeld → idempotent
        wd.mark_escalated(role, gisteren)
        try:
            notify(role, gisteren)
        except Exception:
            pass
        gemist.append(role)
    return gemist
