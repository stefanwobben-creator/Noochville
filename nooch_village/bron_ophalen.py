"""Een transportfout is ONBEKEND, geen leegte. Het gedeelde ophaal-sjabloon voor externe bronnen.

GEMETEN OP PROD, 1 september 2026. `gdelt_tone/vegan_footwear` stond elf dagen als dode bron in de
inbox. De ruwe fetch bleek gewoon HTTP 200 te geven met 103 datapunten. Wat er misging zat niet bij
GDELT maar bij ons: de skill haalde twee termen op met 6 seconden ertussen, GDELT verbrak de tweede
verbinding (`ConnectionResetError`, geen 429), en de `except` daaromheen las dat als "geen data".

Zo werd de TWEEDE term systematisch uitgehongerd terwijl de eerste leefde — en niets in het systeem
kon het verschil zien tussen "opgehaald, er was niets" en "we kregen het niet opgehaald".

DAT IS DE `no_data ≠ nul`-REGEL, één laag lager: niet in de data maar in het TRANSPORT.

    ok           we hebben het opgehaald, hier is de waarde
    leeg         we hebben het opgehaald, er was niets — dat is een FEIT
    ophaalfout   we hebben het niet kunnen ophalen — dat is GEEN feit, dat is onwetendheid

DIT SJABLOON IS BEDOELD OM TE KOPIËREN. Bluesky (403) en Google Trends (429) hebben dezelfde vorm:
de bron zegt geen "nee" maar hangt op, en fail-closed leest dat als afwezigheid. Wie die twee
oppakt, gebruikt `haal_met_retry` in plaats van er een eigen `except` omheen te schrijven.

De retry is belangrijker dan de spacing. Een vast interval is altijd een gok over gedrag dat je niet
beheerst; een retry met backoff vangt de drift. Verhoog de spacing als beleefdheid, maar leun erop
en je bouwt opnieuw iets dat stilletjes verschuift.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

log = logging.getLogger("village.bron")

#: Wachttijden tussen pogingen. Drie stappen: kort (drift), middel (throttle-venster), lang (storing).
BACKOFF = (30, 60, 120)

#: Fouten die over het TRANSPORT gaan en niet over de inhoud. Op naam, niet op klasse: `requests`
#: en `urllib3` wisselen van klassenhiërarchie, en een importfout hier mag geen ophaalfout worden.
_TRANSPORT = ("ConnectionError", "ConnectionResetError", "ConnectTimeout", "ReadTimeout",
              "Timeout", "ProtocolError", "ChunkedEncodingError", "RemoteDisconnected",
              "MaxRetryError", "SSLError")


@dataclass(frozen=True)
class Uitkomst:
    """Wat een ophaalpoging opleverde. `status` is de vraag die telt, niet `waarde`."""
    status: str                      # "ok" | "leeg" | "ophaalfout"
    waarde: object = None
    reden: str = ""
    pogingen: int = 1

    @property
    def gelukt(self) -> bool:
        return self.status in ("ok", "leeg")


def is_transportfout(exc: BaseException) -> bool:
    """Gaat deze fout over de verbinding of over de inhoud?

    Op NAAM en over de hele oorzaakketen: `requests` verpakt een `ConnectionResetError` in een
    `ConnectionError`, en die weer in wat de adapter ervan maakt. Kijken naar alleen het buitenste
    type leest de helft van de resets als iets anders."""
    gezien = set()
    huidig: BaseException | None = exc
    while huidig is not None and id(huidig) not in gezien:
        gezien.add(id(huidig))
        if type(huidig).__name__ in _TRANSPORT:
            return True
        huidig = huidig.__cause__ or huidig.__context__
    return False


def haal_met_retry(fetch, *, naam: str = "", pogingen=BACKOFF, sleep=None, leeg_test=None) -> Uitkomst:
    """Roep `fetch()` aan, met backoff bij een TRANSPORTfout. Geeft een `Uitkomst`.

    `leeg_test(resultaat) -> bool` zegt of het antwoord leeg is; zonder test is elk antwoord "ok".
    Een inhoudelijke fout (geen JSON, andere structuur) is GEEN transportfout en wordt niet herhaald
    — dat gaat de tweede keer net zo goed mis, en dan is opnieuw proberen alleen maar last voor de
    bron.

    `sleep` is injecteerbaar zodat een test niet echt vier minuten wacht."""
    slaap = sleep if sleep is not None else time.sleep
    wachtrij = list(pogingen)
    poging = 0
    while True:
        poging += 1
        try:
            uit = fetch()
        except Exception as exc:                              # noqa: BLE001 — we classificeren hem
            if not is_transportfout(exc):
                log.warning("bron %s: inhoudelijke fout (%s: %s) — niet opnieuw geprobeerd",
                            naam, type(exc).__name__, exc)
                return Uitkomst("ophaalfout", None, f"{type(exc).__name__}: {exc}"[:200], poging)
            if not wachtrij:
                log.warning("bron %s: OPHAALFOUT na %d poging(en) (%s) — dit is ONBEKEND, geen leegte",
                            naam, poging, type(exc).__name__)
                return Uitkomst("ophaalfout", None, f"{type(exc).__name__}: {exc}"[:200], poging)
            wacht = wachtrij.pop(0)
            log.info("bron %s: transportfout (%s) — poging %d, opnieuw over %ds",
                     naam, type(exc).__name__, poging, wacht)
            slaap(wacht)
            continue
        if leeg_test is not None and leeg_test(uit):
            log.info("bron %s: opgehaald en LEEG — dat is een feit, geen fout", naam)
            return Uitkomst("leeg", uit, "", poging)
        return Uitkomst("ok", uit, "", poging)
