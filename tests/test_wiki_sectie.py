"""De sectie van een pagina is te kiezen (26 september 2026).

`bakje_van` leidt de navigatiesectie af uit het domein van de rol, en dat werkt — voor een pagina
die zo'n domein heeft. Het gat zat bij een pagina die er geen heeft:

  - een individuele actie (`ii:<cirkel>`) heeft geen rol, dus geen domein;
  - een rol met twee domeinen in verschillende bakjes levert bewust "Overig — dit vraagt een
    override" op.

In allebei die gevallen bestond de override al als mechanisme (stap 0 van `bakje_van`, die
`meta["domein"]` leest) maar was er nooit een schrijfpad. Op prod staan 3 van de 121 pagina's op
zo'n override; die zijn met de hand in de data gezet.

WAT ONGEWIJZIGD BLIJFT: `bakje_van` zelf, en `_domein_form` — dat gaat puur over het
governance-domein en niet over waar de pagina in de navigatie staat.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, domeinen, wiki
from nooch_village.views.wiki import _nieuwe_pagina_form, _sectie_form, render_pagina

ROL = "mother_earth__nooch__creator_of_shoes"
DOMEIN = "Materials"
CIRKEL = "mother_earth__nooch"
II = f"ii:{CIRKEL}"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    houder = st.people.add("Houder", "houder@t.nl")
    buiten = st.people.add("Buiten", "buiten@t.nl")
    st.assign.assign(ROL, "person", houder.id)
    return dd, st, {"houder": houder, "buiten": buiten}


def _zet(dd, aid, sectie, mail="buiten@t.nl"):
    return cockpit2.dispatch(dd, "pagina_sectie",
                             {"csrf": ["T"], "aid": [aid], "sectie": [sectie], "next": ["/"]},
                             username=mail)


# ── 1. Het schrijfpad dat ontbrak ────────────────────────────────────────────
def test_een_sectie_kiezen_schrijft_de_override(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    _zet(dd, a.id, "finance")
    na = cockpit2._Stores(dd).att.get(a.id)
    assert (na.meta or {}).get("domein") == "finance"


def test_en_bakje_van_volgt_hem_meteen(tmp_path):
    """DE HELE KETEN, niet alleen het veld: de override is stap 0 en wint dus van alles erna."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    st2 = cockpit2._Stores(dd)
    assert domeinen.bakje_van(a, st2.records.all())[0] == "overig", "de opstelling klopt niet"
    _zet(dd, a.id, "finance")
    st3 = cockpit2._Stores(dd)
    bakje, waarom = domeinen.bakje_van(st3.att.get(a.id), st3.records.all())
    assert bakje == "finance" and "override" in waarom


def test_hij_wint_ook_van_een_bestaand_domein(tmp_path):
    """Stap 0 staat vóór stap 1. Dat is precies waarom de poort hieronder dezelfde moet zijn als
    die van het domein — anders is dit een omweg."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Met domein", body="x", domain=DOMEIN)
    _zet(dd, a.id, "finance", mail="houder@t.nl")
    st2 = cockpit2._Stores(dd)
    assert domeinen.bakje_van(st2.att.get(a.id), st2.records.all())[0] == "finance"


def test_leeg_haalt_de_override_weg(tmp_path):
    """LEEG IS "LEID HEM AF", niet "geen sectie". Dat is de stand waar de meeste pagina's in horen
    te blijven: dan verschuift de pagina netjes mee als governance iets herindeelt."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Met domein", body="x", domain=DOMEIN)
    _zet(dd, a.id, "finance", mail="houder@t.nl")
    _zet(dd, a.id, "", mail="houder@t.nl")
    st2 = cockpit2._Stores(dd)
    na = st2.att.get(a.id)
    assert "domein" not in (na.meta or {})
    assert domeinen.bakje_van(na, st2.records.all())[0] == "shoe-development"


def test_een_onbekende_sectie_wordt_geweigerd(tmp_path):
    """Fail-closed, zoals `bakje_van` zelf ook doet met een sleutel die niet bestaat: een pagina
    mag niet uit de structuur getild worden door een typefout."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    _nxt, msg = _zet(dd, a.id, "verzonnen-bakje")
    assert "unknown section" in msg
    assert "domein" not in (cockpit2._Stores(dd).att.get(a.id).meta or {})


def test_de_wijziging_komt_in_de_historie(tmp_path):
    """Waar een pagina in de navigatie hangt is een besluit; wie het veranderde hoort terug te
    lezen te zijn. Daarom `update()` en niet `set_meta()` — die laatste versiont bewust niet."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    _zet(dd, a.id, "finance")
    versies = cockpit2._Stores(dd).att.get(a.id).versions
    assert "sectie: Finance" in versies[-1]["change_note"]


