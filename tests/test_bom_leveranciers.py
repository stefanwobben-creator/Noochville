"""BOM Correctie 2 (2 oktober 2026): de materiaal → leverancier-koppeling is bewerkbaar op `/bom`.

Stefan: "ik zie niet hoe ik de BOM kan bewerken." De koppeling woont nu in één kleine store, per
MATERIAAL; het BOM-scherm zet hem, de materiaalpagina ("Supplied by") toont hem.
"""
from __future__ import annotations

import pytest

from nooch_village import bom_leveranciers, cockpit2, wiki, wiki_seed
from nooch_village.data_bom import NOOCH_SCHOEN_BOM
from nooch_village.views.bom import render_bom

HOUDER = "mother_earth__nooch__creator_of_shoes"          # houdt `Materials` in het testdorp


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Houder", "houder@t.nl")
    st.assign.assign(HOUDER, "person", st.people.by_email("houder@t.nl").id)
    st.people.add("Buiten", "buiten@t.nl")
    return dd, st


def _zet(dd, materiaal, leverancier, wie="houder@t.nl"):
    return cockpit2.dispatch(dd, "bom_leverancier_zet",
                             {"materiaal": [materiaal], "leverancier": [leverancier], "next": ["/bom"]},
                             username=wie)[1]


# ── de store ────────────────────────────────────────────────────────────────

def test_per_materiaal_met_dezelfde_sleutel_als_de_pagina(tmp_path):
    s = bom_leveranciers.BomLeverancierStore(str(tmp_path / "b.json"))
    assert s.zet("BIOREL (?)", "  BioFab  ")
    assert s.van("biorel") == "BioFab"                          # '(?)' en hoofdletters tellen niet
    assert s.alle() == {"biorel": "BioFab"}
    assert s.zet("BIOREL", "")                                  # leeg = ontkoppelen
    assert s.alle() == {}
    assert s.zet("  ", "X") is False                            # zonder materiaal niets te koppelen


def test_de_koppeling_overleeft_een_nieuwe_store_instantie(tmp_path):
    """Lock-veilig op schijf: het cockpit schrijft, de zaaier (een ander proces) leest."""
    pad = str(tmp_path / "b.json")
    bom_leveranciers.BomLeverancierStore(pad).zet("Pliant", "NFW")
    assert bom_leveranciers.BomLeverancierStore(pad).van("Pliant") == "NFW"


# ── de actie en zijn poort ──────────────────────────────────────────────────

def test_de_houder_van_materials_zet_de_koppeling(tmp_path):
    dd, _st = _dorp(tmp_path)
    assert "Pliant supplied by NFW" in _zet(dd, "Pliant", "NFW")
    assert cockpit2._Stores(dd).bom_leveranciers.van("Pliant") == "NFW"
    assert "removed" in _zet(dd, "Pliant", "")
    assert cockpit2._Stores(dd).bom_leveranciers.van("Pliant") == ""


def test_wie_materials_niet_houdt_krijgt_403(tmp_path):
    dd, _st = _dorp(tmp_path)
    with pytest.raises(cockpit2.Forbidden):
        _zet(dd, "Pliant", "NFW", wie="buiten@t.nl")
    assert cockpit2._Stores(dd).bom_leveranciers.van("Pliant") == ""


# ── het scherm ──────────────────────────────────────────────────────────────

def test_de_supplier_cel_is_het_deadline_patroon_voor_wie_mag(tmp_path):
    dd, st = _dorp(tmp_path)
    html = render_bom(st, csrf_token="T", username="houder@t.nl")
    assert html.count("value='bom_leverancier_zet'") == 23          # één per component
    assert "<details class='acard-d'><summary class='chip outline'>+ supplier</summary>" in html
    assert "<div class='datepop'>" in html and "list='bom-lev-opties'" in html
    assert html.count("<datalist id='bom-lev-opties'>") == 1


def test_een_lezer_ziet_geen_formulier(tmp_path):
    dd, st = _dorp(tmp_path)
    for wie, csrf in (("buiten@t.nl", "T"), ("houder@t.nl", "")):
        html = render_bom(st, csrf_token=csrf, username=wie)
        assert "bom_leverancier_zet" not in html and "datalist" not in html, wie


def test_een_koppeling_staat_op_alle_componenten_van_dat_materiaal(tmp_path):
    """HyphaLite zit in zeven onderdelen: één koppeling, zeven keer zichtbaar."""
    dd, st = _dorp(tmp_path)
    _zet(dd, "HyphaLite", "Hypha Labs")
    a = st.att.add(HOUDER, "note", title="Hypha Labs")
    html = render_bom(cockpit2._Stores(dd), csrf_token="", username="buiten@t.nl")
    assert html.count(f"href='{wiki.pagina_url(a.id)}'>Hypha Labs</a>") == 7


# ── de materiaalpagina leest dezelfde bron ──────────────────────────────────

def test_de_pagina_leest_dezelfde_koppeling(tmp_path):
    """Eén bron: wat op /bom gekoppeld is, toont de materiaalpagina — berekend, niet gezaaid."""
    from nooch_village.views.wiki import render_pagina
    dd, st = _dorp(tmp_path)
    _zet(dd, "Pliant", "NFW")
    a = st.att.add(HOUDER, "note", title="Pliant")
    h = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="guest")
    blok = h[h.index("From the BOM"):]
    assert "Supplied by" in blok and "NFW" in blok[:blok.index("BOM screen")]
