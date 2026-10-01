"""Een nieuwe materiaal- of leverancierpagina start met een skelet (BOM stuk 3, 1 oktober 2026).

Stap 4 van "+ New page" volgt HETZELFDE mechanisme als stap 1-3: een gewone select zonder handler,
mee met de ene Create-knop. `artefact_add` vult de body uit `wiki.SJABLONEN`; het blijft vrije tekst.
"""
from __future__ import annotations

import re

from nooch_village import cockpit2, wiki
from nooch_village.views.wiki import _nieuwe_pagina_form

ROL = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _maak(dd, titel, **extra):
    form = {"csrf": ["T"], "owner": [ROL], "kind": ["note"], "title": [titel], "next": ["/"],
            **{k: [v] for k, v in extra.items()}}
    cockpit2.dispatch(dd, "artefact_add", form, username="guest")
    return next(x for x in cockpit2._Stores(dd).att.by_kind("note") if x.title == titel)


def test_stap_4_volgt_het_mechanisme_van_stap_1_tot_3(tmp_path):
    """Conformance: dezelfde vorm (`.att-lbl` + kale `<select>`), geen eigen auto-submit, en
    hij hoort bij hetzelfde formulier als de ene Create-knop."""
    html = _nieuwe_pagina_form(cockpit2._Stores(_dd(tmp_path)), "T", "guest")
    assert "<label class='att-lbl' for='np-sjabloon'>4. Start from</label>" in html
    selects = re.findall(r"<select [^>]*>", html)
    assert "<select id='np-sjabloon' name='sjabloon'>" in selects
    assert not any("onchange" in s for s in selects), "een stap verstuurt zichzelf"
    assert html.count("<form") == 1 and html.count("type='submit'") == 1
    assert html.index("np-sjabloon") < html.index(">Create</button>")
    for sleutel, (label, _body) in wiki.SJABLONEN.items():         # de opties uit de ene tabel
        assert f"<option value='{sleutel}'>{label}</option>" in html


def test_een_materiaalpagina_krijgt_de_kopjes(tmp_path):
    a = _maak(_dd(tmp_path), "Biorel", sjabloon="materiaal")
    for kop in ("Characteristics", "CO2 & Water", "Circularity", "Supplied by", "Certification",
                "Open items"):
        assert f"## {kop}" in a.body
    assert "Price agreement" not in a.body                    # de prijs hoort bij de leverancier


def test_een_leverancierpagina_krijgt_de_kopjes(tmp_path):
    a = _maak(_dd(tmp_path), "LTA S.R.L.", sjabloon="leverancier")
    for kop in ("Location & contact", "Company certification", "Material", "Price agreement",
                "Open items"):
        assert f"## {kop}" in a.body
    assert "CO2 & Water" not in a.body


def test_leeg_onbekend_of_met_eigen_tekst_geen_skelet(tmp_path):
    dd = _dd(tmp_path)
    assert _maak(dd, "Leeg").body == ""
    assert _maak(dd, "Vreemd", sjabloon="verzonnen").body == ""
    assert _maak(dd, "Eigen", sjabloon="materiaal", body="Mijn eigen tekst").body == "Mijn eigen tekst"


def test_een_skelet_bevat_geen_wiki_link():
    """`[[link]]` als voorbeeld werd een echte link naar een pagina "link", en zette die op de
    verlanglijst van elke nieuwe pagina. Gezien bij de visuele check."""
    for _label, body in wiki.SJABLONEN.values():
        assert wiki.verwijzingen(body) == []


def test_zaad_en_skelet_gebruiken_dezelfde_koppen():
    """Eén vocabulaire. Een automatisch gezaaide pagina en een pagina uit het skelet horen dezelfde
    kop te gebruiken voor hetzelfde onderdeel; "Used in" is de enige zaad-eigen kop (de stuklijst
    weet waar een materiaal in zit, het skelet niet)."""
    from nooch_village import wiki_seed
    from nooch_village.data_bom import NOOCH_SCHOEN_BOM
    kop = re.compile(r"^## (.+)$", re.M)
    skelet = {k for _l, body in wiki.SJABLONEN.values() for k in kop.findall(body)}
    zaad = {k for p in wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM) for k in kop.findall(p["body"])}
    assert zaad - {"Used in"} <= skelet, zaad - skelet
