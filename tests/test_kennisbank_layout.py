"""Kennisbank layout PR-1: auto-detect + tabeladapters + staging-ronde (even nakijken).
Alles zonder netwerk; de LLM-atomisatie via een fake reason_fn."""
from __future__ import annotations

import io
import json

import pytest

from nooch_village.kennisbank import load_atoms
from nooch_village.kennisbank_sources import (detect_and_extract, van_csv, van_excel,
                                              _tabel_chunks)
from nooch_village.kennisbank_staging import StagingStore, commit_batch


# ── auto-detectie ────────────────────────────────────────────────────────────

def test_detect_herkent_type_verklaarbaar():
    assert detect_and_extract(text="gewone notitie")["kind"] == "tekst"
    assert detect_and_extract(text="https://voorbeeld.nl/x")["kind"] == "website"
    sheet = detect_and_extract(text="https://docs.google.com/spreadsheets/d/AB_1/edit#gid=3")
    assert sheet["kind"] == "Google Sheet" and sheet["tabular"] is True
    slides = detect_and_extract(text="https://docs.google.com/presentation/d/X/edit")
    assert slides["chunks"] is None and "Slides" in slides["error"]
    # bestand op extensie
    csv = detect_and_extract(filename="survey.csv", data=b"a,b\n1,2\n3,4\n")
    assert csv["kind"] == "CSV" and csv["tabular"] is True and csv["chunks"]
    leeg = detect_and_extract(text="")
    assert leeg["chunks"] is None


def test_tabel_niet_blind_proza():
    chunks = _tabel_chunks(["segment", "betaalbereidheid"],
                           [["Idealist", 120], ["Twijfelaar", 100], ["", ""]], "survey")
    assert len(chunks) == 1
    tekst = chunks[0][0]
    assert "Kolommen: segment, betaalbereidheid" in tekst
    assert "segment: Idealist | betaalbereidheid: 120" in tekst
    assert "Twijfelaar" in tekst                      # lege rij overgeslagen, geen lege regel
    # de tabeldata-vlag bereikt de atomiser-prompt
    from nooch_village.kennisbank_intake import build_intake_prompt
    assert "TABELDATA" in build_intake_prompt("x", tabular=True)
    assert "TABELDATA" not in build_intake_prompt("x", tabular=False)


def test_van_csv_en_excel(tmp_path):
    c = van_csv(b"naam,waarde\nx,1\ny,2\n", "d.csv")
    assert c and "naam: x | waarde: 1" in c[0][0]
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["kol", "getal"]); ws.append(["a", 3]); ws.append(["b", 4])
    buf = io.BytesIO(); wb.save(buf)
    e = van_excel(buf.getvalue(), "boek.xlsx")
    assert e and "kol: a | getal: 3" in e[0][0]


# ── staging-ronde ────────────────────────────────────────────────────────────

_ATOMS = [
    {"content": "Feit A over leer.", "subject": "leer", "provenance": "media",
     "source": "Rapport X", "flags": []},
    {"content": "Feit B over leer.", "subject": "leer", "provenance": "media",
     "source": "Rapport X", "flags": ["verificatie_vereist"]},
    {"content": "Rommel om weg te gooien.", "subject": "", "provenance": "unknown",
     "source": "Rapport X", "flags": []},
]


@pytest.mark.smoke
def test_staging_bewerken_samenvoegen_weggooien_committen(tmp_path):
    dd = str(tmp_path)
    store = StagingStore(f"{dd}/kennisbank_staging.json")
    bid = store.create("PDF", "Rapport X", _ATOMS, by="test")
    b = store.get(bid)
    assert len(b["atoms"]) == 3

    # niets staat in de bibliotheek vóór commit
    assert load_atoms(dd) == {}

    # bewerken: onbekend subject wordt geweigerd, geldig subject blijft
    sid0 = b["atoms"][0]["sid"]
    assert store.edit_atom(bid, sid0, content="Feit A, aangescherpt.", subject="outsole")
    assert store.get(bid)["atoms"][0]["content"] == "Feit A, aangescherpt."
    assert store.get(bid)["atoms"][0]["subject"] == "outsole"

    # weggooien van de rommel
    rommel = next(a for a in store.get(bid)["atoms"] if "Rommel" in a["content"])
    assert store.remove_atom(bid, rommel["sid"])
    assert len(store.get(bid)["atoms"]) == 2

    # samenvoegen van de twee resterende
    sids = [a["sid"] for a in store.get(bid)["atoms"]]
    assert store.merge_atoms(bid, sids, "Samengevat feit over leer")
    atoms = store.get(bid)["atoms"]
    assert len(atoms) == 1 and atoms[0]["content"] == "Samengevat feit over leer"
    assert "Feit A" in atoms[0]["body"] and "Feit B" in atoms[0]["body"]

    # commit → append-only in de bibliotheek, batch opgeruimd
    nieuw, dubbel = commit_batch(store, bid, dd)
    assert nieuw == 1 and dubbel == 0
    assert store.get(bid) is None
    bib = load_atoms(dd)
    assert len(bib) == 1
    kaart = next(iter(bib.values()))
    assert kaart["claim"] == "Samengevat feit over leer" and kaart["body"]
    assert kaart["atomiser_version"]                       # gaat als volwaardig atoom mee


