"""Admin-pagina 'Deelnemers': toevoegen, wijzigen, wachtwoord resetten, verwijderen.
People-beheer zit op /admin, niet meer op de Members-tab."""
from __future__ import annotations

import re

from nooch_village import cockpit2, auth


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _temp_from(html):
    return re.search(r"monospace.*?>([a-z0-9]+)<", html).group(1)


# ── render ───────────────────────────────────────────────────────────────────

def test_admin_toont_beheercontrols_in_schrijfmodus(tmp_path):
    dd, st = _st(tmp_path)
    html = cockpit2.render_admin(cockpit2._Stores(dd), csrf_token="TOK")
    assert "Deelnemers" in html
    assert "person_add" in html and "name='voornaam'" in html
    assert "person_edit" in html and "person_remove" in html and "person_reset_password" in html


def test_admin_readonly_zonder_controls(tmp_path):
    dd, st = _st(tmp_path)
    html = cockpit2.render_admin(cockpit2._Stores(dd), csrf_token="")
    assert "person_edit" not in html and "person_remove" not in html and "person_add" not in html


def test_members_tab_verwijst_naar_admin(tmp_path):
    dd, st = _st(tmp_path)
    m = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth", "members", csrf_token="TOK")
    assert "/admin" in m and "Persoon toevoegen" not in m


# ── toevoegen ────────────────────────────────────────────────────────────────

def test_toevoegen_maakt_persoon_en_toont_wachtwoord(tmp_path):
    dd, st = _st(tmp_path)
    html, _ = cockpit2._handle_person_add(
        dd, {"voornaam": ["Nieuw"], "achternaam": ["Persoon"], "email": ["nieuw@nooch.earth"], "next": ["/admin"]},
        username="guest")
    temp = _temp_from(html)
    assert auth.UserStore(dd + "/people.json").verify_by_email("nieuw@nooch.earth", temp)


