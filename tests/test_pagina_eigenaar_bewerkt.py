"""De eigenaar bewerkt zijn eigen pagina direct; ieder ander stelt voor.

AUTHZ: rolvervuller of Circle Lead bewerkt inline, niet-eigenaar loopt langs het voorstelpad.
Dat is `artefacts.can_write_artefact` — deze tests bewaken dat het scherm die poort ook echt
weerspiegelt, op de permalink én op de Notes-tab van de rol.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.overview import _artefact_tab_html
from nooch_village.views.wiki import render_pagina

OWNER = "mother_earth__nooch__creator_of_shoes"
ANDERE = "mother_earth__nooch__marketing_lead"
CIRCLE = "mother_earth__nooch"
LEAD = "mother_earth__nooch__circle_lead"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _mens(st, naam, email, rol):
    p = st.people.add(naam, email=email)
    st.assign.assign(rol, "person", p.id)
    return p


def _pagina(st):
    return st.att.add(OWNER, "note", title="Hennepvezel", body="wat wij weten over hennep")


# ── de permalink ────────────────────────────────────────────────────────────

def test_eigenaar_bewerkt_direct_op_de_pagina(tmp_path):
    dd, st = _st(tmp_path)
    _mens(st, "Eigenaar", "eig@x.nl", OWNER)
    a = _pagina(st)
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="eig@x.nl")
    assert "value='artefact_edit'" in html            # het bewerkformulier staat er
    assert "value='pagina_voorstel'" not in html      # en niet óók het voorstelpad


def test_circle_lead_bewerkt_ook_direct(tmp_path):
    """Holacracy: de Circle Lead mag in het domein van een rol in zijn cirkel schrijven."""
    dd, st = _st(tmp_path)
    _mens(st, "Lead", "lead@x.nl", LEAD)
    a = _pagina(st)
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="lead@x.nl")
    assert "value='artefact_edit'" in html


def test_niet_eigenaar_krijgt_het_voorstelpad(tmp_path):
    dd, st = _st(tmp_path)
    _mens(st, "Ander", "ander@x.nl", ANDERE)
    a = _pagina(st)
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="t", username="ander@x.nl")
    assert "value='pagina_voorstel'" in html
    assert "value='artefact_edit'" not in html


def test_zonder_schrijfsessie_geen_van_beide(tmp_path):
    """Geen csrf = geen schrijf-sessie. Fail-closed: lezen mag, schrijven en voorstellen niet."""
    dd, st = _st(tmp_path)
    a = _pagina(st)
    html = render_pagina(cockpit2._Stores(dd), a.id, csrf_token="", username=None)
    assert "value='artefact_edit'" not in html and "value='pagina_voorstel'" not in html


# ── de Notes-tab van de rol ─────────────────────────────────────────────────

def test_notes_tab_eigenaar_bewerkt_daar_ook(tmp_path):
    dd, st = _st(tmp_path)
    _mens(st, "Eigenaar", "eig@x.nl", OWNER)
    _pagina(st)
    st2 = cockpit2._Stores(dd)
    html = _artefact_tab_html(st2, st2.records.get(OWNER), "note", "t", "eig@x.nl",
                              titel="Notes", leeg="geen")
    assert "value='artefact_edit'" in html
    assert "value='pagina_voorstel'" not in html


def test_notes_tab_niet_eigenaar_kan_nu_ook_voorstellen(tmp_path):
    """Het gat: op de permalink kon een niet-eigenaar al iets voorstellen, op deze tab zag hij
    alleen tekst — zonder enige weg om te zeggen dat er iets niet klopt."""
    dd, st = _st(tmp_path)
    _mens(st, "Ander", "ander@x.nl", ANDERE)
    _pagina(st)
    st2 = cockpit2._Stores(dd)
    html = _artefact_tab_html(st2, st2.records.get(OWNER), "note", "t", "ander@x.nl",
                              titel="Notes", leeg="geen")
    assert "value='pagina_voorstel'" in html
    assert "value='artefact_edit'" not in html


def test_twee_paginas_krijgen_eigen_veld_ids(tmp_path):
    """Twee velden met dezelfde id laten elke <label for> naar de eerste wijzen."""
    dd, st = _st(tmp_path)
    _mens(st, "Ander", "ander@x.nl", ANDERE)
    a = st.att.add(OWNER, "note", title="Een", body="x")
    b = st.att.add(OWNER, "note", title="Twee", body="y")
    st2 = cockpit2._Stores(dd)
    html = _artefact_tab_html(st2, st2.records.get(OWNER), "note", "t", "ander@x.nl",
                              titel="Notes", leeg="geen")
    assert f"vst-waarom-{a.id}" in html and f"vst-waarom-{b.id}" in html


def test_een_policy_krijgt_geen_voorstelpad(tmp_path):
    """Het voorstelpad hoort bij een pagina. Een policy is governance-eigendom en heeft zijn eigen
    route; er hoort hier geen knop te staan die dat suggereert."""
    dd, st = _st(tmp_path)
    _mens(st, "Ander", "ander@x.nl", ANDERE)
    st.att.add(OWNER, "policy", title="Regel", body="mits")
    st2 = cockpit2._Stores(dd)
    html = _artefact_tab_html(st2, st2.records.get(OWNER), "policy", "t", "ander@x.nl",
                              titel="Policies", leeg="geen")
    assert "value='pagina_voorstel'" not in html