def test_commit_idempotent(tmp_path):
    dd = str(tmp_path)
    store = StagingStore(f"{dd}/kennisbank_staging.json")
    b1 = store.create("tekst", "Bron Y", _ATOMS[:2], by="t")
    commit_batch(store, b1, dd)
    # dezelfde content+bron nog eens door staging → commit voegt niets dubbels toe
    b2 = store.create("tekst", "Bron Y", _ATOMS[:2], by="t")
    nieuw, dubbel = commit_batch(store, b2, dd)
    assert nieuw == 0 and dubbel == 2


def test_merge_vereist_twee_en_kop(tmp_path):
    store = StagingStore(str(tmp_path / "s.json"))
    bid = store.create("tekst", "B", _ATOMS, by="t")
    sids = [a["sid"] for a in store.get(bid)["atoms"]]
    assert store.merge_atoms(bid, sids[:1], "kop") is False       # <2
    assert store.merge_atoms(bid, sids[:2], "") is False          # geen kop


# ── PR-2: live search + koppel-brug + edit/related ───────────────────────────

def _st(dd):
    import types
    from nooch_village.kennisbank import KennisbankStore
    from nooch_village.kennisbank_spel import SpelStore
    from nooch_village.kennisbank_staging import StagingStore
    return types.SimpleNamespace(
        dd=dd, kennisbank=KennisbankStore(f"{dd}/kennisbank.json"),
        spel=SpelStore(f"{dd}/kennisbank_spel.json"),
        staging=StagingStore(f"{dd}/kennisbank_staging.json"),
        notes=__import__("nooch_village.notes_store", fromlist=["NotesStore"]).NotesStore(f"{dd}/notes.json"))


def _seed_atoms(dd):
    from nooch_village.insight import Insight
    from nooch_village.notes_store import NotesStore
    ns = NotesStore(f"{dd}/notes.json")
    ns.add(Insight(id="p1", claim="51% wil de prijs naar 150", source="Survey Fixed Delivery Moments",
                   provenance="survey", tags=["prijs"]))
    ns.add(Insight(id="p2", claim="Van Westendorp optimum 120", source="Survey Fixed Delivery Moments",
                   provenance="survey", tags=["prijs"]))
    ns.add(Insight(id="w1", claim="natuurrubber zool breekt traag af", source="WUR-rapport",
                   provenance="peer_reviewed", tags=["outsole"]))
    return ns


def test_search_op_inhoud_en_bron(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path); _seed_atoms(dd); st = _st(dd)
    op_inhoud = render_kennisbank_search(st, "westendorp", "", "", csrf_token="t")
    assert "Van Westendorp" in op_inhoud and "51% wil" not in op_inhoud
    # zoeken op BRON vindt alle kaarten van die survey
    op_bron = render_kennisbank_search(st, "fixed delivery", "", "", csrf_token="t")
    assert "51% wil" in op_bron and "Van Westendorp" in op_bron and "natuurrubber" not in op_bron
    # bronlabel is klikbaar
    assert "kn-srclink" in op_bron and "Survey Fixed Delivery Moments" in op_bron


def test_brug_markeert_suggesties_en_koppelknoppen(tmp_path):
    from nooch_village.views.kennisbank import render_kennisbank_search
    dd = str(tmp_path); _seed_atoms(dd); st = _st(dd)
    iid = st.kennisbank.add("Prijs blokkeert de kern-doelgroep", subject="prijs")
    frag = render_kennisbank_search(st, "", "", iid, csrf_token="t")
    # met een actief inzicht verschijnen de brug-knoppen + een suggestie-markering
    assert "+ steunt" in frag and "+ tegen" in frag
    assert "past mogelijk" in frag                     # prijs-kaart als steun-suggestie
    assert f"value='{iid}'" in frag                     # kb_link wijst naar dit inzicht


def test_edit_history_en_related_via_dispatch(tmp_path):
    from nooch_village.cockpit2 import dispatch, _Stores
    from nooch_village.kennisbank import load_atoms
    dd = str(tmp_path); _seed_atoms(dd)
    # bewerken bewaart de vorige versie
    dispatch(dd, "kb_atoom_edit", {"atom_id": ["p1"], "claim": ["51% wil de prijs naar €150 (gecorrigeerd)"],
                                   "next": ["/kennisbank"]}, username="guest")
    a = load_atoms(dd)["p1"]
    assert a["claim"].endswith("(gecorrigeerd)") and a["edit_history"][0]["claim"] == "51% wil de prijs naar 150"
    # gerelateerd feit → nieuw gelinkt atoom met eigen bron
    nxt, msg = dispatch(dd, "kb_atoom_related", {"atom_id": ["p1"],
                        "content": ["Concurrent zit op €140"], "source": ["marktonderzoek"],
                        "next": ["/kennisbank"]}, username="guest")
    atoms = load_atoms(dd)
    rel = [a for a in atoms.values() if "Concurrent" in a["claim"]]
    assert len(rel) == 1 and rel[0]["links_to"] == ["p1"] and rel[0]["source"] == "marktonderzoek"
