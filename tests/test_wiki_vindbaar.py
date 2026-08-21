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
