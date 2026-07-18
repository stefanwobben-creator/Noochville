"""Bron-propagatie (founder-feedback dd 2026-07-18): koppelt de mens via de bron-rij een
reference (URL of PDF) aan een statement, dan krijgen alle andere zichtbare atomen met
dezelfde genormaliseerde bron (norm_bron) die er nog GEEN hebben, dezelfde reference mee.
Expliciet > afgeleid: een bestaande (ook afwijkende) reference wordt nooit overschreven;
gearchiveerde atomen blijven ongemoeid. De banner meldt op hoeveel kaartjes hij is gezet."""
from __future__ import annotations

from nooch_village.insight import Insight
from nooch_village.kennisbank import load_atoms, norm_bron
from nooch_village.notes_store import NotesStore


def _seed(dd):
    ns = NotesStore(f"{dd}/notes.json")
    # b1..b3 delen dezelfde genormaliseerde bron (interpunctie/hoofdletters verschillen)
    ns.add(Insight(id="b1", claim="51% wil de prijs naar 150",
                   source="Survey Fixed Delivery Moments", provenance="survey"))
    ns.add(Insight(id="b2", claim="Van Westendorp optimum 120",
                   source="survey fixed-delivery moments!", provenance="survey"))
    ns.add(Insight(id="b3", claim="Kaart met eigen, afwijkende bronlink",
                   source="Survey Fixed Delivery Moments", provenance="survey",
                   reference="https://elders.nl/eigen-rapport"))
    ns.add(Insight(id="b4", claim="Gearchiveerde kaart van dezelfde survey",
                   source="Survey Fixed Delivery Moments", provenance="survey"))
    ns.archive("b4")
    ns.add(Insight(id="c1", claim="Andere bron, blijft leeg",
                   source="WUR-rapport", provenance="peer_reviewed"))
    return ns


def test_norm_bron_matcht_over_interpunctie_heen():
    assert (norm_bron("Survey Fixed Delivery Moments")
            == norm_bron("survey fixed-delivery moments!"))
    assert norm_bron("") == ""


def test_propagate_zet_alleen_lege_zusjes_nooit_overschrijven(tmp_path):
    dd = str(tmp_path)
    ns = _seed(dd)
    assert ns.set_reference("b1", "https://x.nl/rapport.pdf")
    n = ns.propagate_reference("b1")
    assert n == 1                                    # alleen b2
    alles = load_atoms(dd, include_archived=True)
    assert alles["b2"]["reference"] == "https://x.nl/rapport.pdf"
    # expliciet > afgeleid: de bestaande, afwijkende reference blijft staan
    assert alles["b3"]["reference"] == "https://elders.nl/eigen-rapport"
    # gearchiveerd en andere bronnen blijven ongemoeid
    assert not alles["b4"].get("reference")
    assert not alles["c1"].get("reference")
    # idempotent: nog een keer propageren zet niets meer bij
    assert ns.propagate_reference("b1") == 0


def test_propagate_fail_closed(tmp_path):
    dd = str(tmp_path)
    ns = _seed(dd)
    assert ns.propagate_reference("bestaat_niet") == 0
    assert ns.propagate_reference("b2") == 0         # b2 heeft (nog) geen reference
    # een lege bron-sleutel zou álle bronloze atomen matchen → geen propagatie
    ns.add(Insight(id="z1", claim="zonder bron", source="", provenance="unknown",
                   reference="https://z.nl"))
    ns.add(Insight(id="z2", claim="ook zonder bron", source="", provenance="unknown"))
    assert ns.propagate_reference("z1") == 0
    assert not load_atoms(dd)["z2"].get("reference")


def test_dispatch_kb_atoom_reference_propageert_en_telt_in_banner(tmp_path):
    from nooch_village.cockpit2 import dispatch
    dd = str(tmp_path)
    _seed(dd)
    nxt, msg = dispatch(dd, "kb_atoom_reference",
                        {"atom_id": ["b1"], "url": ["https://x.nl/studie"],
                         "next": ["/kennisbank"]}, username="guest")
    assert "🔗" in msg and "1" in msg                # banner telt de meegezette kaartjes
    atoms = load_atoms(dd)
    assert atoms["b1"]["reference"] == "https://x.nl/studie"
    assert atoms["b2"]["reference"] == "https://x.nl/studie"
    assert atoms["b3"]["reference"] == "https://elders.nl/eigen-rapport"
    # zonder zusjes zonder reference: de kale succes-boodschap, zonder telling
    _, msg2 = dispatch(dd, "kb_atoom_reference",
                       {"atom_id": ["c1"], "url": ["https://wur.nl/rapport"],
                        "next": ["/kennisbank"]}, username="guest")
    assert msg2 == "🔗 bronlink gekoppeld"
