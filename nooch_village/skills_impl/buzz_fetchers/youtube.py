"""YouTube-fetcher — comments als gebruikerservaringen (Data API v3, YOUTUBE_API_KEY).

Twee modi, kanaal-modus vóór query-modus:
  a) channel_ids → uploads-playlist (UC…→UU…-conventie, geen extra channels.list-unit) via
     playlistItems.list (1 unit), recentste 5 video's; dan commentThreads.list per video (1 unit).
  b) queries → search.list (100 units!) max 1 call/query/puls, top-3 video's; dan commentThreads.

Quota-guard: dagteller in BuzzCache, budget 2.000 units/dag. Check-before-call; overschrijding →
BUZZ_QUOTA en de fetcher stopt netjes met wat hij al heeft. Geen key → BUZZ_NO_KEY (alleen YouTube
slaat over). Comments uit op een video → BUZZ_COMMENTS_DISABLED + skip, geen error.

Elke rij draagt context_id (videoId) + context_title (videotitel, VERPLICHT) zodat een comment
later te duiden is (het frame-effect).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from nooch_village.util import refuse
from nooch_village.skills_impl.buzz_fetchers.base import BuzzFetcher, UA, CACHE_TTL, FRAGMENT_MAX

_API = "https://www.googleapis.com/youtube/v3"
QUOTA_BUDGET = 2000
_COST = {"search": 100, "playlistItems": 1, "commentThreads": 1}
_VIDEOS_PER_CHANNEL = 5
_VIDEOS_PER_QUERY = 3
_COMMENTS_PER_VIDEO = 50
_MIN_COMMENT_LEN = 15         # kortere comments ("nice!", "🔥", "first") tellen als 'te kort' en worden overgeslagen


class _QuotaExceeded(Exception):
    """Het dag-quotabudget zou overschreden worden door de volgende call."""


def _api_key(context) -> str:
    return (getattr(context, "settings", {}) or {}).get("YOUTUBE_API_KEY") or os.getenv("YOUTUBE_API_KEY") or ""


def _utc_day(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).date().isoformat()


class YouTubeFetcher(BuzzFetcher):
    platform = "youtube"

    def __init__(self):
        self._cache = None
        self._day = None
        self._short = 0          # aantal comments dat als 'te kort' is overgeslagen (per fetch)

    def _get(self, endpoint: str, params: dict) -> dict:
        import requests
        resp = requests.get(f"{_API}/{endpoint}", params=params,
                            headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        return resp.json() or {}

    def _spend(self, units: int) -> None:
        """Check-before-call: reserveer units of gooi _QuotaExceeded als het budget op is."""
        if self._cache.quota_used("youtube", self._day) + units > QUOTA_BUDGET:
            raise _QuotaExceeded()
        self._cache.quota_add("youtube", self._day, units)

    # ── video-bronnen ──────────────────────────────────────────────────────────
    def _channel_videos(self, channel_id: str, key: str) -> list[dict]:
        """Recentste video's van een kanaal via de uploads-playlist (UC…→UU…)."""
        playlist = ("UU" + channel_id[2:]) if channel_id.startswith("UC") else channel_id
        self._spend(_COST["playlistItems"])
        data = self._get("playlistItems", {
            "part": "snippet", "playlistId": playlist,
            "maxResults": _VIDEOS_PER_CHANNEL, "key": key})
        out = []
        for it in data.get("items", []):
            sn = it.get("snippet") or {}
            vid = ((sn.get("resourceId") or {}).get("videoId") or "").strip()
            if vid:
                out.append({"videoId": vid, "title": (sn.get("title") or "").strip()})
        return out

    def _query_videos(self, query: str, key: str) -> list[dict]:
        """Top-video's voor een zoekterm via search.list (100 units!)."""
        self._spend(_COST["search"])
        data = self._get("search", {
            "part": "snippet", "type": "video", "q": query,
            "maxResults": _VIDEOS_PER_QUERY, "order": "relevance", "key": key})
        out = []
        for it in data.get("items", []):
            vid = ((it.get("id") or {}).get("videoId") or "").strip()
            if vid:
                out.append({"videoId": vid, "title": ((it.get("snippet") or {}).get("title") or "").strip()})
        return out

    def _video_comments(self, video: dict, query: str, set_id: str, key: str) -> list[dict]:
        """Top-level comments van één video → rijen. Comments uit → BUZZ_COMMENTS_DISABLED + skip."""
        import requests
        vid = video["videoId"]
        title = video.get("title", "")
        self._spend(_COST["commentThreads"])
        resp = requests.get(f"{_API}/commentThreads", headers={"User-Agent": UA}, timeout=20,
                           params={"part": "snippet", "videoId": vid,
                                   "maxResults": _COMMENTS_PER_VIDEO, "order": "relevance", "key": key})
        if resp.status_code == 403 and "commentsDisabled" in resp.text:
            refuse("BUZZ_COMMENTS_DISABLED", "comments uitgeschakeld op video", video_id=vid)
            return []
        resp.raise_for_status()
        rows = []
        for it in (resp.json() or {}).get("items", []):
            top = ((it.get("snippet") or {}).get("topLevelComment") or {})
            cid = (top.get("id") or "").strip()
            sn = top.get("snippet") or {}
            text = (sn.get("textOriginal") or sn.get("textDisplay") or "").strip()
            if not cid or not text:
                continue
            if len(text) < _MIN_COMMENT_LEN:            # ruis ('nice!', emoji) → 'te kort', overslaan
                self._short += 1
                continue
            rows.append({
                "platform": "youtube",
                "permalink": f"https://www.youtube.com/watch?v={vid}&lc={cid}",
                "title": "",
                "fragment": text[:FRAGMENT_MAX],
                "score": int(sn.get("likeCount") or 0),
                "context_id": vid,
                "context_title": title,           # VERPLICHT: frame voor de comment
                "query": query,
                "query_set_id": set_id,
            })
        return rows

    def _harvest(self, videos: list[dict], query: str, set_id: str, key: str, rows: list[dict]) -> None:
        """Verzamel comments per video; isoleer per-video fouten (behalve quota, die stopt alles)."""
        for v in videos:
            try:
                rows.extend(self._video_comments(v, query, set_id, key))
            except _QuotaExceeded:
                raise
            except Exception as e:
                refuse("BUZZ_FETCH_FAILED", str(e), video_id=v.get("videoId"))

    # ── orchestratie ────────────────────────────────────────────────────────────
    def fetch(self, set_id: str, cfg: dict, context, cache, opts: dict) -> dict:
        key = _api_key(context)
        if not key:
            refuse("BUZZ_NO_KEY", "YOUTUBE_API_KEY ontbreekt — YouTube-fetcher slaat over")
            return {"rows": [], "refuse": "BUZZ_NO_KEY", "requests": 0, "note": "geen key"}
        self._cache = cache
        self._short = 0
        now = opts["now"]
        self._day = _utc_day(now)
        channels = cfg.get("channel_ids") or []
        queries = cfg.get("queries") or []
        rows: list[dict] = []
        made = 0
        try:
            # a) kanaal-modus (voorrang)
            for ch in channels:
                ckey = f"youtube::ch::{ch}"
                if now - cache.ts(ckey) < CACHE_TTL:
                    continue
                try:
                    videos = self._channel_videos(ch, key)
                except _QuotaExceeded:
                    raise
                except Exception as e:
                    refuse("BUZZ_FETCH_FAILED", str(e), channel_id=ch)
                    continue
                made += 1
                cache.mark(ckey, now, len(videos))
                self._harvest(videos, f"channel:{ch}", set_id, key, rows)
            # b) query-modus
            for q in queries:
                qkey = f"youtube::q::{q}"
                if now - cache.ts(qkey) < CACHE_TTL:
                    continue
                try:
                    videos = self._query_videos(q, key)
                except _QuotaExceeded:
                    raise
                except Exception as e:
                    refuse("BUZZ_FETCH_FAILED", str(e), query=q)
                    continue
                made += 1
                cache.mark(qkey, now, len(videos))
                self._harvest(videos, q, set_id, key, rows)
        except _QuotaExceeded:
            refuse("BUZZ_QUOTA", f"YouTube dagbudget {QUOTA_BUDGET} units bereikt",
                   used=cache.quota_used("youtube", self._day))
            return {"rows": rows, "refuse": "BUZZ_QUOTA", "requests": made,
                    "short": self._short, "note": "quota"}
        return {"rows": rows, "refuse": None, "requests": made, "short": self._short,
                "note": f"{cache.quota_used('youtube', self._day)}u/{QUOTA_BUDGET}"}
