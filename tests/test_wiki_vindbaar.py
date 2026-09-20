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


def test_de_bewerkknop_staat_bovenaan_en_is_zichtbaar(tmp_path):
    html = _pagina_html(tmp_path)
    assert "data-qadd-opener" in html, "er hoort een expliciete bewerkknop te staan"
    assert "Edit page" in html
    # BOVENAAN: vóór de inhoud, niet eronder. Dat was precies het probleem.
    assert html.index("data-qadd-opener") < html.index("att-body"), "de knop staat onder de tekst"
    assert "btn" in html.split("data-qadd-opener")[0][-120:], "de knop draagt het knop-atoom"


def test_wie_niet_mag_bewerken_krijgt_geen_knop(tmp_path):
    """Een knop die een poort daarna weigert, belooft iets wat niet kan."""
    html = _pagina_html(tmp_path, can_edit=False)
    assert "data-qadd-opener" not in html


def test_de_knop_opent_hetzelfde_formulier_als_de_tekst(tmp_path):
    """Eén formulier, één submit, één `artefact_edit`. De knop is een tweede INGANG, geen tweede
    opslagpad — anders ontstaat er een tweede waarheid over wat er is opgeslagen."""
    html = _pagina_html(tmp_path)
    assert html.count("value='artefact_edit'") == 1
    assert "data-qadd-inline" in html           # het bestaande formulier
    assert "data-qadd-open" in html             # en de tekst blijft ook klikbaar


def test_de_opener_is_bedraad_in_het_gedeelde_bestand():
    """In `nooch.js` en niet als inline script: de pagina wordt ook als fragment geladen, en een
    script uit innerHTML draait nooit (de les van de checklist-microinteractie, één dag eerder)."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text()
    assert "data-qadd-opener" in js and "scrollIntoView" in js
