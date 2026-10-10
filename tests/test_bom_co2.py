"""CO2e per paar uit /bom (10 oktober 2026): het getal, zijn volledigheid, en de dagreeks per model."""
from __future__ import annotations

import datetime
import types

from nooch_village import bom_co2, bom_reken, cockpit2, wiki
from nooch_village.skills_impl.bom_co2 import BomCo2Source
from nooch_village.views.bom import render_bom

OWNER = "mother_earth__nooch__creator_of_shoes"
KOP = "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\n"


def _bom(*rijen: str) -> str:
    return KOP + "".join(r + "\n" for r in rijen)


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _factor(st, titel, kg):
    a = st.att.add(OWNER, "note", title=titel)
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("CO2 volgens de bron", soort="bron",
                                                        url="https://x",
                                                        waarde=wiki.maak_waarde("co2e_per_kg", kg))]})


def _uit(dd, tekst):
    return bom_reken.bereken(tekst, wiki.paginas(cockpit2._Stores(dd).att))


# ── het getal en zijn volledigheid ──────────────────────────────────────────

def test_zonder_gewicht_geen_getal_en_geen_nul(tmp_path):
    dd = _dd(tmp_path)
    _factor(cockpit2._Stores(dd), "Pliant", "2")
    r = bom_co2.co2_per_paar(_uit(dd, _bom("\t\tOutsole\tPliant\t\t")))
    assert r["kg"] is None and r["ondergrens"] and r["met_factor"] == 1
    assert bom_co2.tekst(r).startswith("No CO2e per pair yet")


def test_een_deel_telt_mee_en_dat_is_een_ondergrens(tmp_path):
    dd = _dd(tmp_path)
    _factor(cockpit2._Stores(dd), "Pliant", "2")
    r = bom_co2.co2_per_paar(_uit(dd, _bom("\t\tOutsole\tPliant\t\t500",
                                           "\t\tLaces\tCotton\t\t10",
                                           "\t\tTongue\tCotton\t\t5")))
    assert r["kg"] == 1.0 and r["ondergrens"]
    assert (r["met_factor"], r["materialen"], r["zonder_factor"]) == (1, 2, ["Cotton"])
    t = bom_co2.tekst(r)
    assert t.startswith("1.00 kg CO2e per pair (lower bound), based on 1 of 2 materials")
    assert "1 have no factor yet: Cotton" in t and "Materials only" in t


def test_compleet_is_geen_ondergrens_maar_zegt_wel_waarop_het_rust(tmp_path):
    dd = _dd(tmp_path)
    _factor(cockpit2._Stores(dd), "Pliant", "2")
    r = bom_co2.co2_per_paar(_uit(dd, _bom("\t\tOutsole\tPliant\t\t500")))
    assert not r["ondergrens"]
    assert bom_co2.tekst(r) == ("1.00 kg CO2e per pair, based on 1 of 1 materials. "
                                "Materials only, not a full LCA.")


def test_ontbrekende_gewichten_staan_erbij(tmp_path):
    dd = _dd(tmp_path)
    _factor(cockpit2._Stores(dd), "Pliant", "2")
    r = bom_co2.co2_per_paar(_uit(dd, _bom("\t\tOutsole\tPliant\t\t500", "\t\tSole\tPliant\t\t")))
    assert r["zonder_gewicht"] == ["Sole"] and "1 of 2 components have no weight yet" in bom_co2.tekst(r)


def test_de_vingerafdruk_volgt_de_samenstelling_niet_de_factor(tmp_path):
    """Een ander product = een andere vingerafdruk; een factor erbij = dezelfde (alleen de dekking)."""
    dd = _dd(tmp_path)
    tekst = _bom("\t\tOutsole\tPliant\t\t500", "\t\tLaces\tCotton\t\t10")
    voor = bom_co2.co2_per_paar(_uit(dd, tekst))["samenstelling"]
    _factor(cockpit2._Stores(dd), "Pliant", "2")
    assert bom_co2.co2_per_paar(_uit(dd, tekst))["samenstelling"] == voor
    ander = _bom("\t\tOutsole\tPliant\t\t520", "\t\tLaces\tCotton\t\t10")
    assert bom_co2.co2_per_paar(_uit(dd, ander))["samenstelling"] != voor


# ── de dagreeks per model ───────────────────────────────────────────────────

def _collect(dd, dag=datetime.date(2026, 10, 10)):
    st = cockpit2._Stores(dd)
    return BomCo2Source().collect_series(types.SimpleNamespace(data_dir=dd), dag, st.observations)


def test_zonder_getal_schrijft_de_bron_niets(tmp_path):
    """De echte stuklijst heeft nog geen gewichten: dan is er geen punt, geen 0."""
    dd = _dd(tmp_path)
    assert _collect(dd) == []


def test_een_punt_per_model_met_volledigheid_en_idempotent(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _factor(st, "Pliant", "2")
    st.bom_materialen.zet("Outsole", model="269-lo", gram="500")
    w = _collect(dd)
    assert w == [("bom", "co2e_per_paar::269-lo", "2026-10-10")]     # Hi heeft nog geen gewicht
    rij = cockpit2._Stores(dd).observations.daily_series("bom_co2e_per_paar_day::269-lo", bron="bom")[-1]
    assert rij["value"] == 1.0 and rij["datum"] == "2026-10-10"
    assert rij["meta"]["ondergrens"] and "Pliant" not in rij["meta"]["zonder_factor"]
    assert rij["meta"]["samenstelling"]
    assert _collect(dd) == []                                         # zelfde dag: niets dubbel


def test_de_bron_staat_standaard_aan(tmp_path):
    from nooch_village.collector import migrate_data_sources
    dd = _dd(tmp_path)
    migrate_data_sources(dd)
    assert cockpit2._Stores(dd).sources.active("bom")


# ── op het scherm ───────────────────────────────────────────────────────────

def test_de_tegel_toont_de_laatste_waarde_met_volledigheid(tmp_path):
    from nooch_village.views.metrics import _render_tile, _sources_for
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    _factor(st, "Pliant", "2")
    st.bom_materialen.zet("Outsole", model="269-lo", gram="500")
    _collect(dd)
    st = cockpit2._Stores(dd)
    rec = st.records.get("mother_earth__nooch")
    bron = next(s for s in _sources_for(st, rec) if s["id"] == "bom")
    assert ("269-lo", "CO₂e per pair · 269 Lo") in bron["measures"]
    tile = {"id": "t", "source": "bom", "measure": "269-lo", "dim": "totaal", "form": "getal"}
    h = _render_tile(st, rec, tile, None, "")
    assert "kg CO₂e/pair" in h and "(lower bound), based on 1 of" in h


def test_bom_toont_de_volledigheid_onder_de_tegels(tmp_path):
    h = render_bom(cockpit2._Stores(_dd(tmp_path)), username="guest")
    assert "No CO2e per pair yet, based on 0 of 14 materials; 14 have no factor yet:" in h
