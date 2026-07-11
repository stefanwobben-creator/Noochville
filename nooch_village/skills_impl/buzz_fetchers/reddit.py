"""Reddit-fetcher — publieke search.json (v1-code ongewijzigd verhuisd naar de registry).

Bron blijft bestaan maar staat in de seed inactief (datacenter-IP's krijgen 403 van Reddit;
wacht op script-app OAuth). Fail-loud: 429→BUZZ_RATE_LIMITED (platform-stop), overige HTTP-fouten
→ BUZZ_FETCH_FAILED per (sub,query) en doorgaan.
"""
from __future__ import annotations

import time
import urllib.parse

from nooch_village.util import refuse
from nooch_village.skills_impl.buzz_fetchers.base import (
    BuzzFetcher, RateLimited, UA, CACHE_TTL, RATE_DELAY, MAX_RETRIES, FRAGMENT_MAX)

_SEARCH = "https://www.reddit.com/r/{sub}/search.json"
_WINDOW_T = {"1d": "day", "7d": "week", "30d": "month", "90d": "month",
             "365d": "year", "1y": "year", "all": "all"}


class RedditFetcher(BuzzFetcher):
    platform = "reddit"

    def _fetch(self, sub: str, query: str, t: str) -> list[dict]:
        """Eén search-call met exponential backoff op 429. Uitgeputte backoff → RateLimited."""
        import requests
        params = {"q": query, "restrict_sr": 1, "sort": "new", "t": t, "limit": 25}
        url = _SEARCH.format(sub=urllib.parse.quote(sub)) + "?" + urllib.parse.urlencode(params)
        for attempt in range(MAX_RETRIES):
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RATE_DELAY * (2 ** attempt))
                    continue
                raise RateLimited(f"429 na {MAX_RETRIES} pogingen (r/{sub})")
            resp.raise_for_status()
            children = ((resp.json() or {}).get("data") or {}).get("children") or []
            return [c for c in children if isinstance(c, dict)]
        return []

    def _to_row(self, child: dict, sub: str, query: str, set_id: str) -> dict:
        d = child.get("data", child) or {}
        pl = (d.get("permalink") or "").strip()
        permalink = ("https://www.reddit.com" + pl) if pl.startswith("/") else pl
        selftext = (d.get("selftext") or "").strip()
        title = (d.get("title") or "").strip()
        return {
            "platform": "reddit",
            "subreddit": d.get("subreddit") or sub,
            "permalink": permalink,
            "title": title[:300],
            "fragment": (selftext or title)[:FRAGMENT_MAX],
            "score": int(d.get("score") or 0),
            "num_comments": int(d.get("num_comments") or 0),
            "created_utc": d.get("created_utc"),
            "query": query,
            "query_set_id": set_id,
        }

    def fetch(self, set_id: str, cfg: dict, context, cache, opts: dict) -> dict:
        subs = cfg.get("subreddits") or []
        queries = cfg.get("queries") or []
        if not subs or not queries:
            return {"rows": [], "refuse": "BUZZ_EMPTY_SET", "requests": 0,
                    "note": "geen subreddits/queries"}
        t = _WINDOW_T.get((opts.get("time_window") or "7d").strip().lower(), "week")
        now = opts["now"]
        rows: list[dict] = []
        made = 0
        did_request = False
        for sub in subs:
            for q in queries:
                key = f"reddit::{sub}::{q}"
                if now - cache.ts(key) < CACHE_TTL:
                    continue
                if did_request:
                    time.sleep(RATE_DELAY)
                did_request = True
                try:
                    children = self._fetch(sub, q, t)
                except RateLimited as e:
                    refuse("BUZZ_RATE_LIMITED", str(e), subreddit=sub, query=q)
                    return {"rows": rows, "refuse": "BUZZ_RATE_LIMITED", "requests": made, "note": "429"}
                except Exception as e:
                    refuse("BUZZ_FETCH_FAILED", str(e), subreddit=sub, query=q)
                    continue
                made += 1
                cache.mark(key, now, len(children))
                rows.extend(self._to_row(c, sub, q, set_id) for c in children)
        return {"rows": rows, "refuse": None, "requests": made, "note": ""}
