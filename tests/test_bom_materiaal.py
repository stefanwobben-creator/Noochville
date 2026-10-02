"""BOM Correctie 3, delen C en D (2 oktober 2026).

C: het materiaal van een COMPONENT is bewerkbaar op `/bom` (store `bom_materialen`), met dezelfde
   poort als de leverancier; de leverancier volgt het NIEUWE materiaal, en het zaad ("Used in") ook.
D: één klikgedrag voor Materiaal én Supplier — ingevuld = link + los potloodje, leeg = formulier.
"""
from __future__ import annotations

import re

import pytest

from nooch_village import bom_materialen, bom_reken, cockpit2, wiki, wiki_seed
from nooch_village.data_bom import NOOCH_SCHOEN_BOM
from nooch_village.views.bom import render_bom

HOUDER = "mother_earth__nooch__creator_of_shoes"
KOP = "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\n"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Houder", "houder@t.nl")
    st.assign.assign(HOUDER, "person", st.people.by_email("houder@t.nl").id)
    st.people.add("Buiten", "buiten@t.nl")
    return dd, st


def _zet(dd, part, materiaal, wie="houder@t.nl"):
    return cockpit2.dispatch(dd, "bom_materiaal_zet",
                             {"part": [part], "materiaal": [materiaal], "next": ["/bom"]},
                             username=wie)[1]


# ── C: de store en de actie ─────────────────────────────────────────────────

def test_per_component_en_leeg_is_terug_naar_de_stuklijst(tmp_path):
    s = bom_materialen.BomMateriaalStore(str(tmp_path / "m.json"))
    assert s.zet("Heel  tab", " Hemp fabric ")
    assert s.van("heel tab") == "Hemp fabric" and s.alle() == {"heel tab": "Hemp fabric"}
    assert s.zet("Heel tab", "") and s.alle() == {}
    assert s.zet(" ", "X") is False


def test_de_houder_zet_het_materiaal_een_buitenstaander_niet(tmp_path):
    dd, _st = _dorp(tmp_path)
    assert "Vamp is now Hemp fabric" in _zet(dd, "Vamp", "Hemp fabric")
    assert cockpit2._Stores(dd).bom_materialen.van("Vamp") == "Hemp fabric"
    assert "follows the bill of materials again" in _zet(dd, "Vamp", "")
    with pytest.raises(cockpit2.Forbidden):
        _zet(dd, "Vamp", "Iets", wie="buiten@t.nl")
    assert cockpit2._Stores(dd).bom_materialen.van("Vamp") == ""


def test_de_leverancier_volgt_het_nieuwe_materiaal():
    tekst = KOP + "\t\tVamp\tHyphaLite\t\t22\n\t\tTongue\tHyphaLite\t\t5\n"
    lev = {"hyphalite": "Hypha Labs", "hemp fabric": "Hemp Co"}
    uit = bom_reken.bereken(tekst, [], lev, materialen={"vamp": "Hemp fabric"})
    vamp, tong = uit["rijen"]
    assert (vamp["materiaal"], vamp["supplier"], vamp["gewijzigd"]) == ("Hemp fabric", "Hemp Co", True)
    assert vamp["origineel"] == "HyphaLite"
    assert (tong["materiaal"], tong["supplier"], tong["gewijzigd"]) == ("HyphaLite", "Hypha Labs", False)
    # Een nieuw materiaal zonder koppeling: geen leverancier, geen oude meegenomen.
    zonder = bom_reken.bereken(tekst, [], {"hyphalite": "Hypha Labs"}, materialen={"vamp": "Cork"})
    assert zonder["rijen"][0]["supplier"] == ""


def test_used_in_volgt_het_gewijzigde_materiaal():
    paginas = {p["titel"]: p for p in wiki_seed.materiaal_paginas(
        NOOCH_SCHOEN_BOM, materialen={"vamp": "Hemp fabric"})}
    assert "- Vamp" in paginas["Hemp fabric"]["body"].split("## Used in")[1].split("##")[0]
    assert "- Vamp" not in paginas["HyphaLite"]["body"].split("## Used in")[1].split("##")[0]


# ── D: het klikgedrag ───────────────────────────────────────────────────────

def _rij(html, part):
    return re.search(rf"<tr><td>{re.escape(part)}</td>.*?</tr>", html, re.S).group(0)


def test_ingevuld_is_een_link_met_een_los_potloodje(tmp_path):
    dd, st = _dorp(tmp_path)
    pliant = st.att.add(HOUDER, "note", title="Pliant")
    nfw = st.att.add(HOUDER, "note", title="NFW")
    cockpit2.dispatch(dd, "bom_leverancier_zet", {"materiaal": ["Pliant"], "leverancier": ["NFW"],
                                                  "next": ["/bom"]}, username="houder@t.nl")
    rij = _rij(render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl"), "Outsole")
    for pagina, wat in ((pliant, "material of Outsole"), (nfw, "supplier of Pliant")):
        # De HOOFDKLIK is de link — niet de summary van het formulier.
        assert f"<a href='{wiki.pagina_url(pagina.id)}'>{pagina.title}</a> <details class='acard-d'>" in rij
        assert f"<summary class='chip outline' aria-label='change {wat}' title='change'>✎</summary>" in rij


def test_leeg_opent_meteen_het_formulier(tmp_path):
    _dd, st = _dorp(tmp_path)
    rij = _rij(render_bom(st, csrf_token="T", username="houder@t.nl"), "Outsole")
    assert "<summary class='chip outline'>+ link supplier</summary>" in rij


def test_een_lezer_ziet_links_en_geen_potloodje(tmp_path):
    _dd, st = _dorp(tmp_path)
    h = render_bom(st, csrf_token="T", username="buiten@t.nl")
    assert "✎" not in h and "bom_materiaal_zet" not in h
    assert "no supplier linked yet" in _rij(h, "Outsole")


def test_een_gewijzigd_materiaal_zegt_wat_de_stuklijst_zei(tmp_path):
    dd, _st = _dorp(tmp_path)
    _zet(dd, "Vamp", "Hemp fabric")
    rij = _rij(render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl"), "Vamp")
    assert "the bill of materials says HyphaLite" in rij
    assert ">back to bill of materials</button>" in rij
    # Een ongewijzigde rij heeft geen (lege) terugknop.
    tong = _rij(render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl"), "Tongue")
    assert "name='materiaal' value=''>" not in tong.split("bom_materiaal_zet")[1].split("</form>")[0]
