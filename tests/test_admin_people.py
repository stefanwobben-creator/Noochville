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
