"""Verrijkingsronde: bestaande kaartjes alsnog een herkomst-verantwoording (LLM, mens-geïnitieerd).

Dekt: dry-run telt zonder LLM of schrijf; de echte run vult provenance_note (en provenance
alleen als die 'unknown' was) via een geïnjecteerde reason-functie; bestaande classificaties
worden nooit overschreven; het grootboek onthoudt ook 'niets gevonden' zodat herdraaien geen
dubbele LLM-calls kost; LLM-uitval is fail-closed en kan later alsnog.
"""
from __future__ import annotations

import json

from nooch_village.herkomst_verrijking import (VerrijkLedger, build_verrijk_prompt,
                                               parse_verrijk, verrijk_herkomst)
from nooch_village.insight import Insight
from nooch_village.notes_store import NotesStore


def _notes(tmp_path) -> tuple[str, NotesStore]:
    dd = str(tmp_path)
    notes = NotesStore(f"{dd}/notes.json")
    notes.add(Insight(id="a1", claim="Externe survey onder 1.200 consumenten toont X",
                      source="Bureau Y", provenance="survey"))
    notes.add(Insight(id="a2", claim="Claim zonder herkomst-aanknopingspunt",
                      source="onbekend"))
    notes.add(Insight(id="a3", claim="Al voorzien", source="z",
                      provenance="media", provenance_note="bestond al"))
    return dd, notes


def test_dry_run_telt_zonder_schrijf(tmp_path):
    dd, notes = _notes(tmp_path)
    boem = lambda prompt: (_ for _ in ()).throw(AssertionError("dry-run mag geen LLM aanroepen"))
    t = verrijk_herkomst(dd, reason_fn=boem, dry_run=True)
    assert t["kandidaten"] == 2                       # a3 heeft al een note
    assert NotesStore(f"{dd}/notes.json").get("a1").provenance_note is None


def test_run_vult_note_en_unknown_provenance(tmp_path):
    dd, notes = _notes(tmp_path)

    def fake(prompt):
        return json.dumps([
            {"id": "a1", "provenance": "survey", "herkomst": "extern, N=1.200"},
            {"id": "a2", "provenance": "media", "herkomst": ""},
        ])

    t = verrijk_herkomst(dd, reason_fn=fake)
    assert t["gevuld"] == 1 and t["prov_gezet"] == 1 and t["leeg"] == 0
    vers = NotesStore(f"{dd}/notes.json")
    assert vers.get("a1").provenance_note == "extern, N=1.200"
    assert vers.get("a1").provenance == "survey"      # was al gezet, niet overschreven
    assert vers.get("a2").provenance == "media"       # unknown → ingevuld
    assert vers.get("a2").provenance_note is None
    # a2 kreeg wél provenance maar geen note → grootboek 'gevuld'; a3 nooit geprobeerd
    ledger = VerrijkLedger(f"{dd}/herkomst_verrijking.json")
    assert ledger.seen("a1") and ledger.seen("a2") and not ledger.seen("a3")


def test_leeg_wordt_onthouden_geen_dubbele_calls(tmp_path):
    dd, _ = _notes(tmp_path)
    calls = []

    def fake(prompt):
        calls.append(prompt)
        return json.dumps([{"id": "a1", "provenance": "survey", "herkomst": ""},
                           {"id": "a2", "provenance": "", "herkomst": ""}])

    t1 = verrijk_herkomst(dd, reason_fn=fake)
    assert t1["leeg"] == 2 and len(calls) == 1
    t2 = verrijk_herkomst(dd, reason_fn=fake)         # herdraai: alles in het grootboek
    assert t2["kandidaten"] == 0 and len(calls) == 1  # geen tweede LLM-call


def test_llm_uitval_failclosed_en_later_alsnog(tmp_path):
    dd, _ = _notes(tmp_path)
    t = verrijk_herkomst(dd, reason_fn=lambda p: None)
    assert t["mislukt"] == 2 and t["gevuld"] == 0
    assert not VerrijkLedger(f"{dd}/herkomst_verrijking.json").seen("a1")   # kan later alsnog
    ok = verrijk_herkomst(dd, reason_fn=lambda p: json.dumps(
        [{"id": "a1", "provenance": "survey", "herkomst": "extern, N=1.200"},
         {"id": "a2", "provenance": "", "herkomst": ""}]))
    assert ok["gevuld"] == 1


def test_prompt_en_parser_randen(tmp_path):
    p = build_verrijk_prompt([{"id": "a1", "claim": "X", "body": None, "source": "s",
                               "reference": None, "provenance": "unknown"}])
    assert "a1" in p and "nooit gokken" in p
    assert parse_verrijk(None) == {}
    assert parse_verrijk("geen json") == {}
    uit = parse_verrijk('```json\n[{"id": "a1", "provenance": "onzin", "herkomst": "x"}]\n```')
    assert uit["a1"]["provenance"] is None and uit["a1"]["herkomst"] == "x"


def test_store_verrijk_overschrijft_nooit(tmp_path):
    dd, notes = _notes(tmp_path)
    assert notes.verrijk_herkomst("a3", note="nieuwe poging", provenance="survey") is False
    a3 = NotesStore(f"{dd}/notes.json").get("a3")
    assert a3.provenance_note == "bestond al" and a3.provenance == "media"
