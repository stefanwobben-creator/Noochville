"""Het bewerkrecht hangt aan het DOMEIN, en een pagina begint in de wiki (26 september 2026).

Twee samenhangende wijzigingen:

1. `_artefact_gate` vroeg "vervul jij de eigenaar-rol?". Dat betekende dat je een mandaat moest
   hebben om een aantekening te maken. Hij vraagt nu "mag jij op dit domein schrijven?" — geen
   domein is open, een domein met een aangewezen eigenaar is dat niet.
2. Een pagina starten kon alleen vanuit de cockpit van een rol, achter de poort van díé rol. Je
   moest dus eerst weten bij wie iets hoorde vóór je het kon opschrijven.

WAT NIET MEEVERHUIST: `_act_artefact_delete` blijft Circle-Lead-only, ongeacht domein. Weggooien
is onomkeerbaar en dat is een andere vraag dan schrijven.
"""
from __future__ import annotations

import pytest

from nooch_village import artefacts, cockpit2, triage_rol, wiki
from nooch_village.views.wiki import _nieuwe_pagina_form, render_wiki_index

#: `creator_of_shoes` houdt `Materials` in de bootstrap, en als enige — geverifieerd met
#: `domein_eigenaar` in de opstelling hieronder, want een tweede houder maakt de poort fail-open
#: en dan slaagt elke "mag niet"-toets om de verkeerde reden.
ROL = "mother_earth__nooch__creator_of_shoes"
DOMEIN = "Materials"
CIRKEL = "mother_earth__nooch"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    houder = st.people.add("Houder", "houder@t.nl")
    lead = st.people.add("Lead", "lead@t.nl")
    buiten = st.people.add("Buiten", "buiten@t.nl")
    st.assign.assign(ROL, "person", houder.id)
    st.assign.assign(f"{CIRKEL}__circle_lead", "person", lead.id)
    assert triage_rol.domein_eigenaar(st, DOMEIN)["rol"] == ROL, "de opstelling klopt niet"
    return dd, st, {"houder": houder, "lead": lead, "buiten": buiten}


def _edit(dd, aid, tekst, mail):
    return cockpit2.dispatch(dd, "artefact_edit",
                             {"csrf": ["T"], "aid": [aid], "body": [tekst], "next": ["/"]},
                             username=mail)


