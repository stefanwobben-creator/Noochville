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

EN SINDS 30 SEPTEMBER 2026 KIJKT HIJ OOK NAAR DE WEKELIJKSE UITGANGEN. Dat gat stond hierboven al
beschreven zonder dat iemand de consequentie trok: deze bewaker keek of de dagelijkse TIK afging,
niet naar wat er ÍN die tik gebeurde. Een gezonde tik met een stilzwijgend overgeslagen weekmemo
ziet er voor hem identiek uit aan een gezonde week.

Gemeten: Stefan had nog nooit een weekmemo gezien — nul berichten in zijn DM-kanaal, ooit. Niet
gemist maar nooit verstuurd, want `weekmemo.ronde` stuurt bewust niets bij een week zonder nieuwe
signalen (dat is geen bug: een memo die "niets gevonden" meldt leer je wegklikken). Het gevolg is
wél een bug: zonder bericht en zonder bewaker is "het draait" niet te onderscheiden van "het is
stil".

WAT DIT DUS NIET DOET: elke lege week een "niets te melden" sturen. Dat is precies de ruis die de
send-gate vermijdt. Het alarm gaat pas af als een uitgang LANGER DAN `STILTE_DAGEN` niets heeft
vastgelegd — ongeacht of die vastlegging "verstuurd" of "geen signalen deze week" was.

PER UITGANG APART. Twee wekelijkse features met dezelfde afleverroute: uit het alarm moet blijken
WELKE stil is, anders begint het zoeken pas bij de melding.
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

#: Hoe lang een WEKELIJKSE uitgang mag zwijgen voordat het stilte heet. Ruimer dan de cyclus zelf:
#: een week die een dag uitloopt (de daemon start later, een periode die op zondag omslaat) is geen
#: storing, en een bewaker die daarop afgaat leert men negeren. Tien dagen dekt één gemiste week
#: zonder een normale te raken.
STILTE_DAGEN = 10


def _weekuitgangen() -> list[tuple[str, str]]:
    """De wekelijkse uitgangen die niets van zich laten horen als er niets te melden is, met het
    bestand waarin ze hun ronde vastleggen.

    DE BESTANDSNAAM KOMT UIT DE MODULE ZELF. Zou hij hier als letterlijke string staan, dan bewaakt
    deze bewaker na één hernoeming een bestand dat niet meer bestaat — en dat merk je pas als de
    stilte die hij moest vangen er al is."""
    from nooch_village import noochie_memo, weekmemo
    return [("weekmemo", weekmemo.STATE), ("noochie-memo", noochie_memo.STATE)]


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


def laatste_ronde(data_dir: str, bestand: str) -> float:
    """Wanneer deze wekelijkse uitgang zijn laatste ronde VASTLEGDE (0.0 = nooit).

    OP DE VASTLEGGING, NIET OP DE BEZORGING. Een week zonder nieuwe signalen levert geen bericht op
    en is toch een geslaagde ronde; die telt hier dus mee. Wat NIET meetelt is een ronde die
    halverwege strandde — `weekmemo.ronde` markeert bewust niet als de bezorging nergens aankwam,
    en dan is stilte precies het juiste woord."""
    try:
        with open(os.path.join(data_dir or ".", bestand), encoding="utf-8") as f:
            return float(json.load(f).get("laatste_at") or 0.0)
    except Exception:                                    # noqa: BLE001 — geen bestand = nooit
        return 0.0


