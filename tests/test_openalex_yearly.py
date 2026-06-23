"""Tests voor de OpenAlex jaar-aandeel-modus. Geen netwerk: fetch wordt vervangen."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from nooch_village.skills_impl.openalex import (
    OpenalexSkill, _parse_year_groups, relative_attention,
)


# ── pure helpers ──────────────────────────────────────────────────────────────

def test_parse_year_groups_skipt_niet_numeriek():
    data = {"group_by": [
        {"key": "2018", "count": 100},
        {"key": "2019", "count": 150},
        {"key": "unknown", "count": 5},
        {"key": None, "count": 3},
    ]}
    assert _parse_year_groups(data) == {2018: 100, 2019: 150}


def test_relative_attention_deelt_door_totaal():
    term  = {2018: 10, 2019: 30}
    total = {2018: 1000, 2019: 1500}
    assert relative_attention(term, total) == {2018: 0.01, 2019: 0.02}


def test_relative_attention_slaat_jaar_zonder_totaal_over():
    assert relative_attention({2020: 5}, {2019: 100}) == {}   # geen totaal voor 2020


def test_relative_attention_is_gesorteerd():
    out = relative_attention({2020: 2, 2010: 1}, {2020: 100, 2010: 100})
    assert list(out.keys()) == [2010, 2020]


# ── run() yearly-modus met nep-fetch ──────────────────────────────────────────

class _FakeOpenalex(OpenalexSkill):
    def __init__(self, term_groups, total_groups):
        self._term_groups = term_groups
        self._total_groups = total_groups
        self.calls = 0

    def _fetch_with_backoff(self, req, timeout=12, max_retries=4):
        self.calls += 1
        # eerste call = term (heeft search=), tweede = totaal
        url = req.full_url
        groups = self._term_groups if "search=" in url else self._total_groups
        return {"group_by": groups}


def _ctx():
    return SimpleNamespace(settings={"OPENALEX_API_KEY": "k", "openalex_mailto": "x@y.nl"})


def test_yearly_geeft_relatieve_reeks():
    skill = _FakeOpenalex(
        term_groups=[{"key": "2018", "count": 10}, {"key": "2019", "count": 30}],
        total_groups=[{"key": "2018", "count": 1000}, {"key": "2019", "count": 1500}],
    )
    out = skill.run({"term": "sustainable", "locale": "en", "mode": "yearly"}, _ctx())
    assert out["mode"] == "yearly"
    assert out["series"] == {2018: 0.01, 2019: 0.02}
    assert skill.calls == 2          # term + totaal


def test_yearly_zonder_key_faalt_closed(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    ctx = SimpleNamespace(settings={})
    with pytest.raises(RuntimeError, match="OPENALEX_API_KEY"):
        _FakeOpenalex([], []).run({"term": "x", "mode": "yearly"}, ctx)


def test_yearly_geen_data():
    skill = _FakeOpenalex(term_groups=[], total_groups=[])
    out = skill.run({"term": "x", "locale": "en", "mode": "yearly"}, _ctx())
    assert out["no_data"] is True
    assert out["series"] == {}