def test_toevoegen_weigert_dubbele_email(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Bestaand", "dub@nooch.earth")
    html, _ = cockpit2._handle_person_add(
        dd, {"voornaam": ["X"], "achternaam": ["Y"], "email": ["dub@nooch.earth"], "next": ["/admin"]},
        username="guest")
    assert "bestaat al" in html


def test_toevoegen_vereist_naam_en_email(tmp_path):
    dd, st = _st(tmp_path)
    html, _ = cockpit2._handle_person_add(dd, {"voornaam": [""], "achternaam": [""], "email": [""], "next": ["/admin"]},
                                          username="guest")
    assert "verplicht" in html


# ── wijzigen ─────────────────────────────────────────────────────────────────

def test_person_edit_wijzigt_naam_en_email(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Oud", "oud@nooch.earth")
    cockpit2.dispatch(dd, "person_edit", {"pid": [p.id], "name": ["Nieuw"], "email": ["new@nooch.earth"], "next": ["/admin"]}, username="guest")
    got = cockpit2._Stores(dd).people.get(p.id)
    assert got.name == "Nieuw" and got.email == "new@nooch.earth"


# ── wachtwoord resetten ──────────────────────────────────────────────────────

def test_reset_password_zet_nieuw_werkend_wachtwoord(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Reset", "reset@nooch.earth")
    html, _ = cockpit2._handle_person_reset(dd, {"pid": [p.id], "next": ["/admin"]}, username="guest")
    temp = _temp_from(html)
    assert auth.UserStore(dd + "/people.json").verify_by_email("reset@nooch.earth", temp)


def test_reset_onbekende_persoon(tmp_path):
    dd, st = _st(tmp_path)
    html, _ = cockpit2._handle_person_reset(dd, {"pid": ["nietbestaand"], "next": ["/admin"]}, username="guest")
    assert "niet gevonden" in html


# ── verwijderen ──────────────────────────────────────────────────────────────

def test_person_remove_verwijdert_en_ruimt_rollen_op(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Weg", "weg@nooch.earth")
    role = "mother_earth__nooch__brand_visual_designer"
    st.assign.assign(role, "person", p.id)
    assert role in cockpit2._Stores(dd).assign.roles_of("person", p.id)
    cockpit2.dispatch(dd, "person_remove", {"pid": [p.id], "next": ["/admin"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.people.get(p.id) is None
    assert st2.assign.roles_of("person", p.id) == []     # rol-toewijzing opgeruimd


def test_person_remove_onbekend(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "person_remove", {"pid": ["nietbestaand"], "next": ["/admin"]}, username="guest")
    assert "niet gevonden" in msg


def test_is_circle_lead(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.all()[0]
    circle = "mother_earth__nooch"
    st.assign.assign(f"{circle}__circle_lead", "person", p.id)   # ken p toe als leadlink
    a = cockpit2._Stores(dd).assign
    assert cockpit2.is_circle_lead(p.id, circle, a) is True
    assert cockpit2.is_circle_lead("iemand_anders", circle, a) is False
    assert cockpit2.is_circle_lead(p.id, "andere_cirkel", a) is False   # andere cirkel
    assert cockpit2.is_circle_lead("", circle, a) is False


def test_is_role_filler(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.all()[0]
    role = "mother_earth__nooch__brand_visual_designer"
    st.assign.assign(role, "person", p.id)                      # ken p toe als rolvervuller
    a = cockpit2._Stores(dd).assign
    assert cockpit2.is_role_filler(p.id, role, a) is True
    assert cockpit2.is_role_filler("iemand_anders", role, a) is False
    assert cockpit2.is_role_filler(p.id, "andere_rol", a) is False   # andere rol
    assert cockpit2.is_role_filler("", role, a) is False


# ── autorisatie-poort op de rol-takken (role_assign/unassign/focus) ───────────

_GATE_ROLE = "mother_earth__nooch__brand_visual_designer"     # parent-cirkel: mother_earth__nooch
_GATE_LEAD = "mother_earth__nooch__circle_lead"


def _assign_form(target_id):
    return {"role": [_GATE_ROLE], "filler": [f"person:{target_id}"], "next": ["/x"]}


def test_gate_guest_mag_toewijzen(tmp_path):
    # auth uit → "guest" → gate laat door, toewijzing slaagt
    dd, st = _st(tmp_path)
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "role_assign", _assign_form(target.id), username="guest")
    assert "toegewezen" in msg
    assert _GATE_ROLE in cockpit2._Stores(dd).assign.roles_of("person", target.id)


def test_gate_circle_lead_mag_toewijzen(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)           # lead van de ouder-cirkel
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "role_assign", _assign_form(target.id), username="lead@nooch.earth")
    assert "toegewezen" in msg
    assert _GATE_ROLE in cockpit2._Stores(dd).assign.roles_of("person", target.id)


def test_gate_niet_lead_wordt_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    outsider = st.people.add("Buiten", "buiten@nooch.earth")  # ingelogd, maar geen lead
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "role_assign", _assign_form(target.id), username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "Circle Lead" in msg
    assert _GATE_ROLE not in cockpit2._Stores(dd).assign.roles_of("person", target.id)


def test_gate_onbekende_gebruiker_wordt_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "role_assign", _assign_form(target.id), username="niemand@nergens.nl")
    assert "niet herkend" in msg
    assert _GATE_ROLE not in cockpit2._Stores(dd).assign.roles_of("person", target.id)


# ── autorisatie-poort op aitask_add (directe ouder-cirkel-lead) ───────────────

def _aitask_form():
    return {"role": [_GATE_ROLE], "acc": ["0"], "pick": ["harry::content_schrijven"], "next": ["/x"]}


def test_gate_aitask_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "aitask_add", _aitask_form(), username="guest")
    assert "gekoppeld" in msg


def test_gate_aitask_circle_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)           # lead van mother_earth__nooch
    _, msg = cockpit2.dispatch(dd, "aitask_add", _aitask_form(), username="lead@nooch.earth")
    assert "gekoppeld" in msg


def test_gate_aitask_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")             # ingelogd, geen lead
    _, msg = cockpit2.dispatch(dd, "aitask_add", _aitask_form(), username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "Circle Lead" in msg


def test_gate_aitask_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "aitask_add", _aitask_form(), username="niemand@nergens.nl")
    assert "niet herkend" in msg


# ── autorisatie-poort op persona_skill_add (anchor-lead: mother_earth) ────────

def _persona_skill_form(dd):
    persona = cockpit2._Stores(dd).personas.add("Testinwoner")
    return persona.id, {"agent": [persona.id], "skill": ["nieuwe_skill"], "next": ["/x"]}


def test_gate_persona_skill_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    pid, form = _persona_skill_form(dd)
    _, msg = cockpit2.dispatch(dd, "persona_skill_add", form, username="guest")
    assert "rugzak" in msg
    assert "nieuwe_skill" in cockpit2._Stores(dd).personas.get(pid).skills


def test_gate_persona_skill_anchor_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Anchor", "anchor@nooch.earth")
    st.assign.assign("mother_earth__circle_lead", "person", lead.id)   # anchor-lead
    pid, form = _persona_skill_form(dd)
    _, msg = cockpit2.dispatch(dd, "persona_skill_add", form, username="anchor@nooch.earth")
    assert "rugzak" in msg
    assert "nieuwe_skill" in cockpit2._Stores(dd).personas.get(pid).skills


def test_gate_persona_skill_niet_anchor_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    # lead van een subcirkel is géén anchor-lead → geweigerd
    subly = st.people.add("Sub", "sub@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", subly.id)          # mother_earth__nooch-lead, niet anchor
    pid, form = _persona_skill_form(dd)
    _, msg = cockpit2.dispatch(dd, "persona_skill_add", form, username="sub@nooch.earth")
    assert "Geen toegang" in msg and "anchor-lead" in msg
    assert "nieuwe_skill" not in cockpit2._Stores(dd).personas.get(pid).skills


def test_gate_persona_skill_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    pid, form = _persona_skill_form(dd)
    _, msg = cockpit2.dispatch(dd, "persona_skill_add", form, username="niemand@nergens.nl")
    assert "niet herkend" in msg
    assert "nieuwe_skill" not in cockpit2._Stores(dd).personas.get(pid).skills


# ══════════════════════════════════════════════════════════════════════════════
# Groep A — anchor-lead only (person_edit / person_remove / def_amend / def_add)
# Representatieve tak: person_remove (destructief, org-breed).
# ══════════════════════════════════════════════════════════════════════════════

_ANCHOR_LEAD = "mother_earth__circle_lead"


def test_gate_anchor_guest_mag_verwijderen(tmp_path):
    dd, st = _st(tmp_path)
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "person_remove", {"pid": [target.id], "next": ["/x"]}, username="guest")
    assert "verwijderd" in msg
    assert cockpit2._Stores(dd).people.get(target.id) is None


def test_gate_anchor_lead_mag_verwijderen(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Anchor", "anchor@nooch.earth")
    st.assign.assign(_ANCHOR_LEAD, "person", lead.id)
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "person_remove", {"pid": [target.id], "next": ["/x"]}, username="anchor@nooch.earth")
    assert "verwijderd" in msg
    assert cockpit2._Stores(dd).people.get(target.id) is None


def test_gate_anchor_subcirkel_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    subly = st.people.add("Sub", "sub@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", subly.id)          # lead van mother_earth__nooch, niet anchor
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "person_remove", {"pid": [target.id], "next": ["/x"]}, username="sub@nooch.earth")
    assert "Geen toegang" in msg and "anchor-lead" in msg
    assert cockpit2._Stores(dd).people.get(target.id) is not None


def test_gate_anchor_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    target = st.people.add("Doel", "doel@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "person_remove", {"pid": [target.id], "next": ["/x"]}, username="niemand@nergens.nl")
    assert "niet herkend" in msg
    assert cockpit2._Stores(dd).people.get(target.id) is not None


# ══════════════════════════════════════════════════════════════════════════════
# Groep B — Circle Lead van de cirkel van het project/de rol
# proj_delete (via pid → owner → cirkel) en aitask_remove (via tid → rol → cirkel).
# ══════════════════════════════════════════════════════════════════════════════

def _make_project(dd, owner=_GATE_ROLE):
    pid = cockpit2._Stores(dd).projects.create(owner, "Testproject", "human")
    return pid


def test_gate_projdelete_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    pid = _make_project(dd)
    _, msg = cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/x"]}, username="guest")
    assert "verwijderd" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is None


def test_gate_projdelete_circle_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)           # lead van mother_earth__nooch (parent van de rol)
    pid = _make_project(dd)
    _, msg = cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/x"]}, username="lead@nooch.earth")
    assert "verwijderd" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is None


def test_gate_projdelete_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")
    pid = _make_project(dd)
    _, msg = cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/x"]}, username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "Circle Lead" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is not None


def test_gate_projdelete_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    pid = _make_project(dd)
    _, msg = cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/x"]}, username="niemand@nergens.nl")
    assert "niet herkend" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is not None


def test_gate_projdelete_individueel_initiatief_lead_van_ii_cirkel(tmp_path):
    # II-project: owner = "ii:<circle>"; lead van díe cirkel mag verwijderen
    dd, st = _st(tmp_path)
    circle = "mother_earth__nooch"
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(f"{circle}__circle_lead", "person", lead.id)
    pid = _make_project(dd, owner=f"{cockpit2._II_PREFIX}{circle}")
    _, msg = cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/x"]}, username="lead@nooch.earth")
    assert "verwijderd" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is None


def test_gate_projdelete_individueel_initiatief_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    circle = "mother_earth__nooch"
    st.people.add("Buiten", "buiten@nooch.earth")
    pid = _make_project(dd, owner=f"{cockpit2._II_PREFIX}{circle}")
    _, msg = cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/x"]}, username="buiten@nooch.earth")
    assert "Geen toegang" in msg
    assert cockpit2._Stores(dd).projects.get(pid) is not None


def _make_aitask(dd):
    return cockpit2._Stores(dd).ai.add(_GATE_ROLE, 0, "harry", "content_schrijven")


def test_gate_aitaskremove_circle_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)
    t = _make_aitask(dd)
    _, msg = cockpit2.dispatch(dd, "aitask_remove", {"tid": [t.id], "next": ["/x"]}, username="lead@nooch.earth")
    assert "verwijderd" in msg


def test_gate_aitaskremove_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")
    t = _make_aitask(dd)
    _, msg = cockpit2.dispatch(dd, "aitask_remove", {"tid": [t.id], "next": ["/x"]}, username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "Circle Lead" in msg
    assert any(x.id == t.id for x in cockpit2._Stores(dd).ai.all())   # niet verwijderd


# ══════════════════════════════════════════════════════════════════════════════
# Groep C — Circle Lead van de cirkel die het overleg houdt (circle uit g("circle"))
# Representatieve tak: rov2_remove.
# ══════════════════════════════════════════════════════════════════════════════

def _rov_remove_form(circle="mother_earth__nooch"):
    return {"circle": [circle], "iid": ["willekeurig"], "next": ["/x"]}


def test_gate_rov_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "rov2_remove", _rov_remove_form(), username="guest")
    assert "verwijderd" in msg


def test_gate_rov_circle_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)           # lead van mother_earth__nooch
    _, msg = cockpit2.dispatch(dd, "rov2_remove", _rov_remove_form(), username="lead@nooch.earth")
    assert "verwijderd" in msg


