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
    html = cockpit2._handle_person_add(
        dd, {"voornaam": ["Nieuw"], "achternaam": ["Persoon"], "email": ["nieuw@nooch.earth"], "next": ["/admin"]})
    temp = _temp_from(html)
    assert auth.UserStore(dd + "/people.json").verify_by_email("nieuw@nooch.earth", temp)


def test_toevoegen_weigert_dubbele_email(tmp_path):
    dd, st = _st(tmp_path)
    st.people.add("Bestaand", "dub@nooch.earth")
    html = cockpit2._handle_person_add(
        dd, {"voornaam": ["X"], "achternaam": ["Y"], "email": ["dub@nooch.earth"], "next": ["/admin"]})
    assert "bestaat al" in html


def test_toevoegen_vereist_naam_en_email(tmp_path):
    dd, st = _st(tmp_path)
    html = cockpit2._handle_person_add(dd, {"voornaam": [""], "achternaam": [""], "email": [""], "next": ["/admin"]})
    assert "verplicht" in html


# ── wijzigen ─────────────────────────────────────────────────────────────────

def test_person_edit_wijzigt_naam_en_email(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Oud", "oud@nooch.earth")
    cockpit2.dispatch(dd, "person_edit", {"pid": [p.id], "name": ["Nieuw"], "email": ["new@nooch.earth"], "next": ["/admin"]})
    got = cockpit2._Stores(dd).people.get(p.id)
    assert got.name == "Nieuw" and got.email == "new@nooch.earth"


# ── wachtwoord resetten ──────────────────────────────────────────────────────

def test_reset_password_zet_nieuw_werkend_wachtwoord(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Reset", "reset@nooch.earth")
    html = cockpit2._handle_person_reset(dd, {"pid": [p.id], "next": ["/admin"]})
    temp = _temp_from(html)
    assert auth.UserStore(dd + "/people.json").verify_by_email("reset@nooch.earth", temp)


def test_reset_onbekende_persoon(tmp_path):
    dd, st = _st(tmp_path)
    html = cockpit2._handle_person_reset(dd, {"pid": ["nietbestaand"], "next": ["/admin"]})
    assert "niet gevonden" in html


# ── verwijderen ──────────────────────────────────────────────────────────────

def test_person_remove_verwijdert_en_ruimt_rollen_op(tmp_path):
    dd, st = _st(tmp_path)
    p = st.people.add("Weg", "weg@nooch.earth")
    role = "mother_earth__nooch__brand_visual_designer"
    st.assign.assign(role, "person", p.id)
    assert role in cockpit2._Stores(dd).assign.roles_of("person", p.id)
    cockpit2.dispatch(dd, "person_remove", {"pid": [p.id], "next": ["/admin"]})
    st2 = cockpit2._Stores(dd)
    assert st2.people.get(p.id) is None
    assert st2.assign.roles_of("person", p.id) == []     # rol-toewijzing opgeruimd


def test_person_remove_onbekend(tmp_path):
    dd, st = _st(tmp_path)
    _, msg = cockpit2.dispatch(dd, "person_remove", {"pid": ["nietbestaand"], "next": ["/admin"]})
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
