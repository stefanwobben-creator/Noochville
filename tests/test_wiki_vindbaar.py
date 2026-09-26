"""Wiki brok 3 — vindbaar voor de mens, leesbaar voor de AI.

Twee oppervlakken, één bron. De globale zoek krijgt een groep Pages (die ook de FEITEN doorzoekt,
want daar zoek je op), en `/context` — de systeemprompt van een AI-vervuller — draagt de feiten mét
hun grond, live bepaald. Zonder dat laatste zou een inwoner een feit kunnen citeren zonder te zien
dat het certificaat eronder verlopen is.
"""
from __future__ import annotations

from nooch_village import artefacts, cert_register, cockpit2, wiki
from nooch_village.views.search import render_search

OWNER = "mother_earth__nooch__creator_of_shoes"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _cert(st, geldig_tot):
    return st.evidence.record(role_id="compliance", skill=cert_register.SKILL, query="vegan",
                              source=cert_register.EXTERN, status="bevestigd",
                              meta={"feit": "vegan", "instantie": "PETA",
                                    "geldig_tot": geldig_tot, "claims": ["vegan"]})


# ── zoeken ──────────────────────────────────────────────────────────────────

def test_zoek_vindt_pagina_op_titel_tekst_en_feit(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="HyphaLite", body="Mycelium-gebaseerd bovenmateriaal.")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Geteeld door Ecovative in de VS")]})
    st2 = cockpit2._Stores(st.dd)

    for term in ("hyphalite", "mycelium", "ecovative"):
        html = render_search(st2, term)
        assert "Pages" in html, term
        assert f"/pagina?id={a.id}" in html, term
        assert "gs-page" in html, term                 # eigen categorie-badge, niet als 'signal'


def test_zoek_vindt_geen_pagina_die_er_niet_is(tmp_path):
    st = _stores(tmp_path)
    st.att.add(OWNER, "note", title="HyphaLite", body="tekst")
    html = render_search(cockpit2._Stores(st.dd), "polyurethaan")
    assert "/pagina?id=" not in html


def test_gearchiveerde_pagina_is_niet_vindbaar(tmp_path):
    st = _stores(tmp_path)
    a = st.att.add(OWNER, "note", title="HyphaLite", body="tekst")
    st.att.archive(a.id)
    html = render_search(cockpit2._Stores(st.dd), "hyphalite")
    assert f"/pagina?id={a.id}" not in html


# ── /context: de systeemprompt van een AI-vervuller ─────────────────────────

def test_context_draagt_de_feiten_met_hun_grond(tmp_path):
    st = _stores(tmp_path)
    r = _cert(st, "2030-01-01")
    a = st.att.add(OWNER, "note", title="HyphaLite", body="Mycelium.")
    st.att.update(a.id, meta={"feiten": [
        wiki.maak_feit("Vegan gecertificeerd", soort="cert", ref=r["id"]),
        wiki.maak_feit("Voelt zacht aan")]})
    st2 = cockpit2._Stores(st.dd)

    ctx = artefacts.serialize_context(OWNER, st2.records, st2.att, st2.evidence)
    feiten = ctx["notes"]["own"][0]["feiten"]
    assert [f["grond"] for f in feiten] == [wiki.GEGROND, wiki.ONGEGROND]
    assert "PETA" in feiten[0]["grond_label"]

    md = artefacts.render_context_markdown(ctx)
    assert f"`{a.id}`" in md                            # citeerbaar id, niet alleen de titel
    assert "✓ Vegan gecertificeerd — PETA" in md
    assert "— Voelt zacht aan — ungrounded" in md       # ongegrond zegt het ook in de prompt


def test_context_toont_een_verlopen_certificaat_als_vervallen(tmp_path):
    st = _stores(tmp_path)
    r = _cert(st, "2024-05-01")
    a = st.att.add(OWNER, "note", title="HyphaLite")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Vegan", soort="cert", ref=r["id"])]})
    st2 = cockpit2._Stores(st.dd)
    md = artefacts.render_context_markdown(
        artefacts.serialize_context(OWNER, st2.records, st2.att, st2.evidence))
    assert "⌛ Vegan — PETA — expired 2024-05-01" in md


def test_context_zonder_kroniek_doet_niet_alsof_het_klopt(tmp_path):
    # Fail-closed: geen ledger = niets te controleren, dus 'ontbreekt' — nooit stilzwijgend gegrond.
    st = _stores(tmp_path)
    r = _cert(st, "2030-01-01")
    a = st.att.add(OWNER, "note", title="HyphaLite")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Vegan", soort="cert", ref=r["id"])]})
    st2 = cockpit2._Stores(st.dd)
    ctx = artefacts.serialize_context(OWNER, st2.records, st2.att)     # géén ledger
    assert ctx["notes"]["own"][0]["feiten"][0]["grond"] == wiki.ONTBREEKT


def test_context_endpoint_geeft_de_feiten_mee(tmp_path):
    st = _stores(tmp_path)
    r = _cert(st, "2030-01-01")
    a = st.att.add(OWNER, "note", title="HyphaLite")
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Vegan", soort="cert", ref=r["id"])]})
    st2 = cockpit2._Stores(st.dd)

    status, ctype, body = cockpit2.role_context(st2, OWNER, "markdown")
    assert status == 200 and "✓ Vegan — PETA — valid until 2030-01-01" in body
    status, ctype, body = cockpit2.role_context(st2, OWNER, "json")
    assert status == 200 and '"grond": "gegrond"' in body


