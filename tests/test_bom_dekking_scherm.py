"""De sectie "Coverage" op /bom (10 oktober 2026): de strook per materiaal en leverancier.

De rekenlaag zelf staat in `test_wiki_dekking.py`; hier alleen wat het SCHERM ermee doet.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki
from nooch_village.views.bom import render_bom

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _sectie(h: str) -> str:
    return h[h.index("id='coverage'"):]


def test_de_sectie_staat_onder_de_stuklijst_met_een_strook_per_materiaal(tmp_path):
    st = _dorp(tmp_path)
    h = render_bom(st, username="guest")
    s = _sectie(h)
    assert h.index("<h1") < h.index("id='coverage'")
    assert "Material coverage" in s and "Contains plastic?" in s
    assert s.count("<tr>") >= 14 + 1               # 14 materialen + de kop
    assert "nu-status--open" in s and "aria-label='Contains plastic?: Open'" in s


def test_het_doelfilter_laat_alleen_de_vragen_van_dat_doel_zien(tmp_path):
    st = _dorp(tmp_path)
    s = _sectie(render_bom(st, username="guest", doel="vs"))
    assert "Animal-derived" in s and "Contains plastic?" not in s
    assert "class='cl-filter on' href='/bom?doel=vs#coverage'" in s
    # CFJ vraagt niets aan een materiaal: geen materiaaltabel, wel de rollup voor leveranciers
    s = _sectie(render_bom(st, username="guest", doel="cfj"))
    assert "Material coverage" not in s and "CFJ labor" in s


def test_een_onbekend_doel_is_alles(tmp_path):
    st = _dorp(tmp_path)
    s = _sectie(render_bom(st, username="guest", doel="<script>"))
    assert "<script>" not in s and "Contains plastic?" in s


def test_de_rollup_noemt_beide_modellen(tmp_path):
    s = _sectie(render_bom(_dorp(tmp_path), username="guest"))
    assert "269 Lo</strong>: 0 of 14 materials" in s
    assert "269 Hi</strong>: 0 of 14 materials" in s


def test_een_cel_linkt_naar_het_kopje_op_de_pagina(tmp_path):
    st = _dorp(tmp_path)
    a = st.att.add(OWNER, "note", title="Pliant", body="## Contains plastic\n{{fact:a}}")
    st.att.update(a.id, meta={"feiten": [{"id": "a", "tekst": "No plastic.",
                                          "grond": {"soort": "attested", "ref": "Stefan",
                                                    "op": "2026-10-05"}}]})
    s = _sectie(render_bom(st, username="guest"))
    assert f"href='/pagina?id={a.id}#kop=Contains%20plastic'" in s
    assert "aria-label='Contains plastic?: Unchecked'" in s


def test_create_page_maakt_de_pagina_met_skelet_en_de_rij_wijst_ernaar(tmp_path):
    """De keten tot het eind: de velden van het formulier door `dispatch`, en daarna staat de rij
    op de nieuwe pagina — met het materiaalskelet als tekst."""
    import re

    st = _dorp(tmp_path)
    s = _sectie(render_bom(st, csrf_token="t", username="guest"))
    formulier = s[:s.index("Create page")]
    formulier = formulier[formulier.rindex("<form"):]
    velden = dict(re.findall(r"name='([a-z_]+)' value='([^']*)'", formulier))
    assert velden["title"] == "Pliant" and velden["sjabloon"] == "materiaal"
    assert velden["owner"] == "mother_earth__nooch__creator_of_shoes"
    import html
    form = {k: [html.unescape(v)] for k, v in velden.items() if k not in ("action", "csrf")}
    cockpit2.dispatch(st.dd, "artefact_add", form, username="guest")
    st = cockpit2._Stores(st.dd)
    nieuw = [a for a in wiki.paginas(st.att) if a.title == "Pliant"]
    assert len(nieuw) == 1 and "## CO2 & Water" in nieuw[0].body
    s = _sectie(render_bom(st, username="guest"))
    assert f"<a href='/pagina?id={nieuw[0].id}'>Pliant</a>" in s


def test_een_lezer_ziet_geen_create_page(tmp_path):
    s = _sectie(render_bom(_dorp(tmp_path), username="guest"))
    assert "Create page" not in s and "No page yet" in s
