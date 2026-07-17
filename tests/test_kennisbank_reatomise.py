"""Reatomise-fix: atomiser-versionering (taak 1) + mens-veilige migratie (taak 2).
Alles met een fake reason_fn, geen netwerk."""
from __future__ import annotations

import json

import pytest

from nooch_village.insight import Insight
from nooch_village.kennisbank import KennisbankStore, load_atoms
from nooch_village.kennisbank_intake import (ATOMISER_VERSION, IntakeLedger, intake,
                                             stable_id)
from nooch_village.kennisbank_reatomise import (in_use_ids, reatomise_document,
                                                _kandidaten)
from nooch_village.notes_store import NotesStore


def _fake(atoms):
    return lambda prompt, **kw: json.dumps(atoms)


_V2 = [{"content": "Schone samengestelde claim uit het document.", "subject": "leer",
        "provenance": "peer_reviewed", "source": "IDS 2021", "reference": "DOI x",
        "body": "1. stap\n2. stap", "flags": [], "link_hints": []}]


# ── taak 1: versie in de ledger ──────────────────────────────────────────────

@pytest.mark.smoke
def test_ledger_versie_bewust_van_reatomise(tmp_path):
    dd = str(tmp_path)
    nieuw, _ = intake("ruwe tekst", "IDS 2021", dd, reason_fn=_fake(_V2))
    assert len(nieuw) == 1
    # zelfde versie opnieuw → idempotent, geen LLM
    def _boem(*a, **k):
        raise AssertionError("mag niet opnieuw draaien binnen dezelfde versie")
    assert intake("ruwe tekst", "IDS 2021", dd, reason_fn=_boem) == ([], 1)
    # het atoom draagt de huidige versie
    assert load_atoms(dd)[nieuw[0]]["atomiser_version"] == ATOMISER_VERSION


def test_oudere_versie_telt_niet_als_klaar(tmp_path):
    dd = str(tmp_path)
    ledger = IntakeLedger(f"{dd}/kennisbank_intake.json")
    # simuleer een v1-entry
    ledger._items[IntakeLedger.raw_key("oude input", "bron")] = {
        "atom_ids": ["oud1"], "source_hint": "bron", "atomiser_version": 1,
        "raw": "oude input", "at": "2026-07-01"}
    ledger._save()
    assert IntakeLedger(f"{dd}/kennisbank_intake.json").seen("oude input", "bron") is None
    assert len(IntakeLedger(f"{dd}/kennisbank_intake.json").stale()) == 1
    # force draait er sowieso overheen en herschrijft de entry op de huidige versie
    intake("oude input", "bron", dd, reason_fn=_fake(_V2), force=True)
    assert IntakeLedger(f"{dd}/kennisbank_intake.json").seen("oude input", "bron") is not None


# ── taak 2: migratie ─────────────────────────────────────────────────────────

def _oud_atoom(notes, aid, source="IDS 2021", **kw):
    notes.add(Insight(id=aid, claim=f"oud {aid}", source=source,
                      provenance="advocacy", tags=["leer"],
                      atomiser_version=None, **kw))     # None = pre-versionering


def test_in_use_bescherming_en_supersede(tmp_path):
    dd = str(tmp_path)
    notes = NotesStore(f"{dd}/notes.json")
    for aid in ("a1", "a2", "a3"):
        _oud_atoom(notes, aid)
    # a2 is in gebruik: gelinkt aan een inzicht
    kb = KennisbankStore(f"{dd}/kennisbank.json")
    iid = kb.add("een inzicht", subject="leer")
    kb.link(iid, "a2", "support")

    assert "a2" in in_use_ids(dd)
    assert set(_kandidaten(dd, "IDS 2021")) == {"a1", "a2", "a3"}

    # dry-run: geen LLM, geen schrijf
    dry = reatomise_document(dd, ["ruwe brontekst"], "IDS 2021", apply=False,
                             reason_fn=_fake(_V2))
    assert dry["oud"] == 3 and dry["ongebruikt"] == 2 and dry["geflagd"] == 1
    assert dry["geflagd_ids"] == ["a2"] and dry["nieuw"] == []
    assert load_atoms(dd).get("a1") is not None            # nog niets gebeurd

    # apply: ongebruikte a1/a3 → gearchiveerd + superseded_by; a2 blijft, geflagd
    rap = reatomise_document(dd, ["ruwe brontekst"], "IDS 2021", apply=True,
                             reason_fn=_fake(_V2))
    assert rap["nieuw"]
    actief = load_atoms(dd)
    assert "a1" not in actief and "a3" not in actief       # gearchiveerd
    assert "a2" in actief                                   # menselijk werk beschermd
    alles = load_atoms(dd, include_archived=True)
    assert alles["a1"]["superseded_by"] == rap["nieuw"]     # spoor oud → nieuw
    assert alles["a1"]["archived"] is True
    nieuw_id = rap["nieuw"][0]
    assert actief[nieuw_id]["atomiser_version"] == ATOMISER_VERSION
    assert (actief[nieuw_id].get("body") or "")             # samengestelde kaart


def test_migratie_idempotent(tmp_path):
    dd = str(tmp_path)
    notes = NotesStore(f"{dd}/notes.json")
    _oud_atoom(notes, "a1")
    reatomise_document(dd, ["brontekst"], "IDS 2021", apply=True, reason_fn=_fake(_V2))
    # her-run: a1 is al superseded → geen kandidaten meer, niets te doen
    assert _kandidaten(dd, "IDS 2021") == {}
    rap2 = reatomise_document(dd, ["brontekst"], "IDS 2021", apply=True, reason_fn=_fake(_V2))
    assert rap2["oud"] == 0
    assert any("niets te doen" in r for r in rap2["regels"])


def test_migratie_fail_closed_archiveert_niet_zonder_nieuw(tmp_path):
    dd = str(tmp_path)
    notes = NotesStore(f"{dd}/notes.json")
    _oud_atoom(notes, "a1")
    rap = reatomise_document(dd, ["brontekst"], "IDS 2021", apply=True,
                             reason_fn=lambda *a, **k: None)   # ladder faalt
    assert rap["nieuw"] == []
    assert load_atoms(dd).get("a1") is not None                # niet gearchiveerd
