"""community_listening discovery-modus — de tweede modus naast MONITOR (vaste set uit de config).

DISCOVERY = projectscope: geen query_set_id maar inline `queries` (+ optioneel `focus`). De skill
bouwt dan een EFEMERE set (youtube+bluesky actief, reddit inactief, GEEN library_link → buiten de
Library om) met id `discover:<slug>`, zodat de observaties per project herkenbaar en gescheiden van
de monitor-reeks blijven. HTTP/fetchers gemockt via een spy — geen netwerk."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nooch_village.buzz_observations import BuzzCache, BuzzObservationStore
from nooch_village.buzz_query_sets import BuzzQuerySets, seed_buzz_query_sets
from nooch_village.skills_impl.community_listening import CommunityListeningSkill, _slugify


class FakeLib:
    def __init__(self, data):
        self._d = data

    def all(self):
        return self._d


def _ctx(tmp_path, library=None):
    ctx = SimpleNamespace(settings={"YOUTUBE_API_KEY": "k"}, data_dir=str(tmp_path), library=library)
    ctx.buzz_query_sets = BuzzQuerySets(str(tmp_path / "sets.json"))
    seed_buzz_query_sets(ctx.buzz_query_sets)                 # zet 'barefoot_ervaringen' klaar (monitor)
    ctx.buzz_observations = BuzzObservationStore(str(tmp_path / "obs.jsonl"))
    return ctx


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._p = status, payload or {}

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


# ── validate_payload: grondings-poort dekt beide modi ─────────────────────────

@pytest.mark.smoke
def test_validate_monitor_bestaand_is_ok(tmp_path):
    ctx = _ctx(tmp_path)
    assert CommunityListeningSkill().validate_payload({"query_set_id": "barefoot_ervaringen"}, ctx) == []


def test_validate_monitor_verzonnen_id_wordt_geweigerd(tmp_path):
    ctx = _ctx(tmp_path)
    issues = CommunityListeningSkill().validate_payload({"query_set_id": "duurzame_sneakers_crowd_sentiment"}, ctx)
    assert issues and "bestaat niet" in issues[0]


@pytest.mark.smoke
def test_validate_discovery_queries_zijn_gegrond(tmp_path):
    ctx = _ctx(tmp_path)
    # geen id, wel inline termen → discovery, niets te gronden
    assert CommunityListeningSkill().validate_payload({"queries": ["barefoot slijtage"]}, ctx) == []


def test_validate_zonder_scope_is_niet_uitvoerbaar(tmp_path):
    ctx = _ctx(tmp_path)
    issues = CommunityListeningSkill().validate_payload({}, ctx)
    assert issues and "discovery-queries" in issues[0]


# ── slug is deterministisch ───────────────────────────────────────────────────

def test_slug_deterministisch_en_kort():
    assert _slugify("Barefoot Slijtage!") == "barefoot-slijtage"
    assert _slugify("  ***  ") == ""
    assert len(_slugify("x" * 80)) == 40


# ── run: discovery routeert naar de fetchers, buiten de Library om ────────────

def test_discovery_routeert_inline_queries_en_tagt_met_discover_prefix(tmp_path):
    # Library bevat een approved term; in discovery mag die NIET meelekken (geen library_link).
    ctx = _ctx(tmp_path, library=FakeLib({"vegan sneakers": {"status": "approved", "locale": None}}))
    captured = {}
    from nooch_village.skills_impl import buzz_fetchers

    def spy(set_id, cfg, context, cache, opts):
        captured["set_id"] = set_id
        captured["queries"] = list(cfg.get("queries") or [])
        return {"rows": [], "refuse": None, "requests": 0, "note": ""}

    spy_fetcher = SimpleNamespace(platform="bluesky", fetch=spy)
    with patch.dict(buzz_fetchers.FETCHERS, {"bluesky": spy_fetcher}), \
         patch("time.sleep"), patch("requests.get", return_value=_Resp(200, {"items": []})):
        res = CommunityListeningSkill().run(
            {"queries": ["barefoot slijtage", "barefoot durability"], "focus": "Barefoot slijtage"}, ctx)

    assert res["ok"]
    assert res["query_set_id"] == "discover:barefoot-slijtage"     # mode-tag uit de focus-slug
    assert captured["set_id"] == "discover:barefoot-slijtage"
    assert captured["queries"] == ["barefoot slijtage", "barefoot durability"]
    assert "vegan sneakers" not in captured["queries"]             # buiten de Library om
    assert res["counts"]["reddit"] == "inactief"                   # reddit standaard uit in discovery


def test_discovery_zonder_focus_slugt_op_eerste_query(tmp_path):
    ctx = _ctx(tmp_path)
    from nooch_village.skills_impl import buzz_fetchers

    def spy(set_id, cfg, context, cache, opts):
        return {"rows": [], "refuse": None, "requests": 0, "note": ""}

    with patch.dict(buzz_fetchers.FETCHERS, {"bluesky": SimpleNamespace(platform="bluesky", fetch=spy),
                                             "youtube": SimpleNamespace(platform="youtube", fetch=spy)}), \
         patch("time.sleep"), patch("requests.get", return_value=_Resp(200, {"items": []})):
        res = CommunityListeningSkill().run({"queries": ["Barefoot durability"]}, ctx)
    assert res["query_set_id"] == "discover:barefoot-durability"


def test_run_zonder_scope_weigert(tmp_path):
    ctx = _ctx(tmp_path)
    res = CommunityListeningSkill().run({}, ctx)
    assert res["ok"] is False and res["refuse"] == "BUZZ_NO_SET"
