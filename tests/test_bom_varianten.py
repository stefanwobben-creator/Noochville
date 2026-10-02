"""BOM Stuk 4 (2 oktober 2026): modellen en varianten op de BOM.

A  model = topnaam met één master (`data_bom.MODELLEN`: sinds 2 oktober 269 Lo en 269 Hi, elk een
   eigen model); kleurvarianten (Shopify-handle) in `bom_varianten`
B  afwijkingen per (model, variant, component): materiaal en/of gewicht, of een rij erbij
C  `/bom` met model- en variantkeuze, afwijk-chips, foto
D  "Used in" op de materiaalpagina's noemt ook de varianten
"""
from __future__ import annotations

import pytest

from nooch_village import bom_reken, cockpit2, wiki_seed
from nooch_village.bom_materialen import BomMateriaalStore
from nooch_village.bom_varianten import BomVariantStore, geldige_handle
from nooch_village.data_bom import MODELLEN, NOOCH_SCHOEN_BOM, STANDAARD_MODEL
from nooch_village.views.bom import render_bom

HOUDER = "mother_earth__nooch__creator_of_shoes"
KOP = "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\n"
M = STANDAARD_MODEL


# ── A ───────────────────────────────────────────────────────────────────────

def test_269_lo_en_269_hi_zijn_twee_modellen():
    """Besluit Stefan (2 oktober): hoogte is geen variant maar een model; kleur is de variant. De
    huidige stuklijst is 269 Lo; 269 Hi begint ervan (verwijzing, geen kopie) en zegt dat erbij."""
    assert M == "269-lo"
    assert (MODELLEN["269-lo"]["naam"], MODELLEN["269-hi"]["naam"]) == ("269 Lo", "269 Hi")
    assert MODELLEN["269-lo"]["master"] is NOOCH_SCHOEN_BOM
    assert MODELLEN["269-hi"]["master"] is NOOCH_SCHOEN_BOM and MODELLEN["269-hi"]["basis_van"] == "269-lo"


def test_een_variant_is_een_shopify_handle_en_bestaat_maar_een_keer(tmp_path):
    s = BomVariantStore(str(tmp_path / "v.json"))
    assert s.voeg_toe(M, "the-269-hi-black", "Hi · Black")
    assert not s.voeg_toe(M, "the-269-hi-black", "Anders")       # niet overschrijven
    for slecht in ("Hi Black", "the_269", "-x", "x-", ""):
        assert not geldige_handle(slecht), slecht
    assert [v["handle"] for v in s.varianten(M)] == ["the-269-hi-black"]


def test_de_foto_valt_terug_op_het_model_en_weigert_vreemde_adressen(tmp_path):
    s = BomVariantStore(str(tmp_path / "v.json"))
    s.voeg_toe(M, "the-269-hi-black")
    assert s.zet_foto(M, "", "https://cdn.example/model.jpg")
    assert s.foto(M, "the-269-hi-black") == "https://cdn.example/model.jpg"
    assert s.zet_foto(M, "the-269-hi-black", f"/bom-foto/{M}/ab_hi.jpg")
    assert s.foto(M, "the-269-hi-black") == f"/bom-foto/{M}/ab_hi.jpg"
    assert s.heeft_foto(M, "ab_hi.jpg") and not s.heeft_foto(M, "ander.jpg")
    for slecht in ("javascript:alert(1)", "data:image/png;base64,x", "http://x/y.jpg"):
        assert not s.zet_foto(M, "", slecht), slecht
    assert not s.zet_foto(M, "bestaat-niet", "https://x/y.jpg")


# ── B ───────────────────────────────────────────────────────────────────────

