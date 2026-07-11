"""community_listening — grounded ophaal-skill die Reddit-ervaringen over een onderwerp
verzamelt als gestructureerde observaties.

Geen oordeel, geen sentiment, geen insights: zelfde patroon als news en de concurrentiemonitor.
De skill leest publieke Reddit-JSON, ontdubbelt op permalink en schrijft observatie-rijen weg.
Het dorp voeden (samenvatting, spanning) doet Billy Buzz (de ConcurrentScout-rol), niet deze skill.

Bron v1 is ALLEEN Reddit, maar elke rij draagt `platform="reddit"` zodat v2 (andere bronnen)
geen migratie vergt. Fail-closed: elke stille early-return krijgt een BUZZ_*-refuse-code
(les van de OFFER_*-fix) — niets faalt zonder logregel.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse

from nooch_village.skills import Skill
from nooch_village.util import refuse

log = logging.getLogger("village.skill.buzz")

# Verplichte nette User-Agent (briefing) — identificeert het dorp bij Reddit.
_UA = "NoochVille/1.0 (community research; contact: stefan@nooch.earth)"
_SEARCH = "https://www.reddit.com/r/{sub}/search.json"
_CACHE_TTL = 6 * 3600          # response-cache per (sub, query): 6 uur
_RATE_DELAY = 1.0              # max 1 request per seconde
_MAX_RETRIES = 3              # exponential backoff op 429, daarna BUZZ_RATE_LIMITED
_FRAGMENT_MAX = 280

# time_window → Reddit's `t`-param (het venster van de zoekopdracht).
_WINDOW_T = {"1d": "day", "7d": "week", "30d": "month", "90d": "month",
             "365d": "year", "1y": "year", "all": "all"}


class _RateLimited(Exception):
    """Reddit gaf herhaald 429 terug; de backoff is uitgeput."""


def _refuse(code: str, reason: str, **ctx) -> dict:
    """Log de weigering (stabiele code, zoals overal) én geef een fail-dict terug, zodat
    élk early-return-pad zowel een logregel als een leesbare uitkomst heeft."""
    refuse(code, reason, **ctx)
    return {"ok": False, "refuse": code, "error": reason, **ctx}


class CommunityListeningSkill(Skill):
    name = "community_listening"
    cost = "rate_limited"          # onofficieel publiek JSON-endpoint, beleefde 1 req/s + backoff
    side_effect_free = False       # schrijft observatie-rijen
    required_env = ()              # keyless (publieke Reddit-JSON)
    description = ("Verzamelt Reddit-ervaringen over een onderwerp als gestructureerde observaties "
                  "(grounded, geen oordeel/sentiment/insight). Fail-closed, 6u-cache, 1 req/s.")
    input_schema = ("query_set_id: str (verplicht — verwijst naar een set in buzz_query_sets.json). "
                    "optioneel: time_window: str (default '7d')")
    required_payload = ("query_set_id",)
    output_schema = ("ok: bool, count/new: int (nieuwe rijen), cached: int (overgeslagen door 6u-cache), "
                     "fetched: int, query_set_id: str | refuse-dict met code BUZZ_*")

    # ── injectie-punten (met fallback op data_dir, zoals competitor_news) ─────────
    def _query_sets(self, context):
        qs = getattr(context, "buzz_query_sets", None)
        if qs is not None:
            return qs
        from nooch_village.buzz_query_sets import BuzzQuerySets
        return BuzzQuerySets(os.path.join(getattr(context, "data_dir", "."), "buzz_query_sets.json"))

    def _obs_store(self, context):
        st = getattr(context, "buzz_observations", None)
        if st is not None:
            return st
        from nooch_village.buzz_observations import BuzzObservationStore
        return BuzzObservationStore(
            os.path.join(getattr(context, "data_dir", "."), "buzz_observations.jsonl"))

    def _cache(self, context):
        from nooch_village.buzz_observations import BuzzCache
        return BuzzCache(os.path.join(getattr(context, "data_dir", "."), "buzz_cache.json"))

    # ── fetch ─────────────────────────────────────────────────────────────────────
    def _fetch(self, sub: str, query: str, t: str) -> list[dict]:
        """Eén Reddit search-call met exponential backoff op 429. Uitgeputte backoff → _RateLimited."""
        import requests
        params = {"q": query, "restrict_sr": 1, "sort": "new", "t": t, "limit": 25}
        url = _SEARCH.format(sub=urllib.parse.quote(sub)) + "?" + urllib.parse.urlencode(params)
        for attempt in range(_MAX_RETRIES):
            resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
            if resp.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RATE_DELAY * (2 ** attempt))   # 1s, 2s, 4s …
                    continue
                raise _RateLimited(f"429 na {_MAX_RETRIES} pogingen (r/{sub})")
            resp.raise_for_status()
            data = resp.json()
            children = ((data or {}).get("data") or {}).get("children") or []
            return [c for c in children if isinstance(c, dict)]
        return []

    def _to_row(self, child: dict, sub: str, query: str, set_id: str) -> dict:
        d = child.get("data", child) or {}
        pl = (d.get("permalink") or "").strip()
        permalink = ("https://www.reddit.com" + pl) if pl.startswith("/") else pl
        selftext = (d.get("selftext") or "").strip()
        title = (d.get("title") or "").strip()
        fragment = (selftext or title)[:_FRAGMENT_MAX]
        return {
            "platform": "reddit",
            "subreddit": d.get("subreddit") or sub,
            "permalink": permalink,
            "title": title[:300],
            "fragment": fragment,
            "score": int(d.get("score") or 0),
            "num_comments": int(d.get("num_comments") or 0),
            "created_utc": d.get("created_utc"),
            "query": query,
            "query_set_id": set_id,
        }

    # ── run ─────────────────────────────────────────────────────────────────────
    def run(self, payload: dict, context=None) -> dict:
        set_id = (payload.get("query_set_id") or "").strip()
        if not set_id:
            return _refuse("BUZZ_NO_SET", "geen query_set_id opgegeven")
        qset = self._query_sets(context).get(set_id)
        if qset is None:
            return _refuse("BUZZ_NO_SET", "zoek-set bestaat niet", query_set_id=set_id)
        if not qset.get("active"):
            return _refuse("BUZZ_SET_INACTIVE", "zoek-set staat op inactive", query_set_id=set_id)
        subs = qset.get("subreddits") or []
        queries = qset.get("queries") or []
        if not subs or not queries:
            return _refuse("BUZZ_EMPTY_SET", "zoek-set heeft geen subreddits of queries",
                           query_set_id=set_id)

        t = _WINDOW_T.get((payload.get("time_window") or "7d").strip().lower(), "week")
        store = self._obs_store(context)
        cache = self._cache(context)
        now = time.time()
        new = cached = fetched = 0
        did_request = False

        for sub in subs:
            for q in queries:
                key = f"{sub}::{q}"
                if now - cache.ts(key) < _CACHE_TTL:
                    cached += 1                     # verse cache → geen dubbele request
                    continue
                if did_request:
                    time.sleep(_RATE_DELAY)         # rate limit: max 1 request/seconde
                did_request = True
                try:
                    children = self._fetch(sub, q, t)
                except _RateLimited as e:
                    return _refuse("BUZZ_RATE_LIMITED", str(e), subreddit=sub, query=q)
                except Exception as e:              # fail-closed per (sub, query), run gaat door
                    refuse("BUZZ_FETCH_FAILED", str(e), subreddit=sub, query=q)
                    continue
                fetched += 1
                cache.mark(key, now, len(children))
                for child in children:
                    if store.record_observation(self._to_row(child, sub, q, set_id)):
                        new += 1

        if not did_request and cached:
            log.info("🎧 community_listening: alle %d combinaties vers in cache (<6u) — geen requests", cached)
        log.info("🎧 community_listening '%s': %d nieuw / %d gefetcht / %d gecachet",
                 set_id, new, fetched, cached)
        return {"ok": True, "count": new, "new": new, "cached": cached,
                "fetched": fetched, "query_set_id": set_id}
