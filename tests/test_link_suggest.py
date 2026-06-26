"""Kennislaag brok 6: Librarian stelt bewijs-links voor; mens bevestigt/verwerpt.
Suggester (relevantie, alleen bevinding→standpunt/signaal, publiceer-risico eerst) + decided-store."""
from __future__ import annotations
import os
import tempfile

from nooch_village import cockpit
from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight, ClaimKind, EvidenceType
from nooch_village.link_suggest import suggest_links, LinkProposals, open_proposals
from nooch_village.knowledge import strength, Strength


def _notes():
    return [
        Insight(id="st", claim="Onze schoen is volledig composteerbaar binnen 90 dagen",
                source="nooch", kind=ClaimKind.STANDPUNT),
        Insight(id="b1", claim="Labtest meet composteerbaar materiaal binnen 88 dagen",
                source="Lab A", kind=ClaimKind.BEVINDING, evidence_type=EvidenceType.MEASURED),
        Insight(id="b2", claim="Iets totaal anders over marketing en kleur", source="x",
                kind=ClaimKind.BEVINDING),
    ]


def test_suggester_matcht_relevante_bevinding():
    sg = suggest_links(_notes())
    pairs = {(s["from_id"], s["to_id"]) for s in sg}
    assert ("b1", "st") in pairs          # deelt 'composteerbaar'
    assert ("b2", "st") not in pairs      # niet relevant genoeg
    assert all(s["relation"] == "supports" for s in sg)


def test_suggester_slaat_bestaande_link_over():
    notes = _notes()
    notes[1].supports = ["st"]            # b1 steunt st al
    assert suggest_links(notes) == []


def test_decided_store_dedup():
    d = tempfile.mkdtemp()
    lp = LinkProposals(os.path.join(d, "lp.json"))
    assert lp.is_decided("b1", "st") is False
    lp.reject("b1", "st")
    assert lp.status("b1", "st") == "rejected"
    # herladen blijft beslist
    assert LinkProposals(os.path.join(d, "lp.json")).is_decided("b1", "st") is True


def test_open_proposals_filtert_beslisten():
    d = tempfile.mkdtemp()
    lp = LinkProposals(os.path.join(d, "lp.json"))
    notes = _notes()
    assert open_proposals(notes, lp)                       # er is er één
    lp.reject("b1", "st")
    assert open_proposals(notes, lp) == []                 # weg na verwerping


def test_confirm_actie_legt_link_en_verhoogt_sterkte():
    d = tempfile.mkdtemp()
    ns = NotesStore(os.path.join(d, "notes.json"))
    for n in _notes():
        ns.add(n)
    r = cockpit._dispatch_action(d, "link_confirm", "", "", extra={"from_id": "b1", "target": "st"})
    assert r["ok"] and r["link_proposal"] == "confirmed"
    ns2 = NotesStore(os.path.join(d, "notes.json"))
    assert ns2.get("b1").supports == ["st"]
    assert strength(ns2.get("st"), ns2.all()) == Strength.ONDERSTEUND
    # niet opnieuw voorgesteld
    lp = LinkProposals(os.path.join(d, "link_proposals.json"))
    assert open_proposals(ns2.all(), lp) == []


def test_reject_actie_onthoudt():
    d = tempfile.mkdtemp()
    ns = NotesStore(os.path.join(d, "notes.json"))
    for n in _notes():
        ns.add(n)
    cockpit._dispatch_action(d, "link_reject", "", "", extra={"from_id": "b1", "target": "st"})
    lp = LinkProposals(os.path.join(d, "link_proposals.json"))
    assert lp.status("b1", "st") == "rejected"
    assert NotesStore(os.path.join(d, "notes.json")).get("b1").supports == []  # geen link gelegd