def stiltes(data_dir: str, *, nu: float | None = None, dagen: int = STILTE_DAGEN) -> list[str]:
    """Eén regel per wekelijkse uitgang die te lang niets heeft vastgelegd. Leeg = alles loopt.

    NOOIT GEDRAAID IS OOK STILTE, en dat is geen strenge lezing maar het geval dat deze check
    veroorzaakte: de weekmemo stond twee weken gewired zonder ooit iets vast te leggen, en niets in
    het dorp zei dat. Een uitgang die nog nooit een ronde afmaakte, hoort precies zo luid te zijn
    als een uitgang die gestopt is."""
    import time

    nu = time.time() if nu is None else nu
    grens = float(dagen) * 86400
    uit = []
    for naam, bestand in _weekuitgangen():
        at = laatste_ronde(data_dir, bestand)
        if at <= 0:
            uit.append(f"{naam}: nog nooit een ronde vastgelegd ({bestand} ontbreekt of is leeg)")
        elif nu - at > grens:
            oud = int((nu - at) // 86400)
            wanneer = datetime.fromtimestamp(at).strftime("%d-%m-%Y")
            uit.append(f"{naam}: {oud} dagen stil — laatste ronde {wanneer} "
                       f"(drempel {dagen} dagen)")
    return uit


def _unit_bestaat(unit: str) -> bool | None:
    """Kent systemd deze unit? None = geen systemd om het aan te vragen.

    Nodig omdat `journalctl -u <onbekend>` exact hetzelfde antwoordt als een unit die vandaag
    toevallig stil was: '-- No entries --'. Zonder deze check leest een tikfout in de unit-naam als
    'de daemon ligt stil', en dan huilt de bewaker elke ochtend wolf om zijn eigen configuratie.
    De CI ving dat: daar bestaat journalctl wél en de test-unit niet."""
    try:
        uit = subprocess.run(["systemctl", "show", unit, "--property=LoadState", "--value"],
                             capture_output=True, text=True, timeout=20)
    except Exception:                                    # noqa: BLE001 — geen systemd
        return None
    if uit.returncode != 0:
        return None
    return (uit.stdout or "").strip() == "loaded"


def log_activiteit_vandaag(unit: str = UNIT) -> bool | None:
    """Heeft de daemon vandaag iets gelogd? None = niet vast te stellen.

    None is geen 'nee', en dat geldt op drie manieren: geen journalctl, geen systemd, of een unit
    die systemd niet kent. In al die gevallen weten we het niet, en dan hoort de bewaker te zwijgen
    in plaats van een storing te melden die hij niet kan zien."""
    if _unit_bestaat(unit) is not True:
        return None
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


def controleer_week(data_dir: str, *, nu: float | None = None,
                    dagen: int = STILTE_DAGEN) -> dict:
    """Hebben de WEKELIJKSE uitgangen zich laten horen? Geeft {ok, redenen}.

    EEN EIGEN UITSLAG, NAAST `controleer` EN NIET ERIN. Ze meten verschillende dingen op
    verschillende klokken: die daar vraagt "is de bel van VANDAAG geluid", deze "heeft deze uitgang
    de afgelopen tien dagen íets vastgelegd". In één uitslag proppen zou betekenen dat een stille
    weekmemo elke ochtend als puls-alarm langskomt, met een tekst die over de dagbel gaat — en dan
    staat er een storing op het scherm die niet is wat hij zegt te zijn.

    Dezelfde vorm als `controleer` (dict met `ok` en `redenen`), zodat `alarm` allebei kan
    versturen zonder te weten welk soort het is."""
    redenen = stiltes(data_dir, nu=nu, dagen=dagen)
    return {"ok": not redenen, "redenen": redenen}


def alarm(data_dir: str, uitslag: dict, kop: str = "🕳️ PULS-ALARM") -> None:
    """Drie kanalen, want als er één stilvalt is dat precies het geval waarvoor dit bestaat.

    `kop` maakt het verschil tussen "de dagbel is niet geluid" en "een wekelijkse uitgang is stil"
    zichtbaar in de eerste drie woorden. De drie kanalen blijven dezelfde: het platte logbestand,
    een bericht bij de founder, en stdout voor cron/systemd."""
    boodschap = f"{kop} — " + " · ".join(uitslag["redenen"])
    try:                                                 # 1. een plat bestand, altijd schrijfbaar
        with open(os.path.join(data_dir, ALARM_LOG), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}  {boodschap}\n")
    except Exception:                                    # noqa: BLE001
        log.exception("alarm-logregel niet weggeschreven")
    # 2. een bericht bij de founder. `stuur_op_pad` logt zelf als het misgaat en gooit niets —
    # een alarm dat de alarmering omver haalt is erger dan een alarm dat niet aankomt.
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    from nooch_village import signaal
    signaal.stuur_op_pad(data_dir, "role", FOUNDER_ROLE_ID, boodschap, by="puls-wacht")
    print(boodschap)                                     # 3. stdout → cron mailt, systemd logt
