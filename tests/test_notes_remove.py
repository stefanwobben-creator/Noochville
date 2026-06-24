"""Tests voor NotesStore.remove (curatie-primitive). Thread-vrij."""
from __future__ import annotations

from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight


def test_remove_verwijdert_kaartje(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim="A", source="s"))
    assert notes.remove("a") is True
    assert notes.get("a") is None


def test_remove_ruimt_inkomende_touwtjes_op(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    notes.add(Insight(id="a", claim="A", source="s"))
    notes.add(Insight(id="b", claim="B", source="s"))
    notes.link("b", "a")                       # b → a
    notes.remove("a")
    assert notes.get("b").links_to == []       # geen dangling verwijzing naar a


def test_remove_onbekend_geeft_false(tmp_path):
    notes = NotesStore(str(tmp_path / "notes.json"))
    assert notes.remove("bestaat_niet") is False
