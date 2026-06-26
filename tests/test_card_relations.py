"""Kennislaag brok 5: bewijs-links leggen tijdens review (kaartpagina).
NotesStore.add_relation + acties note_support/note_contradict + live sterkte op /card."""
from __future__ import annotations
import os
import tempfile

from nooch_village import cockpit
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


def test_support_actie_maakt_standpunt_geverifieerd():
    d = _data()
    cockpit._dispatch_action(d, "note_support", "b1", "", extra={"target": "st"})
    r = cockpit._dispatch_action(d, "note_support", "b2", "", extra={"target": "st"})
    assert r["ok"] and r["note_relation"] == "supports"
    ns = NotesStore(os.path.join(d, "notes.json"))
    assert strength(ns.get("st"), ns.all()) == Strength.GEVERIFIEERD


def test_contradict_actie_maakt_betwist():
    d = _data()
    r = cockpit._dispatch_action(d, "note_contradict", "b1", "", extra={"target": "st"})
    assert r["ok"] and r["note_relation"] == "contradicts"
    ns = NotesStore(os.path.join(d, "notes.json"))
    assert strength(ns.get("st"), ns.all()) == Strength.BETWIST


def test_card_render_heeft_kiezer_en_links():
    d = _data()
    h = cockpit.render_card(
        {"id": "st", "claim": "x", "grounds": None, "status": "unresolved",
         "grounding_count": 1, "word": "", "kind": None, "strength": "onbeslist",
         "supports": [], "contradicts": []},
        [], "tok", all_cards=[{"id": "b1", "claim": "lab A meet 90%"}])
    assert "Soort kiezen" in h and "Bewijs-links" in h
    assert "note_support" in h and "note_contradict" in h
    assert "lab A meet 90%" in h            # doelkaartje in de dropdown
