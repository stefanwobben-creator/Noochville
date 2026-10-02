"""BOM Correctie 3, deel A (2 oktober 2026): de hoeveelheden schalen met de schoenmaat.

De stuklijst draagt de waarden bij de referentiemaat (42). Eén lineaire factor per maatstap, uit
`config/bom_maten.json` — een voorlopige aanname, en de pagina zegt dat. De factor werkt op de
HOEVEELHEID; gewicht, kostprijs, CO2e en water volgen vanzelf.
"""
from __future__ import annotations

import json

from nooch_village import bom_reken, cockpit2, wiki
from nooch_village.views.bom import render_bom

KOP = "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\n"
CFG = {"referentiemaat": 42, "schaal_per_maat": 0.03, "maten": list(range(36, 47)),
       "bron": "set by Stefan", "datum": "2026-10-02"}


def test_de_config_is_de_enige_bron_van_het_getal():
    cfg = bom_reken.maat_config()
    assert cfg["referentiemaat"] == 42 and cfg["schaal_per_maat"] == 0.03
    assert cfg["maten"] == list(range(36, 47))


def test_kapot_of_ontbrekend_is_geen_schaling(tmp_path):
    """Fail-closed: liever de referentiewaarden met een zin erbij dan een verzonnen factor."""
    assert bom_reken.maat_config(str(tmp_path / "weg.json")) == {}
    kapot = tmp_path / "kapot.json"
    kapot.write_text("{niet json")
    assert bom_reken.maat_config(str(kapot)) == {}
    zonder = tmp_path / "zonder.json"
    zonder.write_text(json.dumps({"referentiemaat": 42}))
    assert bom_reken.maat_config(str(zonder)) == {}
    assert bom_reken.schaalfactor(45, {}) == 1.0


def test_lineair_vanaf_de_referentie():
    assert bom_reken.schaalfactor(42, CFG) == 1.0
    assert abs(bom_reken.schaalfactor(45, CFG) - 1.09) < 1e-9
    assert abs(bom_reken.schaalfactor(38, CFG) - 0.88) < 1e-9


def test_alle_vier_de_totalen_schalen_mee_via_de_hoeveelheid(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = "mother_earth__nooch__creator_of_shoes"
    for titel, waarden in (("Helios 200", (("co2e_per_kg", "2"), ("water_per_kg", "100"))),
                           ("LTA S.R.L.", (("prijs_per_kg", "50"),))):
        a = st.att.add(rol, "note", title=titel)
        st.att.update(a.id, meta={"feiten": [wiki.maak_feit("x", waarde=wiki.maak_waarde(g, n))
                                             for g, n in waarden]})
    pags = wiki.paginas(cockpit2._Stores(dd).att)
    # TWEE RIJEN, en dat is geen toeval: met één rij bleef een bug onzichtbaar waarbij de
    # schaal-parameter in de lus werd overschreven door de factor van de vorige pagina.
    tekst = KOP + "\t\tHeel counter\tHelios 200\t\t10\n\t\tToe cap\tHelios 200\t\t4\n"
    lev = {"helios 200": "LTA S.R.L."}
    ref = bom_reken.bereken(tekst, pags, lev)["totalen"]
    groot = bom_reken.bereken(tekst, pags, lev, schaal=bom_reken.schaalfactor(45, CFG))["totalen"]
    for k in ("gram", "prijs", "co2e", "water"):
        assert abs(groot[k]["som"] - ref[k]["som"] * 1.09) < 1e-9, k


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_de_pagina_zegt_dat_het_een_schatting_is(tmp_path):
    h = render_bom(_st(tmp_path), maat="45")
    assert "size 45, scaled from reference size 42 by 3% per size step" in h
    assert "provisional assumption, not yet based on factory data" in h


def test_de_maatkiezer_is_het_bestaande_keuzebalkpatroon(tmp_path):
    """`.cl-bar` + `a.cl-filter`/`.on`. Een dropdown (`cardmenu`) klapte hier half achter de zijbalk."""
    h = render_bom(_st(tmp_path), maat="44")
    assert "<div class='cl-bar' aria-label='EU size'>" in h
    assert h.count("class='cl-filter") == 11
    assert "class='cl-filter on' href='/bom?maat=44' aria-current='true'" in h
    assert "cardmenu" not in h.split("BOM · Nooch shoe")[1]


def test_een_vreemde_maat_is_de_referentie(tmp_path):
    for maat in ("", "99", "abc"):
        assert "Quantities for the reference size 42" in render_bom(_st(tmp_path), maat=maat), maat


def test_na_een_koppeling_blijf_je_op_dezelfde_maat(tmp_path):
    h = render_bom(_st(tmp_path), csrf_token="T", username="guest", maat="40")
    assert "name='next' value='/bom?maat=40'" in h
