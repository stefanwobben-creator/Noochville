"""Tests: de Field Note mag niet gegijzeld worden door een trage/flaky Google Trends.

run_bounded begrenst een trage call; _bounded_trends levert altijd een bruikbare dict
(skill-output of {"error": ...}) zodat field_note de note toch kan schrijven.
Thread-vrij qua dorp, geen netwerk.
"""
from __future__ import annotations

import time

from nooch_village.util import run_bounded
from nooch_village.roles import _bounded_trends


# ── run_bounded ───────────────────────────────────────────────────────────────

def test_run_bounded_snel_geeft_resultaat():
    ok, res = run_bounded(lambda: 42, timeout_s=1.0)
    assert ok is True
    assert res == 42


def test_run_bounded_traag_geeft_timeout():
    ok, res = run_bounded(lambda: time.sleep(2.0), timeout_s=0.1)
    assert ok is False
    assert res is None                       # time-out


def test_run_bounded_vangt_exceptie():
    ok, res = run_bounded(lambda: 1 / 0, timeout_s=1.0)
    assert ok is False
    assert isinstance(res, ZeroDivisionError)


# ── _bounded_trends ───────────────────────────────────────────────────────────

def test_bounded_trends_levert_data_binnen_budget():
    payload = {"keywords": {"vegan shoes": {"interest_latest": 80}}, "rows": [1]}
    out = _bounded_trends(lambda: payload, budget=1.0)
    assert out is payload                     # ongewijzigd doorgegeven


def test_bounded_trends_timeout_geeft_error_dict():
    out = _bounded_trends(lambda: time.sleep(2.0), budget=0.1)
    assert "error" in out
    assert out["keywords"] == {}
    assert out["rows"] == []
    assert "tijdslimiet" in out["error"]


def test_bounded_trends_exceptie_geeft_error_dict():
    def boom():
        raise RuntimeError("429 rate limited")
    out = _bounded_trends(boom, budget=1.0)
    assert "error" in out
    assert "429" in out["error"]
    assert out["keywords"] == {} and out["rows"] == []


def test_field_note_schrijft_door_met_trends_error(tmp_path):
    """Bewijs het eindresultaat: met een trends-error schrijft field_note nog steeds
    een Field Note op basis van Plausible."""
    from types import SimpleNamespace
    from nooch_village.skills_impl.field_note import FieldNoteSkill

    ctx = SimpleNamespace(data_dir=str(tmp_path))
    plausible = {"results": {"visitors": {"value": 107}}}
    trends = _bounded_trends(lambda: time.sleep(2.0), budget=0.1)   # timeout → error dict
    out = FieldNoteSkill().run({"plausible": plausible, "trends": trends}, ctx)
    assert out["path"] is not None
    import os
    assert os.path.exists(out["path"])
