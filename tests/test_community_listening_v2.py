"""community_listening v2: fetcher-registry, migratie-idempotentie, quota-guard, beide
permalink-formaten (YouTube/Bluesky) en het BUZZ_NO_KEY-pad. HTTP volledig gemockt."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.buzz_observations import BuzzCache, BuzzObservationStore
from nooch_village.buzz_query_sets import (
    BuzzQuerySets, seed_buzz_query_sets, migrate_buzz_query_sets, PLATFORM_ORDER)
from nooch_village.skills_impl.buzz_fetchers import FETCHERS, get_fetcher
from nooch_village.skills_impl.buzz_fetchers.youtube import YouTubeFetcher, QUOTA_BUDGET, _utc_day
from nooch_village.skills_impl.buzz_fetchers.bluesky import BlueskyFetcher
from nooch_village.skills_impl.community_listening import CommunityListeningSkill


# ── fetcher-registry ──────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_fetcher_registry_heeft_drie_platforms():
    assert set(FETCHERS) == {"reddit", "youtube", "bluesky"}
    assert get_fetcher("youtube").platform == "youtube"
    assert get_fetcher("bestaat_niet") is None


# ── migratie ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_migratie_wrapt_legacy_en_is_idempotent(tmp_path):
    qs = BuzzQuerySets(str(tmp_path / "sets.json"))
    qs.upsert("old", {"id": "old", "label": "Old", "active": True,
                      "subreddits": ["s1"], "queries": ["q1"]})       # v1-vorm
    assert migrate_buzz_query_sets(qs) == 1
    rec = qs.get("old")
    assert "subreddits" not in rec and "queries" not in rec           # legacy velden weg
    assert rec["platforms"]["reddit"] == {"active": False, "subreddits": ["s1"], "queries": ["q1"]}
    assert migrate_buzz_query_sets(qs) == 0                           # tweede run: niets te doen


def test_seed_vult_ontbrekende_platforms_maar_bewaart_mens_edit(tmp_path):
    qs = BuzzQuerySets(str(tmp_path / "sets.json"))
    seed_buzz_query_sets(qs)
    bf = qs.get("barefoot_ervaringen")
    assert bf["platforms"]["youtube"]["active"] is True
    assert bf["platforms"]["reddit"]["active"] is False              # Reddit inactief geseed
    # mens past youtube-queries aan
    bf["platforms"]["youtube"]["queries"] = ["eigen query"]
    qs.upsert("barefoot_ervaringen", bf)
    seed_buzz_query_sets(qs)                                          # opnieuw seeden/migreren
    assert qs.get("barefoot_ervaringen")["platforms"]["youtube"]["queries"] == ["eigen query"]


# ── HTTP-mock helpers ─────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._p = payload or {}
        self.text = text

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _yt_search(vid, title):
    return {"items": [{"id": {"videoId": vid}, "snippet": {"title": title}}]}


def _yt_comments(*pairs):
    return {"items": [{"snippet": {"topLevelComment": {
        "id": cid, "snippet": {"textOriginal": text, "likeCount": likes}}}}
        for cid, text, likes in pairs]}


def _bsky_posts(*posts):
    return {"posts": [{"uri": uri, "author": {"handle": handle},
                       "record": {"text": text}, "likeCount": likes}
                      for uri, handle, text, likes in posts]}


def _router(*, search=None, comments=None, bsky=None, playlist=None):
    def _get(url, params=None, headers=None, timeout=None):
        params = params or {}
        if "searchPosts" in url:
            return _Resp(200, bsky or {"posts": []})
        if "/playlistItems" in url:
            return _Resp(200, playlist or {"items": []})
        if "/commentThreads" in url:
            return comments(params.get("videoId")) if callable(comments) else _Resp(200, comments or {"items": []})
        if "/search" in url:
            return _Resp(200, search or {"items": []})
        return _Resp(404, {}, "?")
    return _get


def _opts(now=1_700_000_000.0):
    return {"now": now, "time_window": "7d"}


# ── YouTube ──────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_youtube_permalink_en_context_title(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(settings={"YOUTUBE_API_KEY": "k"}, data_dir=str(tmp_path))
    cfg = {"active": True, "channel_ids": [], "queries": ["barefoot"]}
    get = _router(search=_yt_search("VID1", "Great barefoot review"),
                  comments=_yt_comments(("C1", "love it", 12), ("C2", "hurts", 3)))
    with patch("requests.get", get):
        res = YouTubeFetcher().fetch("s", cfg, ctx, cache, _opts())
    assert res["refuse"] is None and len(res["rows"]) == 2
    r0 = res["rows"][0]
    assert r0["permalink"] == "https://www.youtube.com/watch?v=VID1&lc=C1"
    assert r0["context_id"] == "VID1" and r0["context_title"] == "Great barefoot review"
    assert r0["platform"] == "youtube" and r0["score"] == 12
    # quota: search(100) + commentThreads(1) = 101
    assert cache.quota_used("youtube", _utc_day(_opts()["now"])) == 101


def test_youtube_geen_key_geeft_buzz_no_key(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path))
    res = YouTubeFetcher().fetch("s", {"active": True, "queries": ["x"]}, ctx, cache, _opts())
    assert res["refuse"] == "BUZZ_NO_KEY" and res["rows"] == []


@pytest.mark.smoke
def test_youtube_quota_guard_stopt(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    day = _utc_day(_opts()["now"])
    cache.quota_add("youtube", day, QUOTA_BUDGET - 1)          # bijna op: search(100) zou overschrijden
    ctx = SimpleNamespace(settings={"YOUTUBE_API_KEY": "k"}, data_dir=str(tmp_path))
    with patch("requests.get", _router(search=_yt_search("V", "t"))):
        res = YouTubeFetcher().fetch("s", {"active": True, "queries": ["x"]}, ctx, cache, _opts())
    assert res["refuse"] == "BUZZ_QUOTA" and res["rows"] == []
    assert cache.quota_used("youtube", day) == QUOTA_BUDGET - 1    # geen unit meer uitgegeven


def test_youtube_comments_disabled_skipt(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(settings={"YOUTUBE_API_KEY": "k"}, data_dir=str(tmp_path))
    def comments(vid):
        return _Resp(403, {}, '{"error":{"errors":[{"reason":"commentsDisabled"}]}}')
    with patch("requests.get", _router(search=_yt_search("V", "t"), comments=comments)):
        res = YouTubeFetcher().fetch("s", {"active": True, "queries": ["x"]}, ctx, cache, _opts())
    assert res["refuse"] is None and res["rows"] == []             # geen error, wel geskipt


# ── Bluesky ──────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_bluesky_permalink_uit_at_uri(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path))
    bsky = _bsky_posts(("at://did:plc:abc/app.bsky.feed.post/rk1", "alice.bsky.social", "love barefoot", 5))
    with patch("requests.get", _router(bsky=bsky)):
        res = BlueskyFetcher().fetch("s", {"active": True, "queries": ["barefoot"]}, ctx, cache, _opts())
    assert res["refuse"] is None and len(res["rows"]) == 1
    assert res["rows"][0]["permalink"] == "https://bsky.app/profile/alice.bsky.social/post/rk1"
    assert res["rows"][0]["score"] == 5 and res["rows"][0]["platform"] == "bluesky"


# ── skill-orchestratie (multi-platform) ───────────────────────────────────────

def _skill_ctx(tmp_path, with_key=True):
    ctx = SimpleNamespace(settings=({"YOUTUBE_API_KEY": "k"} if with_key else {}),
                          data_dir=str(tmp_path))
    ctx.buzz_query_sets = BuzzQuerySets(str(tmp_path / "sets.json"))
    seed_buzz_query_sets(ctx.buzz_query_sets)
    ctx.buzz_observations = BuzzObservationStore(str(tmp_path / "obs.jsonl"))
    return ctx


@pytest.mark.smoke
def test_skill_mengt_youtube_en_bluesky(tmp_path):
    ctx = _skill_ctx(tmp_path, with_key=True)
    get = _router(search=_yt_search("V", "vid"), comments=_yt_comments(("C1", "a", 1)),
                  bsky=_bsky_posts(("at://d/app.bsky.feed.post/r1", "bob.bsky.social", "b", 2)))
    with patch("time.sleep"), patch("requests.get", get):
        res = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, ctx)
    assert res["ok"] and res["new"] >= 2
    assert res["counts"]["reddit"] == "inactief"
    assert isinstance(res["counts"]["youtube"], int) and isinstance(res["counts"]["bluesky"], int)
    assert "reddit: inactief" in res["summary"]


def test_skill_zonder_youtube_key_draait_bluesky_door(tmp_path):
    ctx = _skill_ctx(tmp_path, with_key=False)
    get = _router(bsky=_bsky_posts(("at://d/app.bsky.feed.post/r1", "bob.bsky.social", "b", 2)))
    with patch("time.sleep"), patch("requests.get", get):
        res = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, ctx)
    assert res["ok"] and res["counts"]["bluesky"] >= 1
    assert res["counts"]["youtube"] == 0
    assert "BUZZ_NO_KEY" in res["summary"]


def test_platform_order_youtube_eerst():
    assert PLATFORM_ORDER[0] == "youtube" and "reddit" in PLATFORM_ORDER