def test_een_variant_gaat_voor_de_master_en_kan_een_rij_toevoegen(tmp_path):
    s = BomMateriaalStore(str(tmp_path / "m.json"))
    s.zet("Vamp", "Cork", model=M)                                  # master-afwijking
    s.zet("Vamp", "Hemp fabric", model=M, variant="hi", gram=30)    # variant wint
    s.zet("Upper hemp", "Hemp fabric", model=M, variant="hi", gram=12, toegevoegd=True)
    tekst = KOP + "\t\tVamp\tHyphaLite\t\t22\n\t\tTongue\tHyphaLite\t\t5\n"
    master = {r["part"]: r for r in bom_reken.effectieve_rijen(tekst, s.afwijkingen(M))}
    hi = {r["part"]: r for r in bom_reken.effectieve_rijen(tekst, s.afwijkingen(M, "hi"))}
    assert master["Vamp"]["material"] == "Cork" and "Upper hemp" not in master
    assert (hi["Vamp"]["material"], hi["Vamp"]["gram"], hi["Vamp"]["niveau"]) == ("Hemp fabric", 30.0, "hi")
    assert hi["Upper hemp"]["toegevoegd"] and hi["Upper hemp"]["gram"] == 12.0
    assert hi["Tongue"]["niveau"] == ""                             # ongemoeid


def test_een_oude_sleutel_leest_als_master_afwijking(tmp_path):
    """Vóór Stuk 4 was de sleutel alleen de component; dat blijft een master-afwijking."""
    pad = tmp_path / "m.json"
    pad.write_text('{"vamp": {"part": "Vamp", "materiaal": "Cork"}}')
    s = BomMateriaalStore(str(pad))
    assert s.alle(M) == {"vamp": "Cork"} and s.van("Vamp") == "Cork"
    s.zet("Vamp", "Hemp", model=M)                                  # gaat op in de nieuwe sleutel
    assert s.alle(M) == {"vamp": "Hemp"} and "vamp" not in s._d


def test_een_toegevoegde_rij_heeft_een_materiaal_nodig(tmp_path):
    s = BomMateriaalStore(str(tmp_path / "m.json"))
    assert not s.zet("Iets", "", model=M, variant="hi", gram=3, toegevoegd=True)


# ── de acties ───────────────────────────────────────────────────────────────

def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Houder", "houder@t.nl")
    st.assign.assign(HOUDER, "person", st.people.by_email("houder@t.nl").id)
    st.people.add("Buiten", "buiten@t.nl")
    return dd, st


def _doe(dd, actie, wie="houder@t.nl", **velden):
    return cockpit2.dispatch(dd, actie, {"next": ["/bom"], **{k: [v] for k, v in velden.items()}},
                             username=wie)[1]


def test_variant_aanmaken_met_poort_en_geldige_handle(tmp_path):
    dd, _st = _dorp(tmp_path)
    assert "added" in _doe(dd, "bom_variant_add", handle="the-269-hi-black", naam="Hi · Black")
    assert "already exists" in _doe(dd, "bom_variant_add", handle="the-269-hi-black")
    assert "Shopify handle" in _doe(dd, "bom_variant_add", handle="Hi Black")
    with pytest.raises(cockpit2.Forbidden):
        _doe(dd, "bom_variant_add", wie="buiten@t.nl", handle="the-269-black")


def test_materiaal_en_gewicht_overschrijven_elkaar_niet(tmp_path):
    """Twee formulieren op één niveau: alleen wat het formulier meestuurt verandert."""
    dd, _st = _dorp(tmp_path)
    _doe(dd, "bom_variant_add", handle="hi")
    assert "is now Hemp fabric" in _doe(dd, "bom_materiaal_zet", part="Vamp", variant="hi",
                                       materiaal="Hemp fabric")
    assert "weighs 30 g" in _doe(dd, "bom_materiaal_zet", part="Vamp", variant="hi", gram="30")
    r = cockpit2._Stores(dd).bom_materialen.regel("Vamp", variant="hi")
    assert (r["materiaal"], r["gram"]) == ("Hemp fabric", 30.0)
    assert "number of grams" in _doe(dd, "bom_materiaal_zet", part="Vamp", variant="hi", gram="veel")
    assert "unknown variant" in _doe(dd, "bom_materiaal_zet", part="Vamp", variant="lo", materiaal="X")
    assert "follows the master again" in _doe(dd, "bom_materiaal_zet", part="Vamp", variant="hi", wis="1")


