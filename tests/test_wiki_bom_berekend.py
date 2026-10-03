""""From the BOM" op een wiki-pagina: berekend uit /bom, niet gezaaid in de tekst (3 oktober 2026).

Aanleiding: op de NFW-pagina verdween de Material-regel bij een gewone bewerking, en de
Pliant PCS-pagina wees na een hernoeming met "Supplied by: [[NFW]]" naar een pagina die niet meer
bestaat. Beide omdat het TEKST was. Nu leest de pagina het bij elke weergave uit dezelfde stores
als /bom, buiten wat een bewerking kan raken.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki_seed
from nooch_village.views.wiki import render_pagina

ROL = "mother_earth__nooch__website_developer"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mat = st.att.add(ROL, "note", title="Pliant PCS", body="Hand-written text.")
    lev = st.att.add(ROL, "note", title="Natural Fiber Welding (NFW)", body="Supplier.")
    st.bom_materialen.zet("Outsole", "Pliant PCS")
    st.bom_leveranciers.zet("Pliant PCS", "Natural Fiber Welding (NFW)")
    return dd, mat.id, lev.id


def _blok(dd, aid):
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")
    if "From the BOM" not in h:
        return ""
    b = h[h.index("From the BOM"):]
    return b[:b.index("</div>")]


def test_een_materiaalpagina_toont_used_in_en_supplied_by(tmp_path):
    dd, mat, lev = _dorp(tmp_path)
    blok = _blok(dd, mat)
    assert "Used in" in blok and "Outsole — 269 Lo" in blok
    assert "Supplied by" in blok and f"href='/pagina?id={lev}'" in blok


def test_een_leverancierpagina_toont_zijn_materiaal(tmp_path):
    dd, mat, lev = _dorp(tmp_path)
    blok = _blok(dd, lev)
    assert "Material" in blok and f"href='/pagina?id={mat}'" in blok


def test_het_blok_loopt_mee_met_bom(tmp_path):
    """Andere leverancier op /bom → de pagina zegt dat meteen, zonder zaaien of bewerken."""
    dd, mat, lev = _dorp(tmp_path)
    cockpit2._Stores(dd).bom_leveranciers.zet("Pliant PCS", "Nieuwe Leverancier")
    blok = _blok(dd, mat)
    assert "Nieuwe Leverancier" in blok and f"id={lev}" not in blok
    assert _blok(dd, lev) == ""                     # NFW levert niets meer → geen blok


def test_een_bewerking_kan_het_blok_niet_wegvegen(tmp_path):
    dd, mat, lev = _dorp(tmp_path)
    cockpit2._Stores(dd).att.update(mat, body="")    # de hele tekst weg
    assert "Supplied by" in _blok(dd, mat)


def test_zonder_koppeling_zegt_het_blok_dat(tmp_path):
    dd, mat, _lev = _dorp(tmp_path)
    cockpit2._Stores(dd).bom_leveranciers.zet("Pliant PCS", "")
    assert "No supplier linked on the BOM screen yet." in _blok(dd, mat)


def test_een_gewone_pagina_krijgt_geen_blok(tmp_path):
    dd, _m, _l = _dorp(tmp_path)
    los = cockpit2._Stores(dd).att.add(ROL, "note", title="How we decide here", body="x")
    assert _blok(dd, los.id) == ""


# ══ de opruimronde voor bestaande pagina's ══════════════════════════════════
ZAAD = """From the bill of materials of the Nooch shoe (founder input).

## Used in
- Outsole — 269 Lo, 269 Hi

## Supplied by
- [[NFW]]

## CO2 & Water
As a fact with a value.

## Open items
- Supplied by: no supplier linked on the BOM screen yet
- Dye/chemical disclosure: not yet provided
"""


def test_de_zaad_secties_gaan_weg_en_de_rest_blijft_letterlijk():
    nieuw, weg, blijft = wiki_seed.bom_secties_weg(ZAAD)
    assert "## Used in" not in nieuw and "## Supplied by" not in nieuw and "[[NFW]]" not in nieuw
    assert "no supplier linked" not in nieuw
    assert "## CO2 & Water\nAs a fact with a value." in nieuw
    assert "- Dye/chemical disclosure: not yet provided" in nieuw
    assert nieuw.startswith("From the bill of materials") and "\n\n\n" not in nieuw
    assert set(weg) == {"Used in", "Supplied by", "open item: no supplier linked"} and blijft == []


def test_eigen_tekst_onder_material_blijft_staan():
    """De NFW-pagina: onder "Material" schreef een mens zelf een alinea. Niet aanraken, wel melden."""
    body = "Intro.\n\n## Material\nPliant PCS: 100% biobased. See material page [[Pliant PCS]].\n"
    nieuw, weg, blijft = wiki_seed.bom_secties_weg(body)
    assert nieuw == body and weg == [] and blijft and "not from the seed" in blijft[0]


def test_opschonen_is_een_nieuwe_versie_en_alleen_met_apply(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    a = st.att.add(ROL, "note", title="Pliant", body=ZAAD)
    voor = a.body
    rapport = wiki_seed.bom_opschoon(st.att)                      # dry-run
    assert rapport and cockpit2._Stores(dd).att.get(a.id).body == voor
    wiki_seed.bom_opschoon(st.att, apply=True, actor_id="cli")
    na = cockpit2._Stores(dd).att.get(a.id)
    assert "## Supplied by" not in na.body
    # EEN NIEUWE VERSIE, dus terug te draaien: de oude tekst staat in de historie.
    assert any("## Supplied by" in (v.get("body_snapshot") or "") for v in (na.versions or []))
