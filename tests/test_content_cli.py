"""Tests voor de testbare CLI-helpers van de content-loop (brokje 13d-ii)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from nooch_village.inbox.__main__ import _content_suggestion_event, _content_check_report
from nooch_village.notes_store import NotesStore


def test_suggestion_event_bouwt_brief():
    item = {"context": {"seed_id": "trend", "cluster_ids": ["trend", "b"]}}
    ev = _content_suggestion_event(item, "blog", "Yasmine", "nieuwsgierig")
    assert ev == {"seed_id": "trend", "kind": "blog",
                  "audience": "Yasmine", "desired_outcome": "nieuwsgierig"}


def test_suggestion_event_kind_default():
    ev = _content_suggestion_event({"context": {"seed_id": "trend"}}, "", "", "")
    assert ev["kind"] == "blog"


def test_check_report_blokkeert_verboden_woord(tmp_path):
    store = NotesStore(str(tmp_path / "n.json"))
    ctx = SimpleNamespace(notes=store, copy_rules="REGELS")
    item = {"context": {"kind": "sales_page", "claim_insight_ids": []}}
    with patch("nooch_village.llm.reason", return_value="OK"):
        rep = _content_check_report(item, "Gemaakt van plastic.", ctx)
    assert "plastic" in rep["forbidden_words"]
    assert rep["gate_ok"] is False


def test_check_report_schone_blog_is_ok(tmp_path):
    store = NotesStore(str(tmp_path / "n.json"))
    ctx = SimpleNamespace(notes=store, copy_rules="REGELS")
    item = {"context": {"kind": "blog", "claim_insight_ids": []}}
    with patch("nooch_village.llm.reason", return_value="OK"):
        rep = _content_check_report(item, "Een schone tekst.", ctx)
    assert rep["gate_ok"] is True
