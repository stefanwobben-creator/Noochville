"""Tests voor NotesStore.content_seeds (Fase 2 brokje 13a). Thread-vrij.

Content-waardig = bevestigd (emergentie) EN verbonden (een echt cluster).
"""
from __future__ import annotations

from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


def _kaart(kid, count, links=None):
    return Insight(id=kid, claim="c", source="t", word=kid, grounding_count=count,
                   links_to=links or [])


def _store(tmp_path, *kaarten):
    s = NotesStore(str(tmp_path / "notes.json"))
    for k in kaarten:
        s.add(k)
    return s


def test_bevestigd_en_verbonden_is_content_waardig(tmp_path):
    # trend (count 4) met een buur 'b' -> content-waardig
    s = _store(tmp_path, _kaart("trend", 4), _kaart("b", 1, links=["trend"]))
    assert [n.id for n in s.content_seeds(budget=5)] == ["trend"]


def test_bevestigd_maar_los_telt_niet(tmp_path):
    # emerged maar geen buren -> geen cluster -> niet content-waardig
    s = _store(tmp_path, _kaart("eenzaam", 5))
    assert s.content_seeds(budget=5) == []


def test_onbevestigd_telt_niet(tmp_path):
    s = _store(tmp_path, _kaart("vers", 1), _kaart("b", 1, links=["vers"]))
    assert s.content_seeds(budget=5) == []


def test_budget_en_sterkste_eerst(tmp_path):
    s = _store(tmp_path,
               _kaart("a", 3), _kaart("b", 9), _kaart("c", 5),
               _kaart("x", 1, links=["a"]), _kaart("y", 1, links=["b"]),
               _kaart("z", 1, links=["c"]))
    gekozen = [n.id for n in s.content_seeds(budget=2)]
    assert gekozen == ["b", "c"]   # 9 en 5, niet de 3


def test_budget_nul_is_leeg(tmp_path):
    s = _store(tmp_path, _kaart("trend", 9), _kaart("b", 1, links=["trend"]))
    assert s.content_seeds(budget=0) == []
