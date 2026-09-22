"""Zoeken in het eigen Giphy-kanaal, vanaf de server.

DE SLEUTEL BLIJFT HIER. Giphy's API-sleutel hoort niet in een browser: alles wat de pagina kan
lezen, kan iedereen die de pagina opent lezen. Daarom is dit een module achter een route en geen
`fetch` met een sleutel erin. De cockpit praat met deze module, deze module praat met Giphy.

PUBLIEK GIPHY, NIET ALLEEN HET MERKKANAAL (founder-besluit, 22 september 2026). Dit zocht
eerst uitsluitend in `@Nooch_Earth` en filterde het antwoord op die eigenaar. Dat kanaal bleek
op productie precies ÉÉN GIF te bevatten, dus het zoekveld vond voor bijna elke term niets —
gemeten bij de deploy: "donut" 0, "shoe" 0, het hele kanaal 1. Een zoekveld dat structureel
niets vindt is geen scope maar een dood veld.

Nu dus gewoon zoeken zoals elke GIF-kiezer. `rating=g` blijft staan: dat is de CONTENTfilter en
staat los van de vraag uit wélk kanaal iets komt. Wat er verder mee te maken had is bewust NIET
meeverdwenen — zie `haal` en `download` hieronder.

FAIL-SOFT OP DE VERBINDING. Geen sleutel, geen netwerk, een trage of stukke Giphy: dan komt er
een lege lijst uit en verder niets. De vaste rij stickers staat los hiervan en blijft werken;
het zoekveld valt stil. Een stickerkiezer die een foutmelding geeft omdat een dienst van derden
hapert, is erger dan een stickerkiezer die even niets vindt.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

log = logging.getLogger("village.giphy")

_ENDPOINT = "https://api.giphy.com/v1/gifs/search"
_TIMEOUT = 4.0        # een stickerkiezer mag geen verzoek 30 seconden vasthouden
_LIMIET = 12          # meer dan dit past niet in het vak onder de vaste rij


def sleutel() -> str:
    """De sleutel uit de omgeving. Leeg = uit; dat is geen fout, dat is een configuratie."""
    return (os.getenv("GIPHY_API_KEY") or "").strip()


def _url(q: str, key: str, limiet: int) -> str:
    # HIER STOND `@Nooch_Earth` VÓÓR DE ZOEKTERM — Giphy's eigen manier om op een kanaal te
    # scopen. Die prefix zat in de VRAAG, niet alleen in de filtering: laat hem staan en je
    # zoekt nog steeds binnen dat ene kanaal, wat de filtering ook doet.
    params = {"api_key": key, "q": (q or "").strip(),
              "limit": str(limiet), "rating": "g", "bundle": "messaging_non_clips"}
    return _ENDPOINT + "?" + urllib.parse.urlencode(params)


def _treffer(rij: dict) -> dict | None:
    """Eén bruikbare treffer, of None. Fail-closed op het PLAATJE — de eigenaarscheck is met de
    merkscope vervallen (een publieke GIF heeft vaak helemaal geen `user`)."""
    beelden = rij.get("images") or {}
    for soort in ("fixed_height_small", "fixed_width_small", "downsized", "original"):
        url = (beelden.get(soort) or {}).get("url")
        if url and url.startswith("https://"):
            return {"id": str(rij.get("id") or ""), "url": url,
                    "naam": str(rij.get("title") or "").strip()[:80]}
    return None


def zoek(q: str, *, limiet: int = _LIMIET, timeout: float = _TIMEOUT) -> list[dict]:
    """De stickers uit het merkkanaal die bij `q` horen. Lege lijst = niets gevonden OF niets
    kunnen vragen; dat onderscheid hoort de gebruiker niet als foutmelding te zien."""
    key = sleutel()
    if not key:
        log.debug("geen GIPHY_API_KEY — zoekveld staat uit")
        return []
    try:
        req = urllib.request.Request(_url(q, key, limiet),
                                     headers={"User-Agent": "NoochVille/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:                                      # noqa: BLE001 — zie de moduletekst
        log.warning("giphy onbereikbaar of onverwacht antwoord", exc_info=True)
        return []
    rijen = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rijen, list):
        return []
    uit = [t for t in (_treffer(r) for r in rijen if isinstance(r, dict)) if t]
    return uit[:limiet]


_GIF_ENDPOINT = "https://api.giphy.com/v1/gifs/"
_MAX_BYTES = 8 * 1024 * 1024      # ruim boven een sticker, ruim onder "iemand stuurt ons een film"


def haal(gif_id: str, *, timeout: float = _TIMEOUT) -> dict | None:
    """De treffer met dit id, opnieuw opgehaald bij Giphy zelf.

    DIT PAD BLIJFT, OOK NU DE MERKSCOPE WEG IS. Het bestond niet om het kanaal te bewaken maar
    om te voorkomen dat de CLIENT bepaalt welk adres deze server ophaalt: neem je de URL uit de
    browser over, dan is elk intern adres en elk bestand achter de firewall bereikbaar. Daarom
    reist alleen een ID mee en zoekt de server het adres er zelf bij.

    Wat hier wél verviel is de tweede eigenaarscontrole — die hoorde bij de scope, niet bij deze
    verdediging."""
    key = sleutel()
    gid = "".join(c for c in str(gif_id or "") if c.isalnum())     # Giphy-id's zijn alfanumeriek
    if not (key and gid):
        return None
    url = _GIF_ENDPOINT + gid + "?" + urllib.parse.urlencode({"api_key": key})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NoochVille/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:                                      # noqa: BLE001
        log.warning("giphy-id %s niet op te halen", gid, exc_info=True)
        return None
    rij = data.get("data") if isinstance(data, dict) else None
    return _treffer(rij) if isinstance(rij, dict) else None


def download(url: str, *, timeout: float = _TIMEOUT, cap: int = _MAX_BYTES) -> bytes | None:
    """De bytes achter een Giphy-URL. None bij twijfel.

    FAIL-CLOSED OP DE HOST. Alleen `*.giphy.com` over https, ook al komt deze URL uit `haal()` en
    niet uit de browser: een adres dat de server gaat ophalen hoort altijd tegen een lijst te
    liggen, niet tegen de herkomst van de string. Plus een harde bovengrens op wat we lezen —
    `Content-Length` vertrouwen we niet, we tellen zelf."""
    ontleed = urllib.parse.urlsplit(str(url or ""))
    gastheer = ontleed.hostname or ""
    if ontleed.scheme != "https" or not (gastheer == "giphy.com"
                                         or gastheer.endswith(".giphy.com")):
        log.warning("giphy-download geweigerd: %s", gastheer)
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NoochVille/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(cap + 1)
    except Exception:                                      # noqa: BLE001
        log.warning("giphy-download mislukt", exc_info=True)
        return None
    if not data or len(data) > cap or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None                                        # te groot, leeg, of geen GIF
    return data