def test_foto_via_adres(tmp_path):
    dd, _st = _dorp(tmp_path)
    assert "photo saved" in _doe(dd, "bom_foto", foto="https://cdn.example/269.jpg")
    assert "https://" in _doe(dd, "bom_foto", foto="javascript:alert(1)")
    assert cockpit2._Stores(dd).bom_varianten.foto(M) == "https://cdn.example/269.jpg"


# ── C ───────────────────────────────────────────────────────────────────────

def test_alleen_aangemaakte_varianten_en_master_zonder_keuze(tmp_path):
    dd, st = _dorp(tmp_path)
    _doe(dd, "bom_variant_add", handle="the-269-hi-black", naam="Hi · Black")
    h = render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl")
    balk = h.split("aria-label='variant'>")[1].split("</div>")[0]
    assert "class='cl-filter on' href='/bom'>Master</a>" in balk
    assert ">Hi · Black</a>" in balk and balk.count("class='cl-filter") == 2
    assert "+ variant" in balk
    assert "BOM · 269 Lo" in h


def test_een_variant_toont_zijn_afwijkingen_met_een_terugknop(tmp_path):
    dd, _st = _dorp(tmp_path)
    _doe(dd, "bom_variant_add", handle="hi", naam="Hi")
    _doe(dd, "bom_materiaal_zet", part="Vamp", variant="hi", materiaal="Hemp fabric")
    _doe(dd, "bom_materiaal_zet", part="Upper hemp", variant="hi", materiaal="Hemp fabric",
         gram="12", toegevoegd="1")
    h = render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl", variant="hi")
    assert "Vamp <span class='chip muted'>differs from master</span>" in h
    assert "Upper hemp <span class='chip muted'>added in this variant</span>" in h
    assert ">back to master</button>" in h and ">remove component</button>" in h
    # De terugweg houdt de variant vast — en wordt niet dubbel ge-escaped.
    assert "name='next' value='/bom?variant=hi'" in h
    # De master ziet niets van de variant.
    master = render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl")
    assert "Upper hemp" not in master and "differs from master" not in master


def test_een_geuploade_foto_is_een_beeld_een_adres_een_kaart(tmp_path):
    """Het BEELD is het bestaande embed-atoom (`_embed_html`). Die maakt alleen een `<img>` van een
    bestand op onze eigen server — nu ook `/bom-foto/` — en NIET van een extern adres: dat zou bij
    elke paginaweergave een verzoek naar een derde partij doen (`test_er_wordt_geen_img_geladen`).
    Een https-foto blijft dus een kaart met link, tot daar bewust anders over besloten wordt."""
    dd, st = _dorp(tmp_path)
    st.bom_varianten.zet_foto(M, "", f"/bom-foto/{M}/ab_269.jpg")
    h = render_bom(cockpit2._Stores(dd), csrf_token="", username="buiten@t.nl")
    kop = h.split("class='ptitle'")[1].split("aria-label='model'")[0]   # niet het logo meetellen
    assert "<img" in kop and f"/bom-foto/{M}/ab_269.jpg" in kop
    assert "enctype='multipart/form-data'" not in h                 # een lezer krijgt geen upload
    _doe(dd, "bom_foto", foto="https://cdn.example/269.jpg")
    h2 = render_bom(cockpit2._Stores(dd), csrf_token="", username="buiten@t.nl")
    assert "https://cdn.example/269.jpg" in h2 and "<img" not in h2.split("class='ptitle'")[1].split("aria-label='model'")[0]


# ── D ───────────────────────────────────────────────────────────────────────

def test_used_in_noemt_de_variant(tmp_path):
    dd, _st = _dorp(tmp_path)
    _doe(dd, "bom_variant_add", handle="the-269-hi-black", naam="Hi · Black")
    _doe(dd, "bom_materiaal_zet", part="Upper hemp", variant="the-269-hi-black",
         materiaal="Hemp fabric", toegevoegd="1")
    st = cockpit2._Stores(dd)
    gebruik = wiki_seed.variant_gebruik(st.bom_materialen, st.bom_varianten)
    assert gebruik == [("Hemp fabric", "Upper hemp", "Hi · Black")]
    ps = {p["titel"]: p for p in wiki_seed.materiaal_paginas(NOOCH_SCHOEN_BOM, varianten=gebruik)}
    assert "- Upper hemp — Hi · Black" in ps["Hemp fabric"]["body"]