# ── 1. De poort hangt aan het domein ─────────────────────────────────────────
def test_zonder_domein_mag_elke_herkende_persoon_bewerken(tmp_path):
    """DE VERRUIMING. Een pagina die over niets in het bijzonder gaat, hoort geen mandaat te
    vereisen om iets aan toe te voegen."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Losse aantekening", body="oud")
    _edit(dd, a.id, "van een buitenstaander", "buiten@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "van een buitenstaander"


def test_zonder_domein_mag_hij_er_ook_een_aanmaken(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    cockpit2.dispatch(dd, "artefact_add",
                      {"csrf": ["T"], "owner": [ROL], "kind": ["note"],
                       "title": ["Van buiten"], "next": ["/"]}, username="buiten@t.nl")
    st2 = cockpit2._Stores(dd)
    assert any(a.title == "Van buiten" for a in st2.att.by_kind("note"))


def test_een_tool_zonder_domein_ook(tmp_path):
    """De poort staat op `_artefact_gate` en dus op elke artefact-soort, niet alleen op notes."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title="Een tool", url="https://x.nl")
    _edit(dd, a.id, "bijgewerkt", "buiten@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "bijgewerkt"


def test_met_domein_mag_een_buitenstaander_niet_bewerken(tmp_path):
    """Wat je wél beschermt is een DOMEIN: dat is een verklaring dat een rol dit onderwerp bezit,
    en wie daarin schrijft raakt iets wat een ander in beheer heeft."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Materiaalpagina", body="oud", domain=DOMEIN)
    with pytest.raises(cockpit2.Forbidden):
        _edit(dd, a.id, "stiekem", "buiten@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "oud"


def test_met_domein_mag_de_houder_wel(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Materiaalpagina", body="oud", domain=DOMEIN)
    _edit(dd, a.id, "door de houder", "houder@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "door de houder"


def test_met_domein_mag_de_circle_lead_ook(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Materiaalpagina", body="oud", domain=DOMEIN)
    _edit(dd, a.id, "door de lead", "lead@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "door de lead"


def test_aanmaken_op_andermans_domein_mag_niet(tmp_path):
    """DE REGEL GELDT AL VOOR HET ARTEFACT BESTAAT — op het domein dat in het aanmaakformulier
    gekozen wordt. Anders maak je hem domeinloos aan en hangt hij er daarna alsnog in."""
    dd, st, wie = _dorp(tmp_path)
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "artefact_add",
                          {"csrf": ["T"], "owner": [ROL], "kind": ["note"],
                           "title": ["Insluiper"], "domain": [DOMEIN], "next": ["/"]},
                          username="buiten@t.nl")
    assert not any(a.title == "Insluiper" for a in cockpit2._Stores(dd).att.by_kind("note"))


def test_de_poort_draait_na_de_domeinkeuze(tmp_path):
    """DE VAL BIJ HET BOUWEN: de poort stond vóór de regels die het domein uitlezen, dus hij zou
    altijd de "geen domein"-tak nemen — oftewel iedereen mag alles aanmaken. De toets hierboven
    vangt dat, deze legt de reden vast."""
    import inspect
    src = inspect.getsource(cockpit2._act_artefact_add)
    assert src.index('g("domain")') < src.index("_artefact_gate(")


def test_een_configuratiefout_sluit_niemand_buiten(tmp_path):
    """`domein_eigenaar` geeft een lege rol terug als niemand het domein houdt, of twee rollen het
    allebei houden. Dat zijn fouten in de governance-administratie en die horen daar opgelost te
    worden — niet doordat een pagina stilzwijgend op slot gaat en niemand meer weet waarom."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Zwevend", body="oud", domain="bestaat-niet")
    assert triage_rol.domein_eigenaar(st, "bestaat-niet")["rol"] == ""
    _edit(dd, a.id, "toch bewerkt", "buiten@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "toch bewerkt"


def test_twee_houders_ook(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    tweede = st.records.get("mother_earth__nooch__compliance")
    tweede.definition.domains = list(tweede.definition.domains) + [DOMEIN]
    st.records.put(tweede)
    st2 = cockpit2._Stores(dd)
    assert triage_rol.domein_eigenaar(st2, DOMEIN)["rol"] == "", "de opstelling klopt niet"
    a = st2.att.add(ROL, "note", title="Betwist", body="oud", domain=DOMEIN)
    _edit(dd, a.id, "toch bewerkt", "buiten@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "toch bewerkt"


def test_een_onbekende_gebruiker_mag_nog_steeds_niets(tmp_path):
    """De verruiming is "elke HERKENDE persoon", niet "iedereen". Een naam die het dorp niet kent
    is geen persoon."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Losse aantekening", body="oud")
    with pytest.raises(cockpit2.Forbidden):
        _edit(dd, a.id, "stiekem", "niemand@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "oud"


def test_de_regel_staat_op_een_plek(tmp_path):
    """`_domein_form` in de wiki stelt dezelfde vraag over hetzelfde domein. Twee kopieën zouden na
    één wijziging uiteenlopen, en dan geeft het scherm een ander antwoord dan de server."""
    import inspect
    from nooch_village.views import wiki as vw
    assert "mag_schrijven_op_domein" in inspect.getsource(cockpit2._artefact_gate)
    assert "mag_schrijven_op_domein" in inspect.getsource(vw._mag_domein_wijzigen)


# ── 2. Verwijderen blijft ongemoeid ──────────────────────────────────────────
def test_verwijderen_blijft_circle_lead_only_ook_zonder_domein(tmp_path):
    """Weggooien is onomkeerbaar; dat is een andere vraag dan schrijven. Zou delete meeliften op
    de verruiming, dan kan elke ingelogde elke domeinloze pagina definitief wissen."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Weg?", body="x")
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "artefact_delete",
                          {"csrf": ["T"], "aid": [a.id], "next": ["/"]}, username="buiten@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id) is not None


def test_de_houder_van_het_domein_mag_ook_niet_verwijderen(tmp_path):
    """Schrijven en weggooien zijn twee verschillende rechten; de domeinhouder heeft alleen het
    eerste."""
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Weg?", body="x", domain=DOMEIN)
    with pytest.raises(cockpit2.Forbidden):
        cockpit2.dispatch(dd, "artefact_delete",
                          {"csrf": ["T"], "aid": [a.id], "next": ["/"]}, username="houder@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id) is not None


def test_de_circle_lead_mag_wel_verwijderen(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(ROL, "note", title="Weg?", body="x")
    cockpit2.dispatch(dd, "artefact_delete",
                      {"csrf": ["T"], "aid": [a.id], "next": ["/"]}, username="lead@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id) is None


# ── 3. Nieuwe pagina vanuit de wiki ──────────────────────────────────────────
def test_de_index_heeft_een_knop(tmp_path):
    dd, st, wie = _dorp(tmp_path)
    html = render_wiki_index(st, csrf_token="T", username="buiten@t.nl")
    assert "+ New page" in html and "value='artefact_add'" in html


def test_de_knop_vraagt_eerst_van_wie_en_dan_waar(tmp_path):
    """Twee stappen, in de volgorde waarin je ze beantwoordt."""
    dd, st, wie = _dorp(tmp_path)
    html = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    # DRIE STAPPEN SINDS DE SECTIE-KEUZE ERBIJ KWAM: van wie, welk domein, waar in de navigatie.
    # Die laatste twee zijn niet hetzelfde — met een domein volgt de sectie vanzelf, en bij een
    # individuele actie is er geen domein om hem uit af te leiden.
    assert (html.index("1. Whose is this?") < html.index("2. Which domain?")
            < html.index("3. Where in the navigation?"))
    assert "name='owner'" in html and "name='domain'" in html and "name='sectie'" in html


def test_stap_1_biedt_individuele_actie_aan(tmp_path):
    """Het bestaande `ii:<cirkel>`-patroon uit de projectwizard, geen nieuwe eigenaarsoort."""
    from nooch_village.views.wizard import II_PREFIX
    dd, st, wie = _dorp(tmp_path)
    html = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    assert f"value='{II_PREFIX}{CIRKEL}'" in html


def test_policy_wordt_hier_niet_aangeboden(tmp_path):
    """EEN KEUZE, met reden. Een policy is geen pagina die je schrijft maar een REGEL op een domein
    dat een rol via governance bezit: `_act_artefact_add` eist dat het gekozen domein in
    `definition.domains` van de eigenaar-rol staat. Een individuele actie heeft die rol niet, en
    bij een gewone rol zou stap 2 (alle domeinen van het dorp) botsen met de lijst waarop de server
    toetst (alleen die van de rol) — dan bied je een keuze aan die daarna wordt geweigerd."""
    dd, st, wie = _dorp(tmp_path)
    html = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    assert "value='policy'" not in html
    assert "value='note'" in html and "value='tool'" in html


def test_stap_2_toont_alleen_domeinen_waar_je_op_mag(tmp_path):
    """Een domein aanbieden en daarna weigeren is een knop die niet doet wat hij belooft."""
    dd, st, wie = _dorp(tmp_path)
    buiten = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    houder = _nieuwe_pagina_form(st, "T", "houder@t.nl")
    assert f"value='{DOMEIN}'" not in buiten
    assert f"value='{DOMEIN}'" in houder


def test_wat_ontbreekt_krijgt_een_reden(tmp_path):
    """Stilzwijgend een kortere lijst tonen laat je zoeken naar iets dat er hoort te zijn."""
    dd, st, wie = _dorp(tmp_path)
    html = _nieuwe_pagina_form(st, "T", "buiten@t.nl")
    assert "another role owns them" in html


def test_de_domeinlijst_komt_uit_governance(tmp_path):
    """ÉÉN BRON voor de keuzelijst én de controle op de server. Zou de server een andere lijst
    hanteren dan het formulier aanbiedt, dan is er een keuze die daarna wordt geweigerd."""
    dd, st, wie = _dorp(tmp_path)
    assert DOMEIN in artefacts.alle_domeinen(st.records)
    import inspect
    assert "alle_domeinen" in inspect.getsource(cockpit2._act_artefact_add)


def test_een_verzonnen_domein_wordt_geweigerd(tmp_path):
    """De server vertrouwt het formulier niet; een typefout hoort geen pagina op een niet-bestaand
    domein op te leveren."""
    dd, st, wie = _dorp(tmp_path)
    _nxt, msg = cockpit2.dispatch(dd, "artefact_add",
                                  {"csrf": ["T"], "owner": [ROL], "kind": ["note"],
                                   "title": ["Verzonnen"], "domain": ["niet-bestaand"],
                                   "next": ["/"]}, username="buiten@t.nl")
    assert "governance actually assigned" in msg
    assert not any(a.title == "Verzonnen" for a in cockpit2._Stores(dd).att.by_kind("note"))


def test_de_individuele_actie_flow_van_begin_tot_eind(tmp_path):
    """END TO END: aanmaken zonder rol, en daarna door iedereen te bewerken — want geen domein."""
    from nooch_village.views.wizard import II_PREFIX
    dd, st, wie = _dorp(tmp_path)
    nxt, _msg = cockpit2.dispatch(dd, "artefact_add",
                                  {"csrf": ["T"], "owner": [f"{II_PREFIX}{CIRKEL}"],
                                   "kind": ["note"], "title": ["Individueel"],
                                   "naar_pagina": ["1"], "next": ["/wiki"]},
                                  username="buiten@t.nl")
    st2 = cockpit2._Stores(dd)
    a = next(x for x in st2.att.by_kind("note") if x.title == "Individueel")
    assert a.anchor == f"{II_PREFIX}{CIRKEL}"
    assert nxt == wiki.pagina_url(a.id), "je landt niet op de nieuwe pagina"
    _edit(dd, a.id, "door een ander", "houder@t.nl")
    assert cockpit2._Stores(dd).att.get(a.id).body == "door een ander"


def test_een_ii_pagina_laat_niets_crashen(tmp_path):
    """`records.get("ii:…")` geeft None. Alles wat de eigenaar opzoekt moet daar tegen kunnen —
    zelfde geest als hoe projects.py dat al doet voor `ii:`-projecten."""
    from nooch_village.views.wizard import II_PREFIX
    from nooch_village.views.wiki import render_pagina
    dd, st, wie = _dorp(tmp_path)
    a = st.att.add(f"{II_PREFIX}{CIRKEL}", "note", title="Individueel", body="x")
    assert artefacts.erfketen(a.anchor, True, st.records) == [a.anchor]
    assert render_wiki_index(st, csrf_token="T", username="houder@t.nl")
    html = render_pagina(st, a.id, csrf_token="T", username="houder@t.nl")
    assert "Individueel" in html


def test_zonder_schrijfsessie_geen_knop(tmp_path):
    """Geen csrf-token = geen schrijf-sessie (publieke view), dus ook geen aanmaakformulier."""
    dd, st, wie = _dorp(tmp_path)
    assert _nieuwe_pagina_form(st, "", "buiten@t.nl") == ""


def test_een_onbekende_naam_krijgt_geen_knop(tmp_path):
    """De poort staat vóór de belofte: wie de server niet kent, mag straks toch niets."""
    dd, st, wie = _dorp(tmp_path)
    assert _nieuwe_pagina_form(st, "T", "niemand@t.nl") == ""
