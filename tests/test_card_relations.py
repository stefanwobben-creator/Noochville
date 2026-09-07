"""Kennislaag brok 5: bewijs-links leggen tijdens review (kaartpagina).
NotesStore.add_relation + acties note_support/note_contradict + live sterkte op /card."""
from __future__ import annotations
import os
import tempfile

from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight, ClaimKind, EvidenceType
from nooch_village.knowledge import strength, Strength


def _data():
    d = tempfile.mkdtemp()
    ns = NotesStore(os.path.join(d, "notes.json"))
    ns.add(Insight(id="st", claim="Onze schoen is composteerbaar", source="nooch",
                   kind=ClaimKind.STANDPUNT))
    ns.add(Insight(id="b1", claim="lab A meet 90%", source="Lab A", kind=ClaimKind.BEVINDING,
                   evidence_type=EvidenceType.MEASURED))
    ns.add(Insight(id="b2", claim="lab B meet 88%", source="Lab B", kind=ClaimKind.BEVINDING,
                   evidence_type=EvidenceType.MEASURED))
    return d


def test_add_relation_store():
    d = _data()
    ns = NotesStore(os.path.join(d, "notes.json"))
    assert ns.add_relation("b1", "st", "supports") is not None
    assert ns.add_relation("b1", "st", "supports") is not None     # idempotent
    assert ns.get("b1").supports == ["st"]
    assert ns.add_relation("b1", "b1", "supports") is None          # geen zelf-relatie
    assert ns.add_relation("b1", "weg", "supports") is None         # doel bestaat niet
    assert ns.add_relation("b1", "st", "flauwekul") is None         # ongeldige relatie






