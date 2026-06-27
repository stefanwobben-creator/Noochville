"""Cockpit 2 (GlassFrog-vorm, PoC): bootstrap + read-only render van cirkels/rollen/personen."""
from __future__ import annotations

from nooch_village import cockpit2


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def test_bootstrap_laadt_nooch(tmp_path):
    st = _st(tmp_path)
    assert st.records.get("mother_earth") is not None
    assert st.records.get("mother_earth__nooch") is not None
    assert len(st.people.all()) == 6


def test_root_overview(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth", "overview")
    assert "Mother Earth" in page and "cirkel" in page
    assert "support and protect all forms of life" in page
    # tabs aanwezig met status-stippen
    assert "Overview" in page and "Members" in page and "Metrics" in page


def test_nooch_roles_tab(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch", "roles")
    assert "Creator of Shoes" in page and "Marketing Lead" in page
    # de cirkel-kaart/boom toont de hiërarchie
    assert "Organisatie" in page


def test_role_overview_fillers_en_domein(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch__website_developer", "overview")
    assert "Website Developer" in page
    assert "Stefan Wobben" in page and "Dan Morgan" in page    # multi-fill zichtbaar
    assert "Nooch.earth" in page                               # domein


def test_grijze_tab(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch", "policies")   # nog grijs
    assert "Nog te bouwen" in page


def test_projecten_tab_leeg_en_toevoegformulier(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch__website_developer", "projects",
                                csrf_token="t")
    assert "Nog geen projecten" in page
    assert "proj_add" in page and "project toevoegen" in page


def test_project_toevoegen_en_koppeling(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {
        "owner": [role], "scope": ["Productpagina live"], "person": [lotte.id],
        "next": [f"/node?id={role}&tab=projects"]})
    # op de rol zichtbaar
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "Productpagina live" in page and "Lotte Mulder" in page
    # op de persoonspagina zichtbaar (via trekker én via rol)
    pp = cockpit2.render_person(cockpit2._Stores(dd), lotte.id)
    assert "Productpagina live" in pp and "Projecten" in pp


def test_project_op_cirkel(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    cockpit2.dispatch(dd, "proj_add", {
        "owner": ["mother_earth__nooch"], "scope": ["Jaarplan 2027"], "person": [""],
        "next": ["/node?id=mother_earth__nooch&tab=projects"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "projects", csrf_token="t")
    assert "Jaarplan 2027" in page


def test_persoonspagina_mijn_rollen(tmp_path):
    st = _st(tmp_path)
    lotte = st.people.by_name("Lotte Mulder")
    page = cockpit2.render_person(st, lotte.id)
    assert "Lotte Mulder" in page and "Mijn rollen" in page
    assert "Creator of Shoes" in page                          # een van haar rollen


def test_members_tab(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch", "members")
    for naam in ("Lotte Mulder", "Stefan Wobben", "Nina Wolter", "Matthijs Boesten"):
        assert naam in page