def test_alleen_een_pagina(tmp_path):
    """Een policy of tool staat niet in deze navigatie-kolom als eigen pagina; de actie hoort daar
    dus niet op te werken."""
    dd, st, wie = _dorp(tmp_path)
    p = st.att.add(ROL, "policy", title="Beleid", body="x", domain=DOMEIN)
    _nxt, msg = _zet(dd, p.id, "finance", mail="houder@t.nl")
    assert "page not found" in msg


# ── 2. De poort ──────────────────────────────────────────────────────────────
def test_wie_het_domein_niet_mag_verzetten_mag_de_sectie_ook_niet(tmp_path):
    """GEEN KEUZE MAAR EEN NOODZAAK. De override WINT van het domein, dus een ruimere poort hier
    zou betekenen dat wie het domein niet mag verzetten de pagina alsnog ergens anders ophangt."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Met domein", body="x", domain=DOMEIN)
    with pytest.raises(cockpit2.Forbidden):
        _zet(dd, a.id, "finance", mail="buiten@t.nl")
    assert "domein" not in (cockpit2._Stores(dd).att.get(a.id).meta or {})


def test_zonder_domein_mag_elke_herkende_persoon(tmp_path):
    """Dezelfde regel als overal sinds de domein-gate: geen domein is open."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    _zet(dd, a.id, "finance", mail="buiten@t.nl")
    assert (cockpit2._Stores(dd).att.get(a.id).meta or {}).get("domein") == "finance"


def test_de_tak_benoemt_zijn_autorisatie():
    import inspect
    assert "AUTHZ:" in inspect.getsource(cockpit2._act_pagina_sectie)


# ── 3. Op het scherm ─────────────────────────────────────────────────────────
def test_de_voet_heeft_een_sectie_rij(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    html = render_pagina(st, a.id, csrf_token="T", username="buiten@t.nl")
    assert ">Section</span>" in html
    assert "value='pagina_sectie'" in html


def test_alle_elf_bakjes_staan_erin(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    veld = _sectie_form(a, "overig", "T", True, st=st, username="buiten@t.nl")
    for sleutel, _lbl in domeinen.BAKJES:
        assert f"value='{sleutel}'" in veld
    assert veld.count("<option") == len(domeinen.BAKJES) + 1, "de lege keuze ontbreekt of is dubbel"


def test_de_huidige_keuze_staat_voorgeselecteerd(tmp_path):
    """Zonder voorselectie zet elke bewerking de pagina terug op "afleiden" — een stille
    verhuizing bij een wijziging die er niets mee te maken had."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    st.att.update(a.id, meta={"domein": "finance"})
    veld = _sectie_form(st.att.get(a.id), "finance", "T", True, st=st, username="buiten@t.nl")
    assert "value='finance' selected" in veld


def test_wie_niet_mag_ziet_een_chip(tmp_path):
    """Een knop die de server daarna weigert, belooft iets wat niet kan."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Met domein", body="x", domain=DOMEIN)
    veld = _sectie_form(a, "shoe-development", "T", True, st=st, username="buiten@t.nl")
    assert "<form" not in veld and "Shoe development" in veld


def test_de_uitleg_zegt_of_hij_afgeleid_of_gezet_is(tmp_path):
    """Dat is het enige dat je hier moet weten: alleen een handmatige keuze blijft staan als
    governance iets herindeelt."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Met domein", body="x", domain=DOMEIN)
    assert "(derived)" in render_pagina(st, a.id, csrf_token="T", username="houder@t.nl")
    st.att.update(a.id, meta={"domein": "finance"})
    assert "(set here)" in render_pagina(st, a.id, csrf_token="T", username="houder@t.nl")


def test_domein_en_sectie_zijn_twee_verschillende_velden(tmp_path):
    """"Move page" blijft puur over het governance-domein gaan. Zou het één veld worden, dan
    verzet je met een navigatiekeuze stilzwijgend het eigenaarschap."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Met domein", body="x", domain=DOMEIN)
    html = render_pagina(st, a.id, csrf_token="T", username="houder@t.nl")
    assert "name='domain'" in html and "name='sectie'" in html
    assert "value='artefact_edit'" in html and "value='pagina_sectie'" in html


def test_bakje_van_is_niet_aangeraakt():
    """De afleiding zelf blijft ongewijzigd — dat werkte al. Deze stap voegt alleen het
    schrijfpad toe voor de override die stap 0 altijd al las."""
    import inspect
    src = inspect.getsource(domeinen.bakje_van)
    assert 'meta.get("domein")' in src and "override op de pagina" in src