def test_een_foto_van_de_eigen_shopify_winkel_is_een_beeld(tmp_path):
    """De ene externe uitzondering (`NOOCH_SHOPIFY_BEELDEN`): de productfoto's die Nooch zelf in
    Shopify heeft, zijn een eigen asset en mogen bovenaan `/bom` als beeld staan."""
    from nooch_village.cockpit2_util import NOOCH_SHOPIFY_BEELDEN
    dd, _st = _dorp(tmp_path)
    url = NOOCH_SHOPIFY_BEELDEN[0] + "files/269-hi-black.jpg"
    assert "photo saved" in _doe(dd, "bom_foto", foto=url)
    h = render_bom(cockpit2._Stores(dd), csrf_token="", username="buiten@t.nl")
    # ALLEEN het stuk tussen titel en kiezers: het logo in de navigatie is óók een `<img>`, en daar
    # liep deze toets eerst op mee (een mutatieproef bleef groen).
    kop = h.split("class='ptitle'")[1].split("aria-label='model'")[0]
    assert "<img" in kop and url in kop



# ── 2 oktober: twee modellen, geen maat, foto naar het model ────────────────

def test_geen_maatkiezer_meer_alles_bij_de_referentiemaat(tmp_path):
    _dd, st = _dorp(tmp_path)
    h = render_bom(st, csrf_token="", username="buiten@t.nl")
    assert "aria-label='EU size'" not in h and "maat=" not in h
    assert "Quantities at reference size EU 42." in h


def test_269_hi_zegt_dat_hij_van_269_lo_begint(tmp_path):
    _dd, st = _dorp(tmp_path)
    hi = render_bom(st, csrf_token="", username="buiten@t.nl", model="269-hi")
    assert "BOM · 269 Hi" in hi and "it starts from 269 Lo" in hi
    assert "it starts from" not in render_bom(st, csrf_token="", username="buiten@t.nl")
    modellen = hi.split("aria-label='model'>")[1].split("</div>")[0]
    assert ">269 Lo</a>" in modellen and "class='cl-filter on' href='/bom?model=269-hi'>269 Hi</a>" in modellen


def test_een_afwijking_van_269_hi_raakt_269_lo_niet(tmp_path):
    dd, _st = _dorp(tmp_path)
    _doe(dd, "bom_materiaal_zet", model="269-hi", part="Upper hemp", materiaal="Hemp fabric",
         gram="12", toegevoegd="1")
    st = cockpit2._Stores(dd)
    assert "Upper hemp" in render_bom(st, csrf_token="T", username="houder@t.nl", model="269-hi")
    assert "Upper hemp" not in render_bom(st, csrf_token="T", username="houder@t.nl")


def test_een_nieuwe_foto_in_een_kleur_gaat_naar_het_model(tmp_path):
    """Stefans check: "+ photo" in een kleurvariant zonder foto mag GEEN losse variant-foto maken die
    de andere kleuren niet zien. De keuze staat op het model; "only this colour" kan bewust."""
    dd, _st = _dorp(tmp_path)
    _doe(dd, "bom_variant_add", handle="the-269-black", naam="Black")
    h = render_bom(cockpit2._Stores(dd), csrf_token="T", username="houder@t.nl",
                   variant="the-269-black")
    keuze = h.split("aria-label='who gets this photo'>")[1].split("</select>")[0]
    assert "<option value='' selected>whole model (every colour)</option>" in keuze
    assert "<option value='the-269-black'>only this colour</option>" in keuze
    # Het formulier draagt zelf geen vaste variant meer: de keuze beslist.
    assert "name='variant' value='the-269-black'" not in h.split("+ photo")[1].split("</details>")[0]
    # Een foto zonder variant komt bij het model, en elke kleur ziet hem.
    _doe(dd, "bom_foto", foto="https://cdn.example/lo.jpg", variant="")
    st = cockpit2._Stores(dd)
    assert st.bom_varianten.foto(M, "the-269-black") == "https://cdn.example/lo.jpg"
    assert (st.bom_varianten.get(M, "the-269-black") or {}).get("foto") == ""