def test_gate_rov_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "rov2_remove", _rov_remove_form(), username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "Circle Lead" in msg


def test_gate_rov_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "rov2_remove", _rov_remove_form(), username="niemand@nergens.nl")
    assert "niet herkend" in msg


# ══════════════════════════════════════════════════════════════════════════════
# Operationele laag — gate = is_role_filler(rol) OF is_circle_lead(ouder-cirkel).
# Helpers resolve_circle_id + _role_gate. Representatieve takken per categorie.
# ══════════════════════════════════════════════════════════════════════════════

def test_resolve_circle_id_rol_cirkel_ii(tmp_path):
    dd, st = _st(tmp_path)
    recs = st.records
    # rol → ouder-cirkel
    assert cockpit2.resolve_circle_id("mother_earth__nooch__brand_visual_designer", recs) == "mother_earth__nooch"
    # cirkel → zichzelf
    assert cockpit2.resolve_circle_id("mother_earth__nooch", recs) == "mother_earth__nooch"
    # Individueel Initiatief → cirkel uit de prefix
    assert cockpit2.resolve_circle_id(f"{cockpit2._II_PREFIX}mother_earth__nooch", recs) == "mother_earth__nooch"
    # leeg / onbekend → None
    assert cockpit2.resolve_circle_id("", recs) is None
    assert cockpit2.resolve_circle_id("bestaat_niet", recs) is None


