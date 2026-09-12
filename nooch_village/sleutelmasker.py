"""Sleutels uit tekst halen vóór die tekst ergens landt waar een mens of een log hem leest.

GEMETEN AANLEIDING (skill-review, 12 september 2026). `requests.raise_for_status()` zet de volledige
URL in de foutmelding, en bij SerpAPI, YouTube en Alpha Vantage staat de sleutel in die URL
(`api_key=…`, `key=…`, `apikey=…`). Zes skills schreven `str(exc)` door naar de wall, de
deliverable-store of system_log.jsonl. Een sleutel die één keer op de wall staat, staat in de
projectfeed, in het einddocument en in elke back-up.

Twee lagen, allebei nodig:
1. Bij de BRON (web_read, de fetchers): de melding wordt gebouwd zonder URL. Dat is de echte fix.
2. Bij de UITGANG (`Inhabitant._execute_checklist`, `_execute_skill`): elke foutreden gaat door
   `masker()` vóór hij naar wall of log gaat. Verdediging in de diepte: een nieuwe skill die
   morgen `str(exc)` doorgeeft, lekt dan nog steeds niets.

`masker` kent twee soorten sleutels: de VORM (een query- of formulierparameter die 'key', 'token'
of 'secret' heet, en Bearer-headers) en de WAARDE (alles wat in het proces als KEY/TOKEN/SECRET/
PASSWORD in de omgeving staat). De tweede laag vangt ook een sleutel die zonder parameternaam in een
melding is beland, bijvoorbeeld in een response-body die de API terugkaatst.
"""
from __future__ import annotations

import os
import re

_PARAM = re.compile(
    r"(?i)\b((?:api[_-]?|access[_-]?|subscription[_-]?|client[_-]?)?(?:key|token|secret|password|pwd))"
    r"(\s*[=:]\s*)([^&\s\"'#,;)]{8,})")   # ≥8: 'key: youtube' in een note is geen sleutel
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-._~+/]+=*")
_ENV_NAAM = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|PASSWD)$")
_MIN_WAARDE = 8                 # kortere env-waarden zijn geen sleutel (poorten, vlaggen, 'true')
MASKER = "***"


def _geheime_waarden(extra=()) -> list[str]:
    """De echte sleutelwaarden uit de omgeving (+ `extra`), langste eerst zodat een sleutel die een
    andere bevat niet half gemaskeerd achterblijft."""
    waarden = {str(v) for v in (extra or ()) if v and len(str(v)) >= _MIN_WAARDE}
    for naam, waarde in os.environ.items():
        if _ENV_NAAM.search(naam) and waarde and len(waarde) >= _MIN_WAARDE:
            waarden.add(waarde)
    return sorted(waarden, key=len, reverse=True)


def masker(tekst, *, extra=()) -> str:
    """Geef `tekst` terug met elke sleutel vervangen door `***`. Niet-strings worden eerst `str()`.

    Idempotent en goedkoop genoeg voor foutpaden; niet bedoeld voor elke logregel van het dorp."""
    s = tekst if isinstance(tekst, str) else str(tekst)
    if not s:
        return s
    s = _PARAM.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASKER}", s)
    s = _BEARER.sub(lambda m: f"{m.group(1)}{MASKER}", s)
    for waarde in _geheime_waarden(extra):
        if waarde in s:
            s = s.replace(waarde, MASKER)
    return s


def http_fout(resp, bron: str) -> str:
    """Eén regel over een mislukte HTTP-aanroep ZONDER de URL: status, reden en het begin van de
    body (die zegt bij de meeste API's wat er mis is; de URL zegt alleen wat wij vroegen, mét
    sleutel). Voor gebruik in plaats van `raise_for_status()`."""
    try:
        body = " ".join((resp.text or "").split())[:200]
    except Exception:
        body = ""
    reden = getattr(resp, "reason", "") or ""
    melding = f"{bron} gaf HTTP {getattr(resp, 'status_code', '?')}"
    if reden:
        melding += f" {reden}"
    if body:
        melding += f" — {body}"
    return masker(melding)
