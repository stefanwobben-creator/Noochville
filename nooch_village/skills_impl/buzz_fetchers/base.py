"""Gedeelde basis voor de community_listening-fetchers.

Een fetcher haalt van één platform gegronde kandidaat-rijen op. Hij bezit z'n eigen HTTP,
rate-limit, backoff, 6u-cache-check en refuse-codes; hij SLAAT NIETS OP (de skill doet centraal
de dedup/store/telling). Elke stille early-return krijgt een BUZZ_*-code (fail-loud).

`fetch()` geeft terug:
  {"rows": [...], "refuse": <code>|None, "requests": int, "note": str}
`refuse` is alleen gezet bij een PLATFORM-brede stop (BUZZ_NO_KEY, BUZZ_QUOTA, BUZZ_RATE_LIMITED);
granulaire fouten (één query/video) worden per stuk via util.refuse() gelogd en overgeslagen.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

# Nette User-Agent, gedeeld over de fetchers (identificeert het dorp).
UA = "NoochVille/1.0 (community research; contact: stefan@nooch.earth)"
CACHE_TTL = 6 * 3600          # 6u response-cache per fetch-eenheid
RATE_DELAY = 1.0              # max 1 request per seconde
MAX_RETRIES = 3              # exponential backoff op 429
FRAGMENT_MAX = 280


class RateLimited(Exception):
    """Het platform gaf herhaald 429 terug; de backoff is uitgeput."""


class BuzzFetcher(ABC):
    """Eén platform-fetcher. Registreer in buzz_fetchers.FETCHERS via `platform`."""

    platform: str = "abstract"

    @abstractmethod
    def fetch(self, set_id: str, cfg: dict, context, cache, opts: dict) -> dict:
        """Haal kandidaat-rijen op voor deze set + platform. Zie module-docstring voor het
        retour-contract. `cfg` = de platform-config uit de set; `opts` draagt o.a. `now` (ts)
        en `time_window`."""
        ...
