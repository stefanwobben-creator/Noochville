"""Test: grounding-assessments (_distill) zijn ALTIJD Engels, ook voor NL-termen.
Knowledge-layer = Engels (Stefans regel). Thread-vrij, geen netwerk."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from test_harry_hemp import _make_harry

import nooch_village.llm as llm


def test_distill_geen_bronnen_is_engels(tmp_path):
    harry, _ = _make_harry(tmp_path)
    out = harry._distill("consument", "nl", [], demand={})
    assert "No academic sources" in out
    assert "Geen academische" not in out


def test_distill_forceert_engels_ook_bij_nl_locale(tmp_path, monkeypatch):
    captured = {}
    def fake_reason(prompt, **kw):
        captured["prompt"] = prompt
        return "English assessment."
    monkeypatch.setattr(llm, "reason", fake_reason)

    harry, _ = _make_harry(tmp_path)
    out = harry._distill(
        "consument", "nl",
        [{"title": "X", "year": 2020, "source": "openalex"}], demand={})

    assert "Write your answer in English." in captured["prompt"]
    assert "in Dutch" not in captured["prompt"]      # term-locale lekt niet de output in
    assert out == "English assessment."
