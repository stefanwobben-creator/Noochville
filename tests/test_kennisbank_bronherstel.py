"""Bronlink-herstel (founder, 19 jul): de link of PDF die bij het aanmaken van signals
is GEBRUIKT hoort de reference te zijn — niet een door de LLM overgetypte DOI die kan
doodlopen. Drie borgingen: (1) bron_reference kiest de echte bron bij intake, (2) bij
signaal-promotie wint de artikellink van de atomiser-reference, (3) het herstel-script
zet de link terug op bestaande kaartjes via radar.promoted_atom_id — idempotent, zonder
ooit een bestaande werkende link te overschrijven."""
from __future__ import annotations

import types

from nooch_village.insight import Insight
from nooch_village.kennisbank_bronherstel import herstel
from nooch_village.kennisbank_sources import bron_reference
from nooch_village.kennisbank_staging import StagingStore
from nooch_village.notes_store import NotesStore
from nooch_village.radar_store import RadarStore


def test_bron_reference_kiest_de_gebruikte_bron():
    # geplakte URL wint (ook boven een meegegeven pdf-pad)
    assert bron_reference("https://nature.com/artikel?utm=x", "/kbref/a.pdf") \
        == "https://nature.com/artikel?utm=x"
    # PDF-upload: het bewaarde pad
    assert bron_reference("", "/kbref/ab12_rapport.pdf") == "/kbref/ab12_rapport.pdf"
    # geplakte tekst: geen override — de atomiser-reference (bijv. een DOI) blijft
    assert bron_reference("gewoon een notitie over zolen", "") is None
    assert bron_reference("", "") is None


def test_stage_signal_artikellink_wint_van_llm_doi(tmp_path, monkeypatch):
    from nooch_village import radar_promote
    dd = str(tmp_path)
    st = types.SimpleNamespace(radar=RadarStore(f"{dd}/radar.json"),
                               staging=StagingStore(f"{dd}/kennisbank_staging.json"),
                               notes=NotesStore(f"{dd}/notes.json"))
    rid = st.radar.add(role="scout", feed="f", kind="nieuws",
                       content="plastic wordt grondstof met zeewater",
                       source="Nature", link="https://nature.com/echte-artikel")
    st.radar.set_status(rid, "goedgekeurd")
    # de gelezen bron levert atomen met een LLM-overgetypte DOI als reference
    monkeypatch.setattr(radar_promote, "_atomen_uit_bron", lambda it: [
        {"content": "claim uit de bron", "subject": "materiaal",
         "reference": "DOI:10.1038/hallucinatie", "provenance": "peer_reviewed"}])
    bid, _ = radar_promote.stage_signal(st, rid)
    atoms = st.staging.get(bid)["atoms"]
    assert atoms[0]["reference"] == "https://nature.com/echte-artikel"
    # zonder link op het signaal blijft de atomiser-reference gewoon staan
    rid2 = st.radar.add(role="scout", feed="f", kind="nieuws",
                        content="tweede claim zonder link", source="Blad", link="")
    st.radar.set_status(rid2, "goedgekeurd")
    bid2, _ = radar_promote.stage_signal(st, rid2)
    atoms2 = st.staging.get(bid2)["atoms"]
    assert any(a.get("reference") == "DOI:10.1038/hallucinatie" for a in atoms2)


def test_herstel_zet_link_terug_idempotent(tmp_path):
    dd = str(tmp_path)
    radar = RadarStore(f"{dd}/radar.json")
    notes = NotesStore(f"{dd}/notes.json")
    notes.add(Insight(id="a1", claim="dode DOI", source="Nature",
                      reference="DOI:10.1038/dood", provenance="peer_reviewed"))
    notes.add(Insight(id="a2", claim="al een echte link", source="WUR",
                      reference="https://wur.nl/rapport", provenance="peer_reviewed"))
    notes.add(Insight(id="a3", claim="lege reference", source="Blad", provenance="media"))
    for aid, link in (("a1", "https://nature.com/echt"),
                      ("a2", "https://elders.nl/x"), ("a3", "https://blad.nl/stuk")):
        rid = radar.add(role="scout", feed="f", kind="nieuws",
                        content=f"signaal {aid}", link=link)
        radar.mark_promoted(rid, aid)
    # dry-run: rapporteert a1 (DOI) en a3 (leeg), raakt a2 (werkende link) nooit aan
    droog = herstel(dd, apply=False)
    assert {r["atom_id"] for r in droog} == {"a1", "a3"}
    assert NotesStore(f"{dd}/notes.json").get("a1").reference \
        == "DOI:10.1038/dood"                                   # dry-run schrijft niets
    # apply: de echte artikellink staat erop, de oude staat in het rapport
    echt = herstel(dd, apply=True)
    assert {(r["atom_id"], r["oud"]) for r in echt} \
        == {("a1", "DOI:10.1038/dood"), ("a3", None)}
    vers = NotesStore(f"{dd}/notes.json")                       # vers van schijf lezen
    assert vers.get("a1").reference == "https://nature.com/echt"
    assert vers.get("a3").reference == "https://blad.nl/stuk"
    assert vers.get("a2").reference == "https://wur.nl/rapport"
    # idempotent: tweede run heeft niets meer te doen
    assert herstel(dd, apply=True) == []
