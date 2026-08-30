"""De hartslag van het dorp. INFRASTRUCTUUR, geen rol.

WAAROM DIT EEN EIGEN MODULE IS. Dit stond in `Facilitator` — een rol, en dus iets dat via
governance kan worden gearchiveerd, geamendeerd of slapend gelegd. Op 28 augustus 2026 legde de
afslanking `facilitator` slapend, en daarmee stond het hele dorp drie dagen stil: er was niemand meer
die de bel luidde. Niet één skill faalde, geen enkele fout werd gelogd, en `_should_fire_daily` stond
gewoon op True. Er was alleen geen tick meer.

De les is niet "die rol had niet mogen slapen" maar: **een hartslag hoort niet af te hangen van een
deelnemer.** Een rol is per definitie iets waarover het dorp mag besluiten; een klok is dat niet. Ze
in één klasse zetten maakte een governance-besluit stilzwijgend tot een infrastructuur-besluit — en
dat is precies het soort koppeling dat niemand ziet tot hij breekt.

Daarom draait de cadans nu naast de rollen in plaats van erin:

    Village.start()  →  Dagcyclus.start()   eigen thread, geen record, geen CLASS_MAP
    Village.stop()   →  Dagcyclus.stop()

De facilitator mag hierna gewoon slapen — hij is weer alleen een governance-rol.

DRIE WACHTERS, DRIE AFSTANDEN, en ze vervangen elkaar niet:

  1. `Dagcyclus._run_pulse_watchdog`   ziet dat een RÓL geen hartslag naliet;
  2. `puls_wacht` (systemd-timer)      ziet dat het hele DORP niet pulseerde — buiten het proces,
                                       want een bewaker binnen de hartslag valt met de hartslag stil;
  3. deze module                       maakt de hartslag zelf niet meer opzegbaar.

Wat hier NIET thuishoort: inhoudelijk werk. De klok publiceert en gaat weer slapen; wie erop
reageert bepaalt zelf wat er gebeurt.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from nooch_village.event_bus import Event
from nooch_village.util import atomic_write_json

log = logging.getLogger("village.dagcyclus")

# De afzender van de bel. Was `facilitator` toen de cadans nog in die rol zat; nu een
# infrastructuur-naam, zodat een lezer van het log ziet dat hier geen rol aan het werk is.
BRON = "dagcyclus"


def should_fire_daily(now, last_day, fire_hh: int, fire_mm: int) -> bool:
    """Vuur de dagcyclus zodra de LOKALE tijd het vaste kloktijdstip (fire_hh:fire_mm) heeft bereikt
    en we die kalenderdag nog niet gevuurd hebben. `last_day` = de laatst-gevuurde datum (persistent),
    zodat een restart/deploy niet dubbel vuurt en het volgende moment niet verschuift; miste de server
    04:32 (was down), dan vuurt hij de dag alsnog éénmaal bij de eerste tick erna."""
    if now.date().isoformat() == last_day:
        return False
    return (now.hour, now.minute) >= (fire_hh, fire_mm)


def cadence_events(d) -> list[str]:
    """Pure helper: geeft de event-namen die op datum d gepubliceerd moeten worden.

    Altijd: dag_begint. Bovendien:
      maand_begint    — op dag 1 van elke maand
      kwartaal_begint — op dag 1 van jan/apr/jul/okt
    """
    events = ["dag_begint"]
    if d.day == 1:
        events.append("maand_begint")
        if d.month in (1, 4, 7, 10):
            events.append("kwartaal_begint")
    return events


class Dagcyclus:
    """Luidt de bel: `dag_eindigt` van gisteren, dan `dag_begint` (+ maand/kwartaal) van vandaag.

    Geen `Inhabitant`, geen `Record`, geen `CLASS_MAP`-entry — met opzet. Wat hier draait valt niet
    onder governance, en dat is het hele punt: het dorp mag over zijn structuur besluiten, niet over
    zijn hartslag."""

    #: hoe vaak de thread kijkt of het tijd is. Niet hoe vaak hij vuurt.
    KIJK_INTERVAL = 1.0

    def __init__(self, bus, context):
        self.bus = bus
        self.context = context
        self.log = log
        self._last_beat: float = 0.0
        self._first_ring: bool = True
        self._interval: float = float(context.settings.get("heartbeat_seconds", 0) or 0)
        # Vast kloktijdstip voor dag_begint (config, centraal in settings.ini).
        raw = str(context.settings.get("dag_begint_time", "04:32")).strip()
        try:
            hh, mm = raw.split(":")
            self._fire_hh, self._fire_mm = int(hh), int(mm)
        except Exception:                                    # noqa: BLE001
            self._fire_hh, self._fire_mm = 4, 32
        # Tijdzone EXPLICIET uit config (IANA, via stdlib zoneinfo), los van de server-tz — Nooch zit
        # in Spanje. Ongeldige/ontbrekende zone → None = val terug op server-lokale tijd (fail-soft).
        tz_name = str(context.settings.get("dag_begint_tz", "Europe/Madrid")).strip()
        try:
            self._tz = ZoneInfo(tz_name) if tz_name else None
        except Exception:                                    # noqa: BLE001
            self._tz = None
        # Laatst-gevuurde datum persistent → restart/deploy vuurt niet dubbel en verschuift niet.
        self._last_day: str | None = self._load_last_day()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── persistentie ────────────────────────────────────────────────────────
    def _last_day_path(self) -> str:
        return os.path.join(self.context.data_dir, "timekeeper_last_day.json")

    def _load_last_day(self):
        try:
            with open(self._last_day_path()) as f:
                return json.load(f).get("last_day")
        except Exception:                                    # noqa: BLE001
            return None

    def _save_last_day(self) -> None:
        try:
            atomic_write_json(self._last_day_path(), {"last_day": self._last_day})
        except Exception:                                    # noqa: BLE001
            pass

    # ── de thread ───────────────────────────────────────────────────────────
    def start(self) -> None:
        """Eigen thread, los van elke inwoner. Idempotent."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="dagcyclus", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:                           # noqa: BLE001 — de klok mag nooit stoppen
                self.log.error("dagcyclus-tick faalde: %s", e)
            # Wachten via het stop-event: dan stopt hij meteen bij een shutdown in plaats van eerst
            # zijn slaap uit te dienen.
            self._stop.wait(min(self.KIJK_INTERVAL, self._interval) if self._interval > 0
                            else self.KIJK_INTERVAL)

    # ── de cadans ───────────────────────────────────────────────────────────
    def tick(self) -> None:
        if self._interval > 0:               # demo/test: relatieve hartslag (heartbeat_seconds)
            now = time.time()
            if now - self._last_beat >= self._interval:
                self._last_beat = now
                self._ring("demo-puls", date.today())
            return
        # productie: één keer per kalenderdag op het vaste kloktijdstip in de GECONFIGUREERDE tijdzone
        # (dag_begint_tz), niet de server-tz. should_fire_daily + de persist-datum rekenen hiertegen.
        now_local = datetime.now(self._tz)
        if should_fire_daily(now_local, self._last_day, self._fire_hh, self._fire_mm):
            self._last_day = now_local.date().isoformat()
            self._save_last_day()
            self._run_pulse_watchdog(self._last_day)   # dead man's switch op de vorige dag, vóór de cyclus
            self._ring(self._last_day, now_local.date())

    def _ring(self, label: str, today) -> None:
        if not self._first_ring:
            self.log.info("🌙 dag_eindigt (%s)", label)
            self.bus.publish(Event("dag_eindigt", {"label": label}, BRON))
        self._first_ring = False
        for name in cadence_events(today):
            self.log.info("🔔 %s (%s)", name, label)
            self.bus.publish(Event(name, {"label": label}, BRON))

    def _run_pulse_watchdog(self, today_iso: str) -> None:
        """Dorp-brede watchdog: escaleer zichtbaar als een verwachte dagelijkse rol op de zojuist
        afgesloten vorige dag geen hartslag naliet (mogelijk niet-uitvoering). Verwachte set uit
        config `daily_pulse_roles` (default: harry_hemp). Fail-soft: mag de cadans nooit breken.

        Dit is de BINNENSTE wachter: hij ziet een rol die stilviel. Dat het dorp zelf stilvalt kan
        hij niet zien — daarvoor is `puls_wacht` (systemd), buiten dit proces."""
        try:
            from nooch_village.human_inbox import _notify_founder
            from nooch_village.pulse_watchdog import run_watchdog
            data_dir = self.context.data_dir
            expected = [r.strip() for r in
                        str(self.context.settings.get("daily_pulse_roles", "harry_hemp")).split(",")
                        if r.strip()]
            if not expected:
                return

            def _notify(role, day):
                _notify_founder(
                    os.path.join(data_dir, "human_inbox.json"), by="pulse_watchdog",
                    snippet=(f"⚠️ Puls-uitval: rol '{role}' liet geen hartslag na op {day} — "
                             f"mogelijk niet-uitvoering (hook/service), geen fout gemeld. "
                             f"Beoordeel via python -m nooch_village.inbox"))

            gemist = run_watchdog(data_dir, expected, today_iso, _notify)
            if gemist:
                self.log.warning("🕳️ puls-watchdog: geen hartslag voor %s op de vorige dag → "
                                 "founder geëscaleerd", gemist)
        except Exception as exc:                             # noqa: BLE001
            self.log.warning("puls-watchdog faalde (genegeerd): %s", exc)