def test_een_individuele_actie_is_ook_echt_te_bewerken(tmp_path):
    """GEVONDEN BIJ HET BOUWEN, en het is een gat dat #610 achterliet: `render_pagina` rekende
    `can_edit` nog uit met de ROL-regel (`eigenaar is not None and _can_edit_artefacts(...)`),
    terwijl de server sinds die PR op het DOMEIN gaat.

    Twee gevolgen. De verruiming was onzichtbaar — wie geen rolvervuller was mocht van de server
    een domeinloze pagina bewerken maar kreeg een read-only scherm. En `records.get("ii:…")` geeft
    None, dus een individuele actie was helemaal niet te bewerken: aanmaken kon, schrijven niet."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(II, "note", title="Individueel", body="x")
    html = render_pagina(st, a.id, csrf_token="T", username="buiten@t.nl")
    assert "id='wiki-form'" in html, "de pagina is niet te bewerken"


def test_het_scherm_en_de_server_geven_hetzelfde_antwoord(tmp_path):
    """Twee antwoorden op één vraag is precies waar `mag_schrijven_op_domein` voor op één plek
    staat. Deze toets legt de drie gevallen naast elkaar."""
    dd, st, wie = _dorp(tmp_path)
    gevallen = [
        (st.att.add(ROL, "note", title="Open", body="x"), True),
        (st.att.add(II, "note", title="Individueel", body="x"), True),
        (st.att.add(ROL, "note", title="Gesloten", body="x", domain=DOMEIN), False),
    ]
    for a, verwacht in gevallen:
        server = cockpit2._artefact_gate(a.anchor, "buiten@t.nl", st,
                                         domein=getattr(a, "domain", "")) is None
        scherm = "id='wiki-form'" in render_pagina(st, a.id, csrf_token="T",
                                                   username="buiten@t.nl")
        assert server == scherm == verwacht, f"{a.title}: server={server} scherm={scherm}"


# ── 4. De nieuwe-pagina-flow ─────────────────────────────────────────────────
def test_het_aanmaakformulier_vraagt_ook_naar_de_sectie(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    html = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    assert "name='sectie'" in html
    assert "3. Where in the navigation?" in html


def test_de_domeinvraag_gaat_nu_over_het_domein(tmp_path):
    """Twee velden die allebei "waar in de navigatie?" heten is één te veel."""
    dd, st, wie = _dorp(tmp_path)
    html = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    assert "2. Which domain?" in html
    assert html.count("Where in the navigation?") == 1


def test_een_individuele_actie_landt_waar_je_hem_zet(tmp_path):
    """END TO END, en dit is het geval waar de hele stap voor bestaat: geen rol, geen domein, dus
    zonder deze keuze belandt hij in Overig zonder dat iemand dat koos."""
    dd, st, wie = _dorp(tmp_path)
    cockpit2.dispatch(dd, "artefact_add",
                      {"csrf": ["T"], "owner": [II], "kind": ["note"], "title": ["Individueel"],
                       "sectie": ["finance"], "naar_pagina": ["1"], "next": ["/wiki"]},
                      username="buiten@t.nl")
    st2 = cockpit2._Stores(dd)
    a = next(x for x in st2.att.by_kind("note") if x.title == "Individueel")
    assert domeinen.bakje_van(a, st2.records.all())[0] == "finance"


def test_zonder_sectie_verandert_er_niets_aan_het_aanmaken(tmp_path):
    """Bij een gewone rol volgt de sectie vanzelf uit het domein; dan hoort dit veld niets te
    doen."""
    dd, st, wie = _dorp(tmp_path)
    cockpit2.dispatch(dd, "artefact_add",
                      {"csrf": ["T"], "owner": [ROL], "kind": ["note"], "title": ["Gewoon"],
                       "next": ["/"]}, username="buiten@t.nl")
    st2 = cockpit2._Stores(dd)
    a = next(x for x in st2.att.by_kind("note") if x.title == "Gewoon")
    assert "domein" not in (a.meta or {})
    assert domeinen.bakje_van(a, st2.records.all())[0] == "shoe-development"


def test_een_verzonnen_sectie_bij_het_aanmaken_wordt_geweigerd(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    _nxt, msg = cockpit2.dispatch(dd, "artefact_add",
                                  {"csrf": ["T"], "owner": [II], "kind": ["note"],
                                   "title": ["Fout"], "sectie": ["verzonnen"], "next": ["/"]},
                                  username="buiten@t.nl")
    assert "unknown section" in msg
    assert not any(x.title == "Fout" for x in cockpit2._Stores(dd).att.by_kind("note"))
