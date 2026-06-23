"""Tests voor NotesStore.link — de graaf-rand (links_to vullen). Thread-vrij.

De link is de keystone onder de kennisgraaf: pas als kaartjes verbonden zijn,
kan de scientist kind-kaartjes ophangen en kan de Content Strategist clusters
combineren. Deze tests leggen de vier regels vast: gericht, persistent,
idempotent, fail-closed (onbestaand of naar-zichzelf).
"""
from __future__ import annotations

from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


def _kaart(kid: str, claim: str = "een claim", word: str | None = None) -> Insight:
    return Insight(id=kid, claim=claim, source="test", word=word)


def _store(tmp_path, *kaarten: Insight) -> NotesStore:
    s = NotesStore(str(tmp_path / "notes.json"))
    for k in kaarten:
        s.add(k)
    return s


def test_link_verbindt_gericht(tmp_path):
    """a -> b: b staat in a.links_to; de link wijst NIET terug."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    bron = s.link("a", "b")
    assert bron is not None
    assert "b" in bron.links_to
    assert s.get("b").links_to == []   # gericht, geen automatische terugkoppeling


def test_link_is_persistent(tmp_path):
    """Een link overleeft een herlaad van schijf."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    vers = NotesStore(str(tmp_path / "notes.json"))
    assert "b" in vers.get("a").links_to


def test_link_is_idempotent(tmp_path):
    """Tweemaal dezelfde link voegt niets dubbels toe."""
    s = _store(tmp_path, _kaart("a"), _kaart("b"))
    s.link("a", "b")
    s.link("a", "b")
    assert s.get("a").links_to == ["b"]


def test_link_naar_onbestaand_kaartje_doet_niets(tmp_path):
    """Fail-closed: ontbreekt bron of doel, dan None en geen wijziging."""
    s = _store(tmp_path, _kaart("a"))
    assert s.link("a", "weg") is None        # doel bestaat niet
    assert s.get("a").links_to == []
    assert s.link("weg", "a") is None        # bron bestaat niet


def test_link_naar_zichzelf_doet_niets(tmp_path):
    """Een kaartje linkt niet naar zichzelf."""
    s = _store(tmp_path, _kaart("a"))
    assert s.link("a", "a") is None
    assert s.get("a").links_to == []
