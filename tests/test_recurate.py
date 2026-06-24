"""Chunk 4: her-curatie van bestaande kaartjes door de curator.

Een Nederlands, niet-atomair kaartje gaat opnieuw door de curate-engine en komt
Engels + atomair terug; het origineel verdwijnt. Fail-closed: levert de curator
niets op, dan blijft het origineel staan (geen kennisverlies).

LLM gemockt via reason_fn; geen netwerk."""
from __future__ import annotations
import json
import pytest

from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight, GroundingStatus
from nooch_village.curate_migrate import recurate_card, recurate_cards


def _notes(tmp_path):
    ns = NotesStore(str(tmp_path / "notes.json"))
    ns.add(Insight(
        id="vegan_betekenis_correctie",
        claim="Vegan betekent zonder dierlijke materialen, niet zonder plastic. "
              "Een typische vegan sneaker bevat PU-leer en EVA-schuim.",
        source="survey", status=GroundingStatus.SUPPORTED, grounds="bron"))
    return ns


def _two_english_cards(_prompt):
    return json.dumps([
        {"id": "vegan_means_no_animal_materials",
         "claim": "Vegan means free of animal materials, not free of plastic.",
         "grounds": "Definition of veganism applied to footwear materials.",
         "evidence_type": "reported", "tags": ["vegan"], "links_to": []},
        {"id": "typical_vegan_sneaker_uses_pu_and_eva",
         "claim": "A typical vegan sneaker uses PU leather and EVA foam.",
         "grounds": "Common bill of materials for mass-market vegan sneakers.",
         "evidence_type": "reported", "tags": ["vegan", "materials"], "links_to": []},
    ])


def test_recurate_vervangt_nederlands_door_engels_atomair(tmp_path):
    ns = _notes(tmp_path)
    res = recurate_card(ns, "vegan_betekenis_correctie", reason_fn=_two_english_cards)

    assert res["replaced"] is True
    assert set(res["new_ids"]) == {
        "vegan_means_no_animal_materials", "typical_vegan_sneaker_uses_pu_and_eva"}
    # Origineel weg, twee Engelse atomaire kaartjes erin
    assert ns.get("vegan_betekenis_correctie") is None
    ids = {n.id for n in ns.all()}
    assert ids == set(res["new_ids"])
    # En het is echt opnieuw geschreven (persistente store: herladen)
    reloaded = NotesStore(str(tmp_path / "notes.json"))
    assert reloaded.get("vegan_means_no_animal_materials") is not None


def test_recurate_fail_closed_behoudt_origineel(tmp_path):
    ns = _notes(tmp_path)
    # Curator geeft niets bruikbaars (LLM weg)
    res = recurate_card(ns, "vegan_betekenis_correctie", reason_fn=lambda _p: None)

    assert res["replaced"] is False
    assert ns.get("vegan_betekenis_correctie") is not None     # origineel behouden
    assert len(ns.all()) == 1


def test_recurate_onbekend_kaartje(tmp_path):
    ns = _notes(tmp_path)
    res = recurate_card(ns, "bestaat_niet", reason_fn=_two_english_cards)
    assert res["replaced"] is False
    assert "niet gevonden" in res["reason"]


def test_recurate_cards_meerdere(tmp_path):
    ns = _notes(tmp_path)
    ns.add(Insight(id="tweede_nl", claim="Nederlandse claim twee.", source="survey",
                   status=GroundingStatus.SUPPORTED, grounds="bron"))
    one = lambda _p: json.dumps([{"id": "english_card_x", "claim": "An English claim.",
                                  "grounds": "Reasoning.", "tags": [], "links_to": []}])
    res = recurate_cards(ns, ["vegan_betekenis_correctie", "tweede_nl"], reason_fn=one)
    assert all(r["replaced"] for r in res)
    # english_card_x wordt door de eerste toegevoegd; de tweede dedupt erop (skip)
    assert ns.get("english_card_x") is not None
