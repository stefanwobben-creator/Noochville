"""Projectbeheer-functionaliteit in cockpit2: trekker wijzigen, owner verplaatsen,
draft goed/afkeuren, wees-projecten zichtbaar maken. Thread-vrij, via dispatch + render."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import projects as P

ROLE   = "mother_earth__nooch__website_developer"
ROLE2  = "mother_earth__nooch__brand_visual_designer"
CIRCLE = "mother_earth__nooch"
ROOT   = "mother_earth"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


# ── trekker (persoon) wijzigen ───────────────────────────────────────────────

def test_proj_settrekker_wijzigt_persoon(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    person = st.people.all()[0]
    cockpit2.dispatch(dd, "proj_settrekker", {"pid": [pid], "trekker": [f"person:{person.id}"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["person"] == person.id


def test_detail_modal_heeft_trekker_form_in_schrijfmodus(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    rw = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    ro = P.render_project(cockpit2._Stores(dd), pid, csrf_token="")
    assert "proj_settrekker" in rw and "name='trekker'" in rw
    assert "proj_settrekker" not in ro            # read-only: geen formulier


# ── owner-rol verplaatsen ────────────────────────────────────────────────────

def test_proj_setowner_verplaatst_naar_andere_rol(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [ROLE2], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["owner"] == ROLE2


def test_proj_setowner_weigert_cirkel(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    _, msg = cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [CIRCLE], "next": ["/"]}, username="guest")
    assert "cirkel" in msg
    assert cockpit2._Stores(dd).projects.get(pid)["owner"] == ROLE   # ongewijzigd


def test_proj_setowner_weigert_onbekende_rol(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    _, msg = cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": ["nietbestaand"], "next": ["/"]}, username="guest")
    assert "onbekende" in msg
    assert cockpit2._Stores(dd).projects.get(pid)["owner"] == ROLE


def test_owner_options_sluit_cirkels_uit(tmp_path):
    dd, st = _st(tmp_path)
    opts = P._owner_options(st)
    assert f"value='{ROLE}'" in opts
    assert f"value='{CIRCLE}'" not in opts          # cirkels doen geen uitvoerend werk


def test_owner_options_toont_dangling_sentinel(tmp_path):
    dd, st = _st(tmp_path)
    opts = P._owner_options(st, sel_owner="ghost_role")
    assert "bestaat niet meer" in opts and "ghost_role" in opts


# ── draft-afhandeling ────────────────────────────────────────────────────────

def test_proj_approve_zet_draft_op_bord(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Concept", "human", status="draft")
    cockpit2.dispatch(dd, "proj_approve", {"pid": [pid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "queued"


def test_proj_discard_verwijdert_draft(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Concept", "human", status="draft")
    cockpit2.dispatch(dd, "proj_discard", {"pid": [pid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid) is None


def test_draft_sectie_zichtbaar_met_knoppen(tmp_path):
    dd, st = _st(tmp_path)
    st.projects.create(ROLE, "Concept idee", "human", status="draft")
    html = P._projects_tab_html(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROLE),
                                csrf_token="TOK", add=True)
    assert "Concepten" in html and "proj_approve" in html and "proj_discard" in html


def test_draft_telt_niet_mee_in_bord_aantal(tmp_path):
    dd, st = _st(tmp_path)
    st.projects.create(ROLE, "Op bord", "human", status="queued")
    st.projects.create(ROLE, "Concept", "human", status="draft")
    html = P._projects_tab_html(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROLE),
                                csrf_token="TOK", add=True)
    assert "Projecten (1)" in html             # alleen het niet-draft project


# ── wees-projecten (dangling owner) zichtbaar maken ──────────────────────────

def _make_orphan(dd, st):
    pid = st.projects.create(ROLE, "Wees project", "human", status="queued")
    st.projects.edit(pid, owner="ghost_role", allow_done=True)
    return pid


def test_wees_sectie_op_wortelcirkel(tmp_path):
    dd, st = _st(tmp_path)
    _make_orphan(dd, st)
    html = P._projects_tab_html(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROOT),
                                csrf_token="TOK", add=True)
    assert "Wees-projecten" in html and "koppel aan rol" in html


def test_wees_project_niet_op_gewone_rol_bord(tmp_path):
    dd, st = _st(tmp_path)
    _make_orphan(dd, st)
    html = P._projects_tab_html(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROLE),
                                csrf_token="TOK", add=True)
    assert "Wees-projecten" not in html       # alleen op de wortel, niet op elke rol


def test_wees_project_koppelbaar_aan_rol(tmp_path):
    dd, st = _st(tmp_path)
    pid = _make_orphan(dd, st)
    cockpit2.dispatch(dd, "proj_setowner", {"pid": [pid], "owner": [ROLE2], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["owner"] == ROLE2


# ── klikbaarheid: publiek = link naar detail (→ login), ingelogd = modal-div ──

def test_kaart_is_link_in_publieke_view(tmp_path):
    """Read-only (geen csrf): geen modal-JS, dus de kaart moet een <a> zijn die naar /project
    navigeert (server redirect dan naar /login). Anders is de kaart een dode div."""
    dd, st = _st(tmp_path)
    st.projects.create(ROLE, "Zichtbaar", "human", status="queued")
    html = P._projects_tab_html(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROLE),
                                csrf_token="", add=False)
    assert "<a class='card pcard' href='/project?pid=" in html
    assert "data-pid" not in html              # geen modal-afhankelijke div in read-only


def test_kaart_is_modal_div_ingelogd(tmp_path):
    dd, st = _st(tmp_path)
    st.projects.create(ROLE, "Zichtbaar", "human", status="queued")
    html = P._projects_tab_html(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROLE),
                                csrf_token="TOK", add=True)
    assert "<div class='card pcard' data-pid=" in html and "draggable=" in html


# ── Individueel Initiatief: project oppakken zonder rol ──────────────────────

def test_toevoegform_biedt_individueel_initiatief_op_cirkel(tmp_path):
    dd, st = _st(tmp_path)
    html = P._inline_add_project(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(CIRCLE),
                                 "TOK", "/back")
    assert f"value='ii:{CIRCLE}'" in html and "Individueel Initiatief" in html


def test_toevoegform_geen_ii_op_rol(tmp_path):
    dd, st = _st(tmp_path)
    html = P._inline_add_project(cockpit2._Stores(dd), cockpit2._Stores(dd).records.get(ROLE),
                                 "TOK", "/back")
    assert "Individueel Initiatief" not in html      # II is een cirkel-begrip, niet op een rol

def test_ii_project_aanmaken_en_tonen(tmp_path):
    dd, st = _st(tmp_path)
    stefan = st.people.all()[0]
    ii = f"ii:{CIRCLE}"
    cockpit2.dispatch(dd, "proj_add", {"owner": [ii], "scope": ["Spontane actie"], "col": ["actief"],
                                       "trekker": [f"person:{stefan.id}"], "next": ["/"]}, username="guest")
    pj = [p for p in cockpit2._Stores(dd).projects.all() if p["owner"] == ii]
    assert len(pj) == 1 and pj[0]["person"] == stefan.id
    page = cockpit2.render_node(cockpit2._Stores(dd), CIRCLE, "projects", csrf_token="TOK", group="rol")
    assert "Spontane actie" in page and "Individueel Initiatief" in page


def test_trekker_default_is_ingelogde_gebruiker(tmp_path):
    # bij '+ project' staat de ingelogde gebruiker standaard voorgeselecteerd als trekker
    import re
    dd, st = _st(tmp_path)
    me = st.people.add("Ingelogd Persoon", "ingelogd@nooch.earth")
    page = cockpit2.render_node(cockpit2._Stores(dd), CIRCLE, "projects",
                                csrf_token="TOK", username="ingelogd@nooch.earth")
    opts = re.search(r"<select name='trekker'>(.*?)</select>", page, re.DOTALL).group(1)
    assert re.search(rf"<option value='person:{me.id}' selected>", opts)
    # guest → geen voorselectie
    page2 = cockpit2.render_node(cockpit2._Stores(dd), CIRCLE, "projects",
                                 csrf_token="TOK", username="guest")
    opts2 = re.search(r"<select name='trekker'>(.*?)</select>", page2, re.DOTALL).group(1)
    assert "selected" not in opts2


# ── impact-pills (scope 2): missie_impact / business_impact ──────────────────────────────────────
def test_proj_setimpact_zet_missie_en_business(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    cockpit2.dispatch(dd, "proj_setimpact",
                      {"pid": [pid], "kind": ["missie"], "value": ["versterkt"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "proj_setimpact",
                      {"pid": [pid], "kind": ["business"], "value": ["hoog"], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p["missie_impact"] == "versterkt" and p["business_impact"] == "hoog"


def test_proj_setimpact_leegmaken(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued", missie_impact="verzwakt")
    cockpit2.dispatch(dd, "proj_setimpact",
                      {"pid": [pid], "kind": ["missie"], "value": [""], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["missie_impact"] == ""   # toggle-off → ongelabeld


def test_proj_setimpact_weigert_ongeldige_waarde(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    _, msg = cockpit2.dispatch(dd, "proj_setimpact",
                               {"pid": [pid], "kind": ["missie"], "value": ["banaan"], "next": ["/"]}, username="guest")
    assert "ongeldig" in msg.lower()
    assert cockpit2._Stores(dd).projects.get(pid)["missie_impact"] == ""   # ongewijzigd


def test_proj_setimpact_onbekend_veld(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued")
    _, msg = cockpit2.dispatch(dd, "proj_setimpact",
                               {"pid": [pid], "kind": ["xyz"], "value": ["hoog"], "next": ["/"]}, username="guest")
    assert "onbekend" in msg.lower()


def test_impact_pills_in_schrijfmodus_niet_read_only(tmp_path):
    dd, st = _st(tmp_path)
    pid = st.projects.create(ROLE, "Test", "human", status="queued", missie_impact="neutraal")
    rw = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    ro = P.render_project(cockpit2._Stores(dd), pid, csrf_token="")
    assert "proj_setimpact" in rw and "imp-pill" in rw
    assert "Missie-impact" in rw and "Business-impact" in rw
    assert "proj_setimpact" not in ro          # read-only: geen bewerk-form
    assert "imp-pill n on" in ro               # wel de gekozen waarde als statische pill