# ── Categorie 1: role_id direct via g("node") — m_add_kpi ─────────────────────

def _kpi_form():
    return {"node": [_GATE_ROLE], "pick": ["manual"], "name": ["Testmeter"], "unit": ["n"], "next": ["/x"]}


def test_gate_op_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "m_add_kpi", _kpi_form(), username="guest")
    assert "toegevoegd" in msg


def test_gate_op_rolvervuller_mag(tmp_path):
    # de rolvervuller zelf (geen Circle Lead) mag zijn eigen rol beheren
    dd, st = _st(tmp_path)
    filler = st.people.add("Vervuller", "vervuller@nooch.earth")
    st.assign.assign(_GATE_ROLE, "person", filler.id)
    _, msg = cockpit2.dispatch(dd, "m_add_kpi", _kpi_form(), username="vervuller@nooch.earth")
    assert "toegevoegd" in msg


def test_gate_op_circle_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)           # lead van de ouder-cirkel, niet de rol
    _, msg = cockpit2.dispatch(dd, "m_add_kpi", _kpi_form(), username="lead@nooch.earth")
    assert "toegevoegd" in msg


def test_gate_op_buitenstaander_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")             # geen rol, geen lead
    _, msg = cockpit2.dispatch(dd, "m_add_kpi", _kpi_form(), username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "rolvervuller" in msg


def test_gate_op_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "m_add_kpi", _kpi_form(), username="niemand@nergens.nl")
    assert "niet herkend" in msg


