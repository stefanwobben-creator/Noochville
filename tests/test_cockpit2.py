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


def test_projecten_tab_kolommen_en_inline_add(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Sleepbaar"], "col": ["actief"],
                                       "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    # statuskolommen (Trello-stijl) + inline toevoegen + slepen
    for col in ("Actief", "Wacht", "Toekomst", "Done"):
        assert col in page
    assert "proj_add" in page and "+ kaart toevoegen" in page
    assert "data-to='toekomst'" in page and "draggable" in page.lower()
    assert "data-href=" in page                 # kaart klikbaar naar detail
    assert "vbtn" in page                        # board/lijst-schakelaar


def test_inline_add_in_kolom_zet_status(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Later-idee"],
                                       "col": ["toekomst"], "next": ["/"]})
    p = cockpit2._Stores(dd).projects.all()[0]
    assert p["status"] == "future"          # toegevoegd in de Toekomst-kolom


def test_dispatch_geeft_bevestiging(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    nxt, msg = cockpit2.dispatch(dd, "proj_add", {
        "owner": ["mother_earth__nooch"], "scope": ["X"], "col": ["actief"], "next": ["/"]})
    assert "toegevoegd" in msg


def test_project_toevoegen_en_koppeling(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {
        "owner": [role], "scope": ["Productpagina live"], "trekker": [f"person:{lotte.id}"],
        "next": [f"/node?id={role}&tab=projects"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "Productpagina live" in page and "Lotte Mulder" in page
    pp = cockpit2.render_person(cockpit2._Stores(dd), lotte.id)
    assert "Productpagina live" in pp and "Projecten" in pp


def test_project_op_cirkel(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    cockpit2.dispatch(dd, "proj_add", {
        "owner": ["mother_earth__nooch"], "scope": ["Jaarplan 2027"], "trekker": [""],
        "next": ["/node?id=mother_earth__nooch&tab=projects"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "projects", csrf_token="t")
    assert "Jaarplan 2027" in page


def test_project_status_done_delete(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Bug-sprint"], "trekker": [""],
                                       "next": ["/"]})
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    # status → wacht
    cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["wacht"], "next": ["/"]})
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "blocked"
    # → done
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]})
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "done"
    # verwijderen
    cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/"]})
    assert cockpit2._Stores(dd).projects.get(pid) is None


def test_project_detail_checklist_en_feed(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Detail-test"], "col": ["actief"],
                                       "next": ["/"]})
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    # omschrijving + label via edit
    cockpit2.dispatch(dd, "proj_edit", {"pid": [pid], "scope": ["Detail-test"],
                                        "description": ["Een nette omschrijving"], "label": ["groen"],
                                        "trekker": [""], "next": ["/"]})
    # checklist-items + afvinken
    cockpit2.dispatch(dd, "check_add", {"pid": [pid], "text": ["Stap 1"], "next": ["/"]})
    cockpit2.dispatch(dd, "check_add", {"pid": [pid], "text": ["Stap 2"], "next": ["/"]})
    item1 = cockpit2._Stores(dd).projects.get(pid)["checklist"][0]["id"]
    cockpit2.dispatch(dd, "check_toggle", {"pid": [pid], "item": [item1], "next": ["/"]})
    # opmerking in de feed
    cockpit2.dispatch(dd, "proj_comment", {"pid": [pid], "comment": ["Eerste voortgang"], "next": ["/"]})

    page = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", back="/node?id=" + role)
    assert "Detail-test" in page and "Een nette omschrijving" in page
    assert "Stap 1" in page and "Stap 2" in page
    assert "50% (1/2)" in page                     # voortgangsbalk
    assert "Eerste voortgang" in page              # activiteitenfeed
    assert "check_toggle" in page and "check_add" in page


def test_project_kaart_toont_label_en_progress(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Met label"], "col": ["actief"],
                                       "next": ["/"]})
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    cockpit2.dispatch(dd, "proj_edit", {"pid": [pid], "scope": ["Met label"], "label": ["koraal"],
                                        "trekker": [""], "next": ["/"]})
    cockpit2.dispatch(dd, "check_add", {"pid": [pid], "text": ["a"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "clabel" in page and "FF6B5B" in page    # kleurbalk op de kaart
    assert "0%" in page                              # checklist-progress badge (geen 💬)
    assert "💬" not in page


def test_projecten_groeperen_per_persoon(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Van Lotte"], "col": ["actief"],
                                       "trekker": [f"person:{lotte.id}"], "next": ["/"]})
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Zonder trekker"], "col": ["actief"],
                                       "trekker": [""], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t", group="persoon")
    # swimlanes per persoon: Lotte en 'Geen trekker'
    assert "swim-h" in page and "Lotte Mulder" in page and "Geen trekker" in page


def test_circle_projecten_subtree_en_per_rol(tmp_path):
    # cirkel toont projecten van onderliggende rollen, groepeerbaar per rol
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    cockpit2.dispatch(dd, "proj_add", {"owner": ["mother_earth__nooch__website_developer"],
                                       "scope": ["Subproject"], "col": ["actief"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "projects",
                                csrf_token="t", group="rol")
    assert "Subproject" in page and "Website Developer" in page and "swim-h" in page


def test_project_archiveren_default(tmp_path):
    # archiveren = blijft bestaan, uit het actieve board; herstellen kan
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Oud project"], "trekker": [""],
                                       "next": ["/"]})
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    cockpit2.dispatch(dd, "proj_archive", {"pid": [pid], "next": ["/"]})
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p is not None and p["archived"] is True          # blijft bestaan
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "Gearchiveerd (1)" in page and "Oud project" in page
    # herstellen
    cockpit2.dispatch(dd, "proj_unarchive", {"pid": [pid], "next": ["/"]})
    assert cockpit2._Stores(dd).projects.get(pid)["archived"] is False


def test_project_ai_trekker(tmp_path):
    # verbetering t.o.v. GlassFrog: een AI-inwoner als trekker
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    noochie = st.personas.add("Noochie")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["SEO-audit"],
                                       "trekker": [f"persona:{noochie.id}"], "next": ["/"]})
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "SEO-audit" in page and "Noochie" in page and "(AI)" in page


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
