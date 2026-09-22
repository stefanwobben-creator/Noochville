"""Zoeken in het eigen Giphy-kanaal, vanaf de server.

DE SLEUTEL BLIJFT HIER. Giphy's API-sleutel hoort niet in een browser: alles wat de pagina kan
lezen, kan iedereen die de pagina opent lezen. Daarom is dit een module achter een route en geen
`fetch` met een sleutel erin. De cockpit praat met deze module, deze module praat met Giphy.

GESCOPED OP HET MERKKANAAL, TWEE KEER. We vragen scoped (`@Nooch_Earth` in de zoekterm) én we
controleren het antwoord (`user.username`). Alleen vragen is niet genoeg: de zoek-API mag zelf
bepalen wat hij relevant vindt, en één los GIF'je van iemand anders in de stickerkiezer van een
merk is precies wat je niet wil. Fail-closed op de scope dus: staat er geen herkenbare eigenaar
bij, dan valt de treffer af.

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

#: Het merkkanaal. Eén plek; wie dit ergens anders overtypt krijgt vanzelf een tweede waarheid.
GIPHY_USER = "Nooch_Earth"
_ENDPOINT = "https://api.giphy.com/v1/gifs/search"
_TIMEOUT = 4.0        # een stickerkiezer mag geen verzoek 30 seconden vasthouden
_LIMIET = 12          # meer dan dit past niet in het vak onder de vaste rij


def sleutel() -> str:
    """De sleutel uit de omgeving. Leeg = uit; dat is geen fout, dat is een configuratie."""
    return (os.getenv("GIPHY_API_KEY") or "").strip()


def _url(q: str, key: str, limiet: int) -> str:
    # `@gebruiker` in de zoekterm is Giphy's eigen manier om op een kanaal te scopen. Staat de
    # gebruiker er twee keer in (iemand typt zelf "@Nooch_Earth"), dan is dat onschadelijk.
    params = {"api_key": key, "q": f"@{GIPHY_USER} {q}".strip(),
              "limit": str(limiet), "rating": "g", "bundle": "messaging_non_clips"}
    return _ENDPOINT + "?" + urllib.parse.urlencode(params)


def _treffer(rij: dict) -> dict | None:
    """Eén bruikbare treffer, of None. Fail-closed op zowel de eigenaar als het plaatje."""
    if (rij.get("user") or {}).get("username") != GIPHY_USER:
        return None
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
