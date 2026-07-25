"""Seed/overlay-splitsing van de claims-database: de getrackte seed blijft read-only, runtime-
curatie (toevoegen/intrekken/status) landt in data/claims_runtime.json. Dekt de exacte delta-merge,
de conflictregel (aanwezigheid wint), de test-isolatie van het overlay-pad, de migratie en de
retract-UI via de dispatch."""
from __future__ import annotations

import json
import os
import shutil

from nooch_village import claims_db, claims_migrate, cockpit2


def _kopie_seed(tmp_path):
    """Een verse kopie van de seed op een tmp-pad + een eigen data_dir voor de overlay."""
    pad = str(tmp_path / "claims_database.json")
    shutil.copy(claims_db.DB_PATH, pad)
    dd = str(tmp_path / "data")
    os.makedirs(dd, exist_ok=True)
    return pad, dd


# ── 1. De overlay-kern ────────────────────────────────────────────────────────────────────────

def test_geen_overlay_is_identiek_aan_seed(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    seed = claims_db.load_seed()
    eff = claims_db.load(data_dir=dd)
    assert [t["patroon"] for t in eff["termen"]] == [t["patroon"] for t in seed["termen"]]
    assert not os.path.exists(os.path.join(dd, "claims_runtime.json"))   # lezen schrijft niets


def test_add_landt_in_overlay_niet_in_seed(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    voor = len(claims_db.load_seed()["termen"])
    nieuw, versie = claims_db.overlay_add_term(dd, term="Xclaim", patroon=r"xclaim",
                                               stoplicht="red", categorie="Test")
    assert nieuw["term"] == "Xclaim" and versie
    eff = claims_db.load(data_dir=dd)
    assert any(t["patroon"] == "xclaim" for t in eff["termen"]) and len(eff["termen"]) == voor + 1
    assert os.path.exists(os.path.join(dd, "claims_runtime.json"))       # onder data_dir (isolatie)
    assert len(claims_db.load_seed()["termen"]) == voor                  # seed ongemoeid


def test_retract_runtime_term_verdwijnt_schoon(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db.overlay_add_term(dd, term="Weg", patroon=r"wegterm", stoplicht="orange", categorie="Test")
    claims_db.overlay_retract(dd, "wegterm")
    eff = claims_db.load(data_dir=dd)
    assert not any(t["patroon"] == "wegterm" for t in eff["termen"])
    assert not eff.get("_conflicten")                                    # geen conflict: was runtime


def test_retract_seed_term_blijft_en_meldt_conflict(tmp_path):
    """De conflictregel: een in-git seed-term die runtime wordt ingetrokken blijft staan
    (aanwezigheid wint) en het conflict wordt zichtbaar in `_conflicten` gezet."""
    _pad, dd = _kopie_seed(tmp_path)
    seed_patroon = claims_db.load_seed()["termen"][0]["patroon"]
    claims_db.overlay_retract(dd, seed_patroon)
    eff = claims_db.load(data_dir=dd)
    assert any(t["patroon"] == seed_patroon for t in eff["termen"])      # blijft staan
    assert eff.get("_conflicten")                                        # conflict zichtbaar


def test_add_heft_eerdere_retractie_op(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db.overlay_retract(dd, "herstelterm")
    claims_db.overlay_add_term(dd, term="Herstel", patroon=r"herstelterm", stoplicht="green", categorie="Test")
    eff = claims_db.load(data_dir=dd)
    assert any(t["patroon"] == "herstelterm" for t in eff["termen"])
    ov = json.load(open(os.path.join(dd, "claims_runtime.json"), encoding="utf-8"))
    assert "herstelterm" not in ov["ingetrokken"]


def test_status_override_via_overlay(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    seed = claims_db.load_seed()
    item = seed["werklijst"][0]
    doel = next(s for s in claims_db.werk_statussen(seed) if s != item["status"])
    claims_db.overlay_set_status(dd, item["nr"], doel)
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == item["nr"])["status"] == doel
    assert claims_db.load_seed()["werklijst"][0]["status"] == item["status"]    # seed ongemoeid


def test_status_onbekend_wordt_geweigerd_maar_machine_mag_auto(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    nr = claims_db.load_seed()["werklijst"][0]["nr"]
    try:
        claims_db.overlay_set_status(dd, nr, "verzonnenstatus")
        assert False, "onbekende status moet weigeren"
    except ValueError:
        pass
    # de auto-scan mag de AUTO_STATUSSEN wél zetten
    claims_db.overlay_set_status(dd, nr, claims_db.AUTO_REGRESSIE, machine=True)
    eff = claims_db.load(data_dir=dd)
    assert next(i for i in eff["werklijst"] if i["nr"] == nr)["status"] == claims_db.AUTO_REGRESSIE


def test_check_tekst_pikt_runtime_term_op(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db.overlay_add_term(dd, term="Runtimeclaim", patroon=r"runtimeclaim",
                               stoplicht="red", categorie="Test")
    met = claims_db.check_tekst("hier staat een runtimeclaim", data_dir=dd)
    assert any(b["term"] == "Runtimeclaim" for b in met["bevindingen"])
    zonder = claims_db.check_tekst("hier staat een runtimeclaim")       # kale seed
    assert not any(b["term"] == "Runtimeclaim" for b in zonder["bevindingen"])


def test_kapotte_overlay_faalt_luid(tmp_path):
    _pad, dd = _kopie_seed(tmp_path)
    with open(os.path.join(dd, "claims_runtime.json"), "w", encoding="utf-8") as f:
        f.write("{ kapot")
    try:
        claims_db.load(data_dir=dd)
        assert False, "kapotte overlay moet luid falen"
    except claims_db.ClaimsDbError:
        pass


# ── 2. Migratie ───────────────────────────────────────────────────────────────────────────────

def test_bereken_delta_tilt_extra_termen_en_statusdiffs():
    committed = {"termen": [{"patroon": "a", "term": "A"}],
                 "werklijst": [{"nr": 1, "status": "open"}], "meta": {"versie": "2026-07-01"}}
    working = {"termen": [{"patroon": "a", "term": "A"}, {"patroon": "b", "term": "B-runtime"}],
               "werklijst": [{"nr": 1, "status": "opgelost"}], "meta": {"versie": "2026-07-20"}}
    d = claims_migrate.bereken_delta(committed, working)
    assert [t["patroon"] for t in d["toegevoegd"]] == ["b"]
    assert d["werklijst"] == {"1": "opgelost"} and d["meta_versie"] == "2026-07-20"
    assert d["ingetrokken"] == []                                        # nooit auto-intrekken
    assert claims_migrate._leeg(claims_migrate.bereken_delta(committed, committed))


def test_migratie_is_idempotent_als_overlay_bestaat(tmp_path, capsys):
    _pad, dd = _kopie_seed(tmp_path)
    claims_db._schrijf_overlay(dd, claims_db._leeg_overlay())
    assert claims_migrate.main([dd]) == 0
    assert "bestaat al" in capsys.readouterr().out


# ── 3. Retract-UI via de dispatch ───────────────────────────────────────────────────────────────

def test_dispatch_retract_verwijdert_runtime_term(tmp_path, monkeypatch):
    pad, dd = _kopie_seed(tmp_path)
    monkeypatch.setattr(claims_db, "DB_PATH", pad)
    cockpit2.dispatch(dd, "claims_term_add",
                      {"term": ["Tijdelijk"], "patroon": ["tijdelijkterm"], "stoplicht": ["red"],
                       "categorie": ["Test"], "next": ["/claims"]}, "guest")
    assert any(t["patroon"] == "tijdelijkterm" for t in claims_db.load(data_dir=dd)["termen"])
    _, msg = cockpit2.dispatch(dd, "claims_term_retract",
                               {"patroon": ["tijdelijkterm"], "next": ["/claims"]}, "guest")
    assert msg.startswith("✓")
    assert not any(t["patroon"] == "tijdelijkterm" for t in claims_db.load(data_dir=dd)["termen"])


def test_database_tab_toont_intrek_knop_alleen_voor_curator(tmp_path, monkeypatch):
    pad, dd = _kopie_seed(tmp_path)
    monkeypatch.setattr(claims_db, "DB_PATH", pad)
    from nooch_village.views.claims import render_claims
    zonder = render_claims(csrf_token="t", tab="database", kan_cureren=False, data_dir=dd)
    assert "claims_term_retract" not in zonder
    met = render_claims(csrf_token="t", tab="database", kan_cureren=True, data_dir=dd)
    assert "claims_term_retract" in met and "Intrekken" in met