# ── Categorie 2: role_id afgeleid via pid (proj_status) en cid (cl_report) ────

def test_gate_op_projstatus_afgeleid_via_pid(tmp_path):
    # rol afgeleid uit het project (pid → owner); rolvervuller mag, buitenstaander niet
    dd, st = _st(tmp_path)
    filler = st.people.add("Vervuller", "vervuller@nooch.earth")
    st.assign.assign(_GATE_ROLE, "person", filler.id)
    st.people.add("Buiten", "buiten@nooch.earth")
    pid = cockpit2._Stores(dd).projects.create(_GATE_ROLE, "P", "human")
    _, ok = cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["actief"], "next": ["/x"]},
                              username="vervuller@nooch.earth")
    assert "verplaatst" in ok
    _, deny = cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["wacht"], "next": ["/x"]},
                                username="buiten@nooch.earth")
    assert "Geen toegang" in deny


def test_gate_op_clreport_afgeleid_via_cid(tmp_path):
    # rol/node afgeleid uit het checklist-item (cid → node)
    dd, st = _st(tmp_path)
    lead = st.people.add("Lead", "lead@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", lead.id)
    st.people.add("Buiten", "buiten@nooch.earth")
    it = cockpit2._Stores(dd).checklists.add(_GATE_ROLE, "Wekelijkse check", "wekelijks", by="founder")
    cid = it["id"]
    _, ok = cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "next": ["/x"]}, username="lead@nooch.earth")
    assert "genoteerd" in ok
    _, deny = cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "next": ["/x"]}, username="buiten@nooch.earth")
    assert "Geen toegang" in deny


# ── Punt 1: collaboratie-takken ongated — elke ingelogde gebruiker mag ────────

def test_collaboratie_buitenstaander_mag_reageren(tmp_path):
    # proj_comment heeft GEEN rol-gate: een ingelogde niet-lid mag reageren
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")             # geen rol, geen lead
    pid = cockpit2._Stores(dd).projects.create(_GATE_ROLE, "P", "human")
    _, msg = cockpit2.dispatch(dd, "proj_comment", {"pid": [pid], "comment": ["hoi"], "next": ["/x"]},
                               username="buiten@nooch.earth")
    assert "geplaatst" in msg and "Geen toegang" not in msg


# ── Punt 2: proj_add van een Individueel Initiatief — elk cirkellid mag ───────

def test_is_circle_member(tmp_path):
    dd, st = _st(tmp_path)
    circle = "mother_earth__nooch"
    member = st.people.add("Lid", "lid@nooch.earth")
    st.assign.assign(_GATE_ROLE, "person", member.id)         # rol in de cirkel → lid
    outsider = st.people.add("Buiten", "buiten@nooch.earth")
    a, r = cockpit2._Stores(dd).assign, cockpit2._Stores(dd).records
    assert cockpit2.is_circle_member(member.id, circle, r, a) is True
    assert cockpit2.is_circle_member(outsider.id, circle, r, a) is False


def _ii_add_form(circle="mother_earth__nooch"):
    return {"owner": [f"{cockpit2._II_PREFIX}{circle}"], "scope": ["Mijn eigen initiatief"], "next": ["/x"]}


