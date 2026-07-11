"""Bluesky-fetcher — publieke AT-Protocol search (geen auth).

GET api.bsky.app/xrpc/app.bsky.feed.searchPosts?q&sort=latest&limit=25, nette UA zoals
Reddit. 1 req/s, backoff op 429; harde fail → BUZZ_FETCH_FAILED per query en doorgaan.

Rij: permalink=https://bsky.app/profile/{handle}/post/{rkey} (rkey = laatste segment van de
at://-uri), fragment=post-tekst, score=likeCount, context_id/title leeg.
"""
from __future__ import annotations

import time

from nooch_village.util import refuse
from nooch_village.skills_impl.buzz_fetchers.base import (
    BuzzFetcher, RateLimited, UA, CACHE_TTL, RATE_DELAY, MAX_RETRIES, FRAGMENT_MAX)

_SEARCH = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


class BlueskyFetcher(BuzzFetcher):
    platform = "bluesky"

    def _search(self, query: str) -> list[dict]:
        """Eén searchPosts-call met backoff op 429. Uitgeputte backoff → RateLimited."""
        import requests
        params = {"q": query, "sort": "latest", "limit": 25}
        for attempt in range(MAX_RETRIES):
            resp = requests.get(_SEARCH, params=params, headers={"User-Agent": UA}, timeout=20)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RATE_DELAY * (2 ** attempt))
                    continue
                raise RateLimited(f"429 na {MAX_RETRIES} pogingen (bluesky '{query}')")
            resp.raise_for_status()
            posts = (resp.json() or {}).get("posts") or []
            return [p for p in posts if isinstance(p, dict)]
        return []

    def _to_row(self, post: dict, query: str, set_id: str) -> dict | None:
        uri = (post.get("uri") or "").strip()
        rkey = uri.rsplit("/", 1)[-1] if "/" in uri else ""
        handle = ((post.get("author") or {}).get("handle") or "").strip()
        if not rkey or not handle:
            return None                                   # geen permalink af te leiden → skip
        text = ((post.get("record") or {}).get("text") or "").strip()
        return {
            "platform": "bluesky",
            "permalink": f"https://bsky.app/profile/{handle}/post/{rkey}",
            "title": "",
            "fragment": text[:FRAGMENT_MAX],
            "score": int(post.get("likeCount") or 0),
            "context_id": "",
            "context_title": "",
            "query": query,
            "query_set_id": set_id,
        }

    def fetch(self, set_id: str, cfg: dict, context, cache, opts: dict) -> dict:
        queries = cfg.get("queries") or []
        if not queries:
            return {"rows": [], "refuse": "BUZZ_EMPTY_SET", "requests": 0, "note": "geen queries"}
        now = opts["now"]
        rows: list[dict] = []
        made = 0
        did_request = False
        for q in queries:
            key = f"bluesky::q::{q}"
            if now - cache.ts(key) < CACHE_TTL:
                continue
            if did_request:
                time.sleep(RATE_DELAY)
            did_request = True
            try:
                posts = self._search(q)
            except RateLimited as e:
                refuse("BUZZ_RATE_LIMITED", str(e), query=q)
                return {"rows": rows, "refuse": "BUZZ_RATE_LIMITED", "requests": made, "note": "429"}
            except Exception as e:
                refuse("BUZZ_FETCH_FAILED", str(e), query=q)
                continue
            made += 1
            cache.mark(key, now, len(posts))
            rows.extend(r for r in (self._to_row(p, q, set_id) for p in posts) if r)
        return {"rows": rows, "refuse": None, "requests": made, "note": ""}
