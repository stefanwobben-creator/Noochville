"""community_listening: observatie-store (dedup/refuse/index) + BuzzCache, en de Reddit-fetcher
(happy-path, 6u-cache-skip, 429→BUZZ_RATE_LIMITED). Geen netwerk — requests gemockt.

De multi-platform skill-orchestratie, migratie en de YouTube/Bluesky-fetchers staan in
tests/test_community_listening_v2.py."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.buzz_observations import BuzzObservationStore, BuzzCache
from nooch_village.skills_impl.buzz_fetchers.reddit import RedditFetcher


# ── observatie-store ────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_store_dedup_op_permalink(tmp_path):
    st = BuzzObservationStore(str(tmp_path / "buzz.jsonl"))
    row = {"permalink": "https://www.reddit.com/r/x/1", "title": "a", "query_set_id": "s"}
    assert st.record_observation(row) is True
    assert st.record_observation(dict(row)) is False        # zelfde permalink → geen dubbel
    assert len(st.for_set("s")) == 1


@pytest.mark.smoke
def test_store_weigert_rij_zonder_permalink(tmp_path):
    st = BuzzObservationStore(str(tmp_path / "buzz.jsonl"))
    assert st.record_observation({"title": "geen link", "query_set_id": "s"}) is False
    assert st.all() == []                                   # BUZZ_NO_SOURCE: niet opgeslagen


def test_store_index_herbouwt_na_herstart(tmp_path):
    p = str(tmp_path / "buzz.jsonl")
    BuzzObservationStore(p).record_observation({"permalink": "https://r/1", "query_set_id": "s"})
    st2 = BuzzObservationStore(p)                           # verse instance leest het bestand
    assert st2.has("https://r/1")
    assert st2.record_observation({"permalink": "https://r/1", "query_set_id": "s"}) is False


def test_top_by_score_sorteert_en_filtert_platform(tmp_path):
    st = BuzzObservationStore(str(tmp_path / "buzz.jsonl"))
    st.record_observation({"permalink": "https://r/1", "score": 3, "platform": "youtube", "query_set_id": "s"})
    st.record_observation({"permalink": "https://r/2", "score": 40, "platform": "bluesky", "query_set_id": "s"})
    st.record_observation({"permalink": "https://r/3", "score": 12, "platform": "youtube", "query_set_id": "s"})
    assert [r["score"] for r in st.top_by_score("s")] == [40, 12, 3]
    assert [r["score"] for r in st.top_by_score("s", platform="youtube")] == [12, 3]


def test_cache_quota_teller(tmp_path):
    c = BuzzCache(str(tmp_path / "cache.json"))
    assert c.quota_used("youtube", "2026-07-11") == 0
    assert c.quota_add("youtube", "2026-07-11", 100) == 100
    assert c.quota_add("youtube", "2026-07-11", 1) == 101
    c2 = BuzzCache(str(tmp_path / "cache.json"))            # persistente teller
    assert c2.quota_used("youtube", "2026-07-11") == 101


# ── Reddit-fetcher (v1-code, nu in de registry) ────────────────────────────────

class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._p = payload or {}

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _reddit_payload(*permalinks):
    return {"data": {"children": [
        {"data": {"permalink": pl, "title": f"post {pl}", "selftext": "ervaring",
                  "score": 10 + i, "num_comments": 2, "subreddit": "sub"}}
        for i, pl in enumerate(permalinks)]}}


def _cfg():
    return {"active": True, "subreddits": ["sub"], "queries": ["exp"]}


def _opts(now=1_700_000_000.0):
    return {"now": now, "time_window": "7d"}


@pytest.mark.smoke
def test_reddit_fetcher_happy_en_cache_skip(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    payload = _reddit_payload("/r/sub/1", "/r/sub/2")
    with patch("requests.get", return_value=_Resp(200, payload)) as gm:
        res = RedditFetcher().fetch("s", _cfg(), ctx, cache, _opts())
    assert res["refuse"] is None and len(res["rows"]) == 2 and gm.call_count == 1
    assert res["rows"][0]["permalink"].startswith("https://www.reddit.com/r/sub/")
    # tweede run binnen 6u → geen request meer
    with patch("requests.get", return_value=_Resp(200, payload)) as gm2:
        res2 = RedditFetcher().fetch("s", _cfg(), ctx, cache, _opts())
    assert gm2.call_count == 0 and res2["rows"] == []


def test_reddit_fetcher_429_wordt_rate_limited(tmp_path):
    cache = BuzzCache(str(tmp_path / "cache.json"))
    ctx = SimpleNamespace(data_dir=str(tmp_path))
    with patch("time.sleep"), patch("requests.get", return_value=_Resp(429)):
        res = RedditFetcher().fetch("s", _cfg(), ctx, cache, _opts())
    assert res["refuse"] == "BUZZ_RATE_LIMITED" and res["rows"] == []