def test_ii_proj_add_cirkellid_mag(tmp_path):
    dd, st = _st(tmp_path)
    member = st.people.add("Lid", "lid@nooch.earth")
    st.assign.assign(_GATE_ROLE, "person", member.id)         # vervult een rol in mother_earth__nooch
    _, msg = cockpit2.dispatch(dd, "proj_add", _ii_add_form(), username="lid@nooch.earth")
    assert "toegevoegd" in msg


def test_ii_proj_add_niet_lid_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")             # geen rol in de cirkel, geen lead
    _, msg = cockpit2.dispatch(dd, "proj_add", _ii_add_form(), username="buiten@nooch.earth")
    assert "Geen toegang" in msg and "cirkel" in msg


def test_normale_proj_add_blijft_rolvervuller_of_lead(tmp_path):
    # een rol-owner (geen ii): buitenstaander geweigerd, rolvervuller mag
    dd, st = _st(tmp_path)
    st.people.add("Buiten", "buiten@nooch.earth")
    form = {"owner": [_GATE_ROLE], "scope": ["Werk"], "next": ["/x"]}
    _, deny = cockpit2.dispatch(dd, "proj_add", form, username="buiten@nooch.earth")
    assert "Geen toegang" in deny and "rolvervuller" in deny


# ══════════════════════════════════════════════════════════════════════════════
# People-beheer buiten dispatch: _handle_person_add / _handle_person_reset.
# Anchor-lead only; retourneren (body, statuscode).
# ══════════════════════════════════════════════════════════════════════════════

_ANCHOR = "mother_earth__circle_lead"


def _add_form():
    return {"voornaam": ["Nieuw"], "achternaam": ["Persoon"], "email": ["nieuw@nooch.earth"], "next": ["/admin"]}


def test_person_add_gate_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    body, code = cockpit2._handle_person_add(dd, _add_form(), username="guest")
    assert code == 200 and "toegevoegd" in body


def test_person_add_gate_anchor_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Anchor", "anchor@nooch.earth")
    st.assign.assign(_ANCHOR, "person", lead.id)
    body, code = cockpit2._handle_person_add(dd, _add_form(), username="anchor@nooch.earth")
    assert code == 200 and "toegevoegd" in body


def test_person_add_gate_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    subly = st.people.add("Sub", "sub@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", subly.id)          # subcirkel-lead, geen anchor
    body, code = cockpit2._handle_person_add(dd, _add_form(), username="sub@nooch.earth")
    assert code == 403 and "anchor-lead" in body
    assert cockpit2._Stores(dd).people.by_email("nieuw@nooch.earth") is None


def test_person_add_gate_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    body, code = cockpit2._handle_person_add(dd, _add_form(), username="niemand@nergens.nl")
    assert code == 403 and "niet herkend" in body
    assert cockpit2._Stores(dd).people.by_email("nieuw@nooch.earth") is None


def test_person_reset_gate_guest_mag(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Doel", "doel@nooch.earth")
    body, code = cockpit2._handle_person_reset(dd, {"pid": [p.id], "next": ["/admin"]}, username="guest")
    assert code == 200 and "gereset" in body


def test_person_reset_gate_anchor_lead_mag(tmp_path):
    dd, st = _st(tmp_path)
    lead = st.people.add("Anchor", "anchor@nooch.earth")
    st.assign.assign(_ANCHOR, "person", lead.id)
    p = st.people.add("Doel", "doel@nooch.earth")
    body, code = cockpit2._handle_person_reset(dd, {"pid": [p.id], "next": ["/admin"]}, username="anchor@nooch.earth")
    assert code == 200 and "gereset" in body


def test_person_reset_gate_niet_lead_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    subly = st.people.add("Sub", "sub@nooch.earth")
    st.assign.assign(_GATE_LEAD, "person", subly.id)
    p = st.people.add("Doel", "doel@nooch.earth")
    body, code = cockpit2._handle_person_reset(dd, {"pid": [p.id], "next": ["/admin"]}, username="sub@nooch.earth")
    assert code == 403 and "anchor-lead" in body


def test_person_reset_gate_onbekende_gebruiker_geweigerd(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Doel", "doel@nooch.earth")
    body, code = cockpit2._handle_person_reset(dd, {"pid": [p.id], "next": ["/admin"]}, username="niemand@nergens.nl")
    assert code == 403 and "niet herkend" in body
