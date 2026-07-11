"""community_listening (Billy Buzz): observatie-store (dedup/refuse), zoek-set-seed en de
skill (cache-skip, 429→BUZZ_RATE_LIMITED, happy-path parse). Geen netwerk — requests gemockt."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.buzz_observations import BuzzObservationStore
from nooch_village.buzz_query_sets import BuzzQuerySets, seed_buzz_query_sets
from nooch_village.skills_impl.community_listening import CommunityListeningSkill, _MAX_RETRIES


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


def test_top_by_score_sorteert_aflopend(tmp_path):
    st = BuzzObservationStore(str(tmp_path / "buzz.jsonl"))
    for i, sc in enumerate([3, 40, 12]):
        st.record_observation({"permalink": f"https://r/{i}", "score": sc, "query_set_id": "s"})
    scores = [r["score"] for r in st.top_by_score("s", limit=5)]
    assert scores == [40, 12, 3]


# ── zoek-sets ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_seed_idempotent_en_mens_curatie_ongemoeid(tmp_path):
    qs = BuzzQuerySets(str(tmp_path / "sets.json"))
    seed_buzz_query_sets(qs)
    assert qs.get("barefoot_ervaringen")["active"] is True
    qs.add("barefoot_ervaringen", "Aangepast", ["q"], ["sub"], active=False)   # mens wijzigt
    seed_buzz_query_sets(qs)                                # tweede seed
    assert qs.get("barefoot_ervaringen")["label"] == "Aangepast"   # niet overschreven
    assert len(qs.all()) == 1


# ── skill: fetch/cache/backoff ────────────────────────────────────────────────

class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


def _reddit_payload(*permalinks):
    return {"data": {"children": [
        {"data": {"permalink": pl, "title": f"post {pl}", "selftext": "ervaring hier",
                  "score": 10 + i, "num_comments": 2, "created_utc": 1, "subreddit": "sub"}}
        for i, pl in enumerate(permalinks)]}}


def _ctx(tmp_path):
    ctx = SimpleNamespace(data_dir=str(tmp_path), settings={})
    ctx.buzz_query_sets = BuzzQuerySets(str(tmp_path / "sets.json"))
    ctx.buzz_query_sets.add("s1", "Set 1", ["exp"], ["sub"], active=True)
    ctx.buzz_observations = BuzzObservationStore(str(tmp_path / "buzz.jsonl"))
    return ctx


@pytest.mark.smoke
def test_skill_happy_path_en_cache_skip(tmp_path):
    ctx = _ctx(tmp_path)
    payload = _reddit_payload("/r/sub/1", "/r/sub/2")
    with patch("requests.get", return_value=_Resp(200, payload)) as gm:
        res = CommunityListeningSkill().run({"query_set_id": "s1"}, ctx)
    assert res["ok"] and res["new"] == 2 and res["fetched"] == 1
    assert gm.call_count == 1
    # permalink canoniek gemaakt
    rows = ctx.buzz_observations.for_set("s1")
    assert rows[0]["permalink"].startswith("https://www.reddit.com/r/sub/")
    assert rows[0]["platform"] == "reddit"
    # tweede run binnen 6u → geen enkele request meer, niets nieuws
    with patch("requests.get", return_value=_Resp(200, payload)) as gm2:
        res2 = CommunityListeningSkill().run({"query_set_id": "s1"}, ctx)
    assert gm2.call_count == 0 and res2["cached"] == 1 and res2["new"] == 0


@pytest.mark.smoke
def test_skill_429_wordt_buzz_rate_limited(tmp_path):
    ctx = _ctx(tmp_path)
    with patch("nooch_village.skills_impl.community_listening.time.sleep"), \
         patch("requests.get", return_value=_Resp(429)) as gm:
        res = CommunityListeningSkill().run({"query_set_id": "s1"}, ctx)
    assert res["ok"] is False and res["refuse"] == "BUZZ_RATE_LIMITED"
    assert gm.call_count == _MAX_RETRIES                    # backoff uitgeput


def test_skill_onbekende_set_weigert(tmp_path):
    ctx = _ctx(tmp_path)
    res = CommunityListeningSkill().run({"query_set_id": "bestaat_niet"}, ctx)
    assert res["ok"] is False and res["refuse"] == "BUZZ_NO_SET"


def test_skill_inactieve_set_weigert(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.buzz_query_sets.set_active("s1", False)
    res = CommunityListeningSkill().run({"query_set_id": "s1"}, ctx)
    assert res["ok"] is False and res["refuse"] == "BUZZ_SET_INACTIVE"
