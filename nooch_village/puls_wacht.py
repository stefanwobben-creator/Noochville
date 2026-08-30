"""De hartslagbewaker die BUITEN het dorp staat.

WAAROM BUITEN. Er was al een puls-watchdog, en hij werkte: `Facilitator._run_pulse_watchdog`
escaleert een rol die op de vorige dag geen hartslag naliet. Maar hij wordt aangeroepen vanuit
`tick()` — de hartslag zelf. Toen de afslanking van 28 aug 2026 de facilitator slapend legde, viel
de tick weg, en daarmee de bewaker. Het dorp stond drie dagen stil en er kwam geen enkel signaal.
Bij het herstel vuurde hij meteen wél: hij was nooit stuk, hij kon alleen niet draaien.

Een bewaker die dezelfde faalmodus deelt als wat hij bewaakt, is geen bewaker.

WAAROP HIJ GRONDT, en waarop nadrukkelijk NIET:

  WEL  `timekeeper_last_day.json` — geschreven door de TimeKeeper zodra de dagbel luidt, en de
       enige plek die zegt "de bel van vandaag is geluid". Een bestand, geen event.
  WEL  logactiviteit van vandaag — draait het proces überhaupt nog?
  NIET `pulse_completed`, `last_pulse.json` of `pulse_history.jsonl`. Die hangen alle drie aan
       `website_watcher`, en die kán slapen — dan meldt de bewaker een storing die er niet is, of
       erger: hij zwijgt omdat het signaal dat hij mist ook zijn eigen bron was. Gemeten op
       30 aug 2026: de bel luidde, 659 regels werk, en `last_pulse` bleef op 27 augustus staan.

FAIL-LOUD, niet fail-soft. Dit is het ene stuk van het dorp dat mag schreeuwen: hij schrijft een
regel in `data/puls_alarm.log`, legt een melding in de founder-inbox, en eindigt met een
non-zero exit-code zodat cron of systemd het óók ziet. Drie kanalen, want als er één stilvalt is dat
precies het geval waarvoor hij bestaat.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime

log = logging.getLogger("village.puls_wacht")

ALARM_LOG = "puls_alarm.log"
UNIT = "noochville-village"


def _tijdzone(settings):
    naam = str((settings or {}).get("dag_begint_tz", "Europe/Madrid")).strip()
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(naam) if naam else None
    except Exception:                                    # noqa: BLE001 — val terug op server-tijd
        return None


def _vuurtijd(settings) -> tuple[int, int]:
    raw = str((settings or {}).get("dag_begint_time", "04:32")).strip()
    try:
        hh, mm = raw.split(":")
        return int(hh), int(mm)
    except Exception:                                    # noqa: BLE001
        return 4, 32


def laatste_bel(data_dir: str) -> str:
    """De datum waarop de dagbel het laatst luidde ('' = nooit / onleesbaar)."""
    try:
        with open(os.path.join(data_dir, "timekeeper_last_day.json"), encoding="utf-8") as f:
            return str(json.load(f).get("last_day") or "")
    except Exception:                                    # noqa: BLE001
        return ""


def log_activiteit_vandaag(unit: str = UNIT) -> bool | None:
    """Heeft de daemon vandaag iets gelogd? None = niet vast te stellen (geen journalctl).

    None is geen 'nee': op een machine zonder journal weten we het niet, en dan hoort de bewaker
    daarover te zwijgen in plaats van een storing te melden die hij niet kan zien."""
    try:
        uit = subprocess.run(["journalctl", "-u", unit, "--since", "today", "--no-pager", "-n", "1"],
                             capture_output=True, text=True, timeout=20)
    except Exception:                                    # noqa: BLE001
        return None
    if uit.returncode != 0:
        return None
    tekst = (uit.stdout or "").strip()
    return bool(tekst) and "No entries" not in tekst


def controleer(data_dir: str, settings=None, *, nu=None, unit: str = UNIT) -> dict:
    """Is de dagpuls van vandaag gebeurd? Geeft {ok, redenen, bel, verwacht, activiteit}.

    `verwacht` is False vóór het vuurmoment: 's ochtends om 03:00 is een ontbrekende bel van vandaag
    geen storing maar de normale toestand. Zonder dat onderscheid gaat de bewaker elke nacht af, en
    een bewaker die vals alarm geeft leert men negeren."""
    tz = _tijdzone(settings)
    nu = nu or (datetime.now(tz) if tz else datetime.now())
    hh, mm = _vuurtijd(settings)
    vandaag = nu.date().isoformat()
    bel = laatste_bel(data_dir)
    verwacht = (nu.hour, nu.minute) >= (hh, mm)
    redenen = []
    if verwacht and bel != vandaag:
        redenen.append(f"de dagbel van {vandaag} is niet geluid — laatste bel: {bel or 'nooit'} "
                       f"(verwacht sinds {hh:02d}:{mm:02d})")
    act = log_activiteit_vandaag(unit)
    if act is False:
        redenen.append(f"de daemon '{unit}' heeft vandaag niets gelogd")
    return {"ok": not redenen, "redenen": redenen, "bel": bel, "vandaag": vandaag,
            "verwacht": verwacht, "activiteit": act}


def alarm(data_dir: str, uitslag: dict) -> None:
    """Drie kanalen, want als er één stilvalt is dat precies het geval waarvoor dit bestaat."""
    boodschap = "🕳️ PULS-ALARM — " + " · ".join(uitslag["redenen"])
    try:                                                 # 1. een plat bestand, altijd schrijfbaar
        with open(os.path.join(data_dir, ALARM_LOG), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}  {boodschap}\n")
    except Exception:                                    # noqa: BLE001
        log.exception("alarm-logregel niet weggeschreven")
    try:                                                 # 2. de inbox van de founder
        from nooch_village.human_inbox import FOUNDER_ROLE_ID
        from nooch_village.notifications import NotifStore
        NotifStore(os.path.join(data_dir, "notifications.json")).add(
            "role", FOUNDER_ROLE_ID, "", by="puls-wacht", snippet=boodschap)
    except Exception:                                    # noqa: BLE001
        log.exception("alarm-melding niet in de inbox gezet")
    print(boodschap)                                     # 3. stdout → cron mailt, systemd logt
