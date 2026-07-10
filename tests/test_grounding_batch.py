"""Batching-hefboom: Harry grondt meerdere termen in ÉÉN LLM-call i.p.v. één per term.

Default batch_size=1 = ongewijzigd gedrag (direct gronden). >1 = bundelen, met een
flush op de dagelijkse hartslag zodat een restbundel niet blijft hangen.
Thread-vrij; llm.reason gemockt; geen netwerk."""
from __future__ import annotations
import sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from test_harry_hemp import _make_harry
from nooch_village.event_bus import Event


def _kw(word, locale="en"):
    return Event("keyword_proposed", {"word": word, "demand": {"locale": locale}}, "test")


def _collect(bus):
    seen = []
    bus.subscribe("keyword_evidence", lambda e: seen.append(e.data["word"]))
    return seen


# ── _distill_batch primitief ──────────────────────────────────────────────────

def test_distill_batch_parseert_json_object(tmp_path, monkeypatch):
    harry, _ = _make_harry(tmp_path)
    monkeypatch.setattr("nooch_village.llm.reason",
                        lambda p, **kw: '{"vegan": "A about vegan.", "leather": "B about leather."}')
    items = [{"word": "vegan", "locale": "en", "evidence": [{"title": "T", "year": 2020}]},
             {"word": "leather", "locale": "en", "evidence": []}]
    out = harry._distill_batch(items)
    assert out["vegan"] == "A about vegan."
    assert out["leather"] == "B about leather."


def test_distill_batch_fail_closed_valt_terug_per_woord(tmp_path, monkeypatch):
    harry, _ = _make_harry(tmp_path)
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **kw: None)   # LLM weg
    items = [{"word": "vegan", "locale": "en", "evidence": []},
             {"word": "hemp", "locale": "en", "evidence": [{"title": "Paper X", "year": 2021}]}]
    out = harry._distill_batch(items)
    assert "No academic sources found for 'vegan'" in out["vegan"]
    assert "1 source(s) found for 'hemp'" in out["hemp"]


def test_distill_batch_vult_ontbrekend_woord_aan(tmp_path, monkeypatch):
    """LLM geeft maar één van de twee terug → de ander krijgt de fallback."""
    harry, _ = _make_harry(tmp_path)
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **kw: '{"vegan": "Only vegan."}')
    items = [{"word": "vegan", "locale": "en", "evidence": []},
             {"word": "leather", "locale": "en", "evidence": []}]
    out = harry._distill_batch(items)
    assert out["vegan"] == "Only vegan."
    assert "No academic sources found for 'leather'" in out["leather"]


# ── buffer + flush ────────────────────────────────────────────────────────────

def test_default_size_1_grondt_direct(tmp_path):
    harry, bus = _make_harry(tmp_path)
    assert harry._batch_size == 1
    seen = _collect(bus)
    harry._on_keyword_proposed(_kw("vegan"))
    assert seen == ["vegan"]                       # meteen, geen hartslag nodig


def test_bundelt_in_een_call(tmp_path, monkeypatch):
    harry, bus = _make_harry(tmp_path)
    harry._batch_size = 3
    calls = {"n": 0, "sizes": []}

    def spy_batch(items):
        calls["n"] += 1
        calls["sizes"].append(len(items))
        return {it["word"]: f"A:{it['word']}" for it in items}

    monkeypatch.setattr(harry, "_distill_batch", spy_batch)
    seen = _collect(bus)

    harry._on_keyword_proposed(_kw("a"))
    harry._on_keyword_proposed(_kw("b"))
    assert seen == []                              # buffer nog niet vol → nog niks
    harry._on_keyword_proposed(_kw("c"))           # 3e vult de bundel → flush
    assert calls["n"] == 1 and calls["sizes"] == [3]
    assert seen == ["a", "b", "c"]


def test_restbundel_flusht_op_dag_begint(tmp_path, monkeypatch):
    harry, bus = _make_harry(tmp_path)
    harry._batch_size = 5                           # hoger dan wat we sturen
    monkeypatch.setattr(harry, "_distill_batch",
                        lambda items: {it["word"]: "x" for it in items})
    seen = _collect(bus)

    harry._on_keyword_proposed(_kw("a"))
    harry._on_keyword_proposed(_kw("b"))
    assert seen == []                              # blijft in de buffer
    harry._flush_groundings(Event("dag_begint", {}, "test"))
    assert seen == ["a", "b"]                      # hartslag leegt de restbundel


def test_dedup_zelfde_woord_in_buffer(tmp_path):
    harry, bus = _make_harry(tmp_path)
    harry._batch_size = 5
    harry._on_keyword_proposed(_kw("vegan"))
    harry._on_keyword_proposed(_kw("vegan"))       # zelfde term → genegeerd (busy)
    assert len(harry._pending_groundings) == 1