def test_policies_en_tools_veranderen_niet(tmp_path):
    # Alleen notes zijn pagina's; een policy of tool krijgt geen feiten-veld aangenaaid.
    st = _stores(tmp_path)
    st.att.add(OWNER, "policy", title="Alleen plantaardig", domain="Materials")
    st.att.add(OWNER, "tool", title="Stuklijst", url="https://voorbeeld.nl")
    st2 = cockpit2._Stores(st.dd)
    ctx = artefacts.serialize_context(OWNER, st2.records, st2.att, st2.evidence)
    assert "feiten" not in ctx["policies"]["own"][0]
    assert "feiten" not in ctx["tools"]["own"][0]

# ── de bewerkknop (21 september 2026) ────────────────────────────────────────
#
# WAT ER MIS WAS, en het was geen ontbrekende functie maar een onvindbare: bewerken kon al, via een
# klein grijs "edit"-linkje ÓNDER de hele pagina-inhoud, plus een klik op de tekst zelf die nergens
# werd aangekondigd. Wie niet wist dat de tekst klikbaar was, vond de bewerkmogelijkheid niet.
# Eén zichtbare knop bovenaan erbij — dezelfde `<details>`, dezelfde ene `artefact_edit`-actie.

def _pagina_html(tmp_path, can_edit=True):
    from nooch_village import cockpit2, wiki
    from nooch_village.views.wiki import render_pagina
    dd = str(tmp_path)
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    a = st.att.add(rol, wiki.PAGINA_KIND, title="Testpagina", body="Wat tekst.")
    mens = st.people.add("Beheerder", "b@t.nl")
    if can_edit:
        st.assign.assign(rol, "person", mens.id)
    return render_pagina(st, a.id, csrf_token="TOK",
                         username="b@t.nl" if can_edit else "")


def test_bewerken_hoeft_niet_meer_gevonden_te_worden(tmp_path):
    """DE VRAAG VAN DIT BESTAND WAS "IS DE BEWERKKNOP VINDBAAR?" — en die is op 26 september
    vervallen, niet beantwoord.

    De geschiedenis erachter staat in de docstring die hier stond: eerst opende een klein grijs
    tekstlinkje ónder de inhoud een formulier, toen werd het een knop bóven de tekst. Sinds
    bewerken de stand is voor wie mag bewerken, is er niets meer te vinden: je opent de pagina en
    typt, zoals in een tekstverwerker. Een knop die niet bestaat, kan ook niet onvindbaar zijn.

    Wat blijft te bewaken is het gevolg: het bewerkvlak staat er meteen, en het staat er alleen
    voor wie mag."""
    html = _pagina_html(tmp_path)
    assert "data-wiki-start" not in html, "de Edit page-knop is terug"
    assert "contenteditable" in html or "wiki-form" in html, "er is geen bewerkvlak"
    assert html.index("wiki-form") > html.index("att-body"), \
        "de opslaan-balk hoort onder de tekst te staan, niet ervoor"


def test_wie_niet_mag_bewerken_krijgt_geen_bewerkvlak(tmp_path):
    """Een poort die pas ná de belofte weigert, is geen poort. Zonder bewerkrecht rendert de
    server geen formulier — en zonder dat formulier zet `nooch.js` niets aan."""
    html = _pagina_html(tmp_path, can_edit=False)
    assert "data-wiki-start" not in html
    assert "contenteditable" not in html and "wiki-form" not in html


def test_er_is_maar_een_plek_waar_de_tekst_staat(tmp_path):
    """DIT IS DE KERN VAN DE VERVANGING. Het oude model zette de opgemaakte tekst bovenaan en het
    bewerkformulier — met dezelfde tekst als ruwe markdown — eronder. Twee kopieën op één scherm,
    en typen op een andere plek dan waar je leest.

    Nu staat de tekst één keer op de pagina en wordt hij daar bewerkbaar. Het formulier dat
    overblijft draagt geen inhoud, alleen de opslaan-balk en de verborgen velden."""
    html = _pagina_html(tmp_path)
    assert html.count("value='artefact_edit'") == 1        # nog steeds één opslagpad
    assert html.count("Wat tekst.") == 1                   # en één kopie van de inhoud
    # Het Facts-formulier heeft nog wél een textarea (voor een citaat) en dat hoort zo: de
    # Facts-sectie blijft ongewijzigd. Wat weg moest is het BODY-vak met de ruwe markdown.
    assert "name='body'" not in html and 'name="body"' not in html
    assert "data-qadd-inline" not in html                  # het oude formulier is weg
    assert "wiki-form" in html and "body_html" in html     # wat ervoor in de plaats kwam


def test_de_editor_is_bedraad_in_het_gedeelde_bestand():
    """In `nooch.js` en niet als inline script: de pagina wordt ook als fragment geladen, en een
    script uit innerHTML draait nooit (de les van de checklist-microinteractie, één dag eerder).

    HET HAAKJE HEET ANDERS sinds de openknop verviel: `#wiki-form` is nu én de aanhechting én de
    poort."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    assert "#wiki-form" in js and "contentEditable" in js
