"""community_listening v2.1 — Library-koppeling: allowlist-statusfilter, exclude, cap, diff-log,
BUZZ_LIBRARY_UNAVAILABLE (fail-open), locale-filter en migratie-idempotentie."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.buzz_observations import BuzzCache, BuzzObservationStore
from nooch_village.buzz_query_sets import (
    BuzzQuerySets, seed_buzz_query_sets, migrate_buzz_query_sets)
from nooch_village.buzz_library_sync import sync_library_terms
from nooch_village.skills_impl.community_listening import CommunityListeningSkill


class FakeLib:
    def __init__(self, data):
        self._d = data

    def all(self):
        return self._d


class BrokenLib:
    def all(self):
        raise IOError("library kapot")


def _link(active=True, locale=("nl", "en"), max_queries=10, exclude=(), tags=()):
    return {"active": active,
            "filter": {"status": "research_approved", "tags": list(tags), "locale": list(locale)},
            "max_queries": max_queries, "exclude": list(exclude)}


def _cache(tmp_path):
    return BuzzCache(str(tmp_path / "cache.json"))


# ── statusfilter = ALLOWLIST ──────────────────────────────────────────────────

@pytest.mark.smoke
def test_status_is_allowlist_alleen_approved_passeert(tmp_path):
    lib = FakeLib({
        "goedgekeurd":  {"status": "approved"},
        "verboden":     {"status": "forbidden"},
        "vermijden":    {"status": "avoid"},
        "banaan":       {"status": "banaan"},        # onbekende, toekomstige status → moet AF vallen
        "leeg":         {},                           # geen status → af
    })
    res = sync_library_terms("s", "bluesky", _link(locale=[]), lib, _cache(tmp_path))
    assert res == ["goedgekeurd"]                     # alleen approved; alle andere (ook 'banaan') geweigerd


def test_exclude_wint_van_filter_match(tmp_path):
    lib = FakeLib({"a": {"status": "approved"}, "b": {"status": "approved"}})
    res = sync_library_terms("s", "bluesky", _link(locale=[], exclude=["A"]), lib, _cache(tmp_path))
    assert res == ["b"]                                # 'a' geëxcludeerd (case-insensitive)


# ── cap ───────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_cap_deterministisch_en_logt_afgevallen_termen(tmp_path, caplog):
    lib = FakeLib({w: {"status": "approved"} for w in ("delta", "alpha", "charlie", "bravo")})
    with caplog.at_level(logging.WARNING):
        res = sync_library_terms("s", "bluesky", _link(locale=[], max_queries=2), lib, _cache(tmp_path))
    assert res == ["alpha", "bravo"]                  # eerste 2 alfabetisch
    assert "BUZZ_LIBRARY_CAP" in caplog.text
    assert "charlie" in caplog.text and "delta" in caplog.text   # afgevallen termen benoemd


# ── diff-log ──────────────────────────────────────────────────────────────────

def test_diff_log_plus_min_en_geen_regel_bij_geen_verandering(tmp_path, caplog):
    cache = _cache(tmp_path)
    data = {"a": {"status": "approved"}, "b": {"status": "approved"}}
    lib = FakeLib(data)
    with caplog.at_level(logging.INFO, logger="village.skill.buzz"):
        sync_library_terms("s", "bluesky", _link(locale=[]), lib, cache)
        assert "library-sync [s/bluesky]: +2 (a, b)" in caplog.text
        caplog.clear()
        sync_library_terms("s", "bluesky", _link(locale=[]), lib, cache)   # geen verandering
        assert "library-sync" not in caplog.text
        caplog.clear()
        data.pop("b"); data["c"] = {"status": "approved"}                   # b weg, c erbij
        sync_library_terms("s", "bluesky", _link(locale=[]), lib, cache)
        assert "+1 (c)" in caplog.text and "-1 (b)" in caplog.text


# ── BUZZ_LIBRARY_UNAVAILABLE (fail-open) ──────────────────────────────────────

def test_library_none_geeft_unavailable(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        res = sync_library_terms("s", "bluesky", _link(), None, _cache(tmp_path))
    assert res == [] and "BUZZ_LIBRARY_UNAVAILABLE" in caplog.text


def test_library_exception_geeft_unavailable(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        res = sync_library_terms("s", "bluesky", _link(), BrokenLib(), _cache(tmp_path))
    assert res == [] and "BUZZ_LIBRARY_UNAVAILABLE" in caplog.text


# ── locale-filter ─────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_locale_filter_gevraagde_plus_null(tmp_path):
    lib = FakeLib({
        "nl_term":   {"status": "approved", "locale": "nl"},
        "en_term":   {"status": "approved", "locale": "en"},
        "de_term":   {"status": "approved", "locale": "de"},
        "null_term": {"status": "approved", "locale": None},
    })
    res = sync_library_terms("s", "bluesky", _link(locale=["nl"]), lib, _cache(tmp_path))
    assert res == ["nl_term", "null_term"]            # nl + null passeren; en/de vallen af


# ── migratie: additief + mens-edit-behoud ─────────────────────────────────────

@pytest.mark.smoke
def test_migratie_voegt_library_link_toe_en_bewaart_mens_edit(tmp_path):
    qs = BuzzQuerySets(str(tmp_path / "sets.json"))
    # v2-vorm zonder library_link (pre-v2.1 prod)
    qs.upsert("barefoot_ervaringen", {
        "id": "barefoot_ervaringen", "label": "B", "active": True,
        "platforms": {"bluesky": {"active": True, "queries": ["barefoot shoes"]},
                      "youtube": {"active": True, "channel_ids": [], "queries": ["x"]}}})
    assert migrate_buzz_query_sets(qs) == 1
    bl = qs.platform_cfg("barefoot_ervaringen", "bluesky")
    assert bl["library_link"]["active"] is True
    assert "library_link" not in qs.platform_cfg("barefoot_ervaringen", "youtube")   # youtube blijft dicht
    # mens edit: exclude, daarna opnieuw migreren → niet overschreven
    bl["library_link"]["exclude"] = ["barefoot schoenen"]
    rec = qs.get("barefoot_ervaringen"); qs.upsert("barefoot_ervaringen", rec)
    assert migrate_buzz_query_sets(qs) == 0                                            # niets meer te doen
    assert qs.platform_cfg("barefoot_ervaringen", "bluesky")["library_link"]["exclude"] == ["barefoot schoenen"]


# ── skill-integratie: fail-open + termen bereiken de fetcher ──────────────────

class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._p = status, payload or {}

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _bsky_one():
    return {"posts": [{"uri": "at://d/app.bsky.feed.post/r1", "author": {"handle": "a.bsky.social"},
                       "record": {"text": "prima ervaring met barefoot"}, "likeCount": 3}]}


def _skill_ctx(tmp_path, library):
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path), library=library)
    ctx.buzz_query_sets = BuzzQuerySets(str(tmp_path / "sets.json"))
    seed_buzz_query_sets(ctx.buzz_query_sets)
    ctx.buzz_observations = BuzzObservationStore(str(tmp_path / "obs.jsonl"))
    return ctx


def test_skill_library_unavailable_draait_handmatige_queries_door(tmp_path):
    ctx = _skill_ctx(tmp_path, library=None)          # geen library → fail-open
    with patch("time.sleep"), patch("requests.get", return_value=_Resp(200, _bsky_one())):
        res = CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, ctx)
    assert res["ok"] and res["counts"]["bluesky"] >= 1     # bluesky draaide op de handmatige queries


def test_skill_library_termen_bereiken_de_bluesky_fetcher(tmp_path):
    ctx = _skill_ctx(tmp_path, library=FakeLib({"vegan sneakers": {"status": "approved", "locale": None}}))
    captured = {}
    from nooch_village.skills_impl import buzz_fetchers
    real = buzz_fetchers.FETCHERS["bluesky"].fetch

    def spy(set_id, cfg, context, cache, opts):
        captured["queries"] = list(cfg.get("queries") or [])
        return {"rows": [], "refuse": None, "requests": 0, "note": ""}

    with patch.dict(buzz_fetchers.FETCHERS, {"bluesky": SimpleNamespace(platform="bluesky", fetch=spy)}), \
         patch("time.sleep"), patch("requests.get", return_value=_Resp(200, {"items": []})):
        CommunityListeningSkill().run({"query_set_id": "barefoot_ervaringen"}, ctx)
    assert "vegan sneakers" in captured["queries"]     # library-term gemerged in de effectieve queries
    assert "barefoot shoes" in captured["queries"]     # handmatige query ook nog aanwezig
