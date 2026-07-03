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


def test_meetings_alleen_op_cirkels(tmp_path):
    st = _st(tmp_path)
    circle = cockpit2.render_node(st, "mother_earth__nooch", "overview", csrf_token="t")
    role = cockpit2.render_node(st, "mother_earth__nooch__website_developer", "overview", csrf_token="t")
    assert "Tactical meeting" in circle and "Governance meeting" in circle
    assert "Tactical meeting" not in role and "Governance meeting" not in role


def test_root_overview(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth", "overview")
    assert "Mother Earth" in page and "cirkel" in page
    assert "support and protect all forms of life" in page
    # tabs aanwezig met status-stippen
    assert "Overview" in page and "Members" in page and "Metrics" in page


def test_nooch_roles_tab(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch", "roles", csrf_token="t")
    assert "Creator of Shoes" in page and "Marketing Lead" in page
    assert "Organisatie" in page                              # org-boom (rail)
    # kernrollen apart + purpose onder de rol + toewijs-icoon
    assert "Kernrollen" in page and "Circle Lead" in page
    assert "Make Nooch visually consistent" in page          # purpose onder Brand & Visual Designer
    assert "manage-ico" in page and "/rolefillers?role=" in page   # neutraal beheer-icoon
    # vervullers links uitgelijnd met naam-link naar de persoon
    assert "Nina Wolter" in page and "/person?id=" in page


def test_rolefillers_modal_en_assign(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    role = "mother_earth__nooch__factory_development_specialist"   # onbemand
    frag = cockpit2.render_rolefillers(st, role, csrf_token="t", fragment=True)
    assert "<!doctype" not in frag.lower()
    assert "Rolvervullers beheren" in frag and "role_assign" in frag and "Nog niemand toegewezen" in frag
    assert "kies persoon" in frag and "of AI" not in frag      # alleen mensen vervullen een rol
    # toewijzen + verwijderen via dispatch
    wytse = st.people.by_name("Wytse Valkema")
    cockpit2.dispatch(dd, "role_assign", {"role": [role], "filler": [f"person:{wytse.id}"], "next": ["/"]}, username="guest")
    assert any(f.id == wytse.id for f in cockpit2._Stores(dd).assign.fillers_of(role))
    cockpit2.dispatch(dd, "role_unassign", {"role": [role], "filler": [f"person:{wytse.id}"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).assign.fillers_of(role) == []


def test_rolefiller_focus(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    role = "mother_earth__nooch__community_and_email"
    nina = st.people.by_name("Nina Wolter")
    cockpit2.dispatch(dd, "role_focus", {"role": [role], "filler": [f"person:{nina.id}"],
                                         "focus": ["nieuwsbrieven"], "next": ["/"]}, username="guest")
    f = next(x for x in cockpit2._Stores(dd).assign.fillers_of(role) if x.id == nina.id)
    assert f.focus == "nieuwsbrieven"
    # focus zichtbaar in de beheer-modal
    frag = cockpit2.render_rolefillers(cockpit2._Stores(dd), role, csrf_token="t", fragment=True)
    assert "nieuwsbrieven" in frag and "role_focus" in frag


def test_roles_tab_stack_bij_3plus(tmp_path):
    # 3+ vervullers → gestapelde avatars + '+ nog N'
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    role = "mother_earth__nooch__factory_development_specialist"
    for nm in ("Lotte Mulder", "Stefan Wobben", "Nina Wolter", "Dan Morgan"):
        cockpit2.dispatch(dd, "role_assign",
                          {"role": [role], "filler": [f"person:{st.people.by_name(nm).id}"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "roles", csrf_token="t")
    assert "+ nog 1" in page and "stack" in page              # 4 vervullers → 3 avatars + nog 1


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
                                       "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    # statuskolommen (Trello-stijl) in een niet-lege lane + slepen + top-level toevoegen
    for col in ("Actief", "Wacht", "Toekomst", "Done"):
        assert col in page
    assert "qadd-top" in page and "Te bereiken uitkomst" in page   # universele inline '+ project'
    assert "+ project toevoegen" in page                     # Trello per-kolom-add in niet-lege lane
    assert "data-to='toekomst'" in page and "draggable" in page.lower()
    assert "data-href=" in page                 # kaart klikbaar naar detail


def test_inline_add_in_kolom_zet_status(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Later-idee"],
                                       "col": ["toekomst"], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.all()[0]
    assert p["status"] == "future"          # toegevoegd in de Toekomst-kolom


def test_dispatch_geeft_bevestiging(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    nxt, msg = cockpit2.dispatch(dd, "proj_add", {
        "owner": ["mother_earth__nooch__website_developer"], "scope": ["X"], "col": ["actief"],
        "next": ["/"]}, username="guest")
    assert "toegevoegd" in msg


def test_project_toevoegen_en_koppeling(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {
        "owner": [role], "scope": ["Productpagina live"], "trekker": [f"person:{lotte.id}"],
        "next": [f"/node?id={role}&tab=projects"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "Productpagina live" in page and "Lotte Mulder" in page


def test_persoonspagina_projecten_tab_owner_based(tmp_path):
    # projecten-tab: bron van waarheid = owner ∈ de rollen die de persoon vervult
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__website_developer"
    st.assign.assign(role, "person", lotte.id)                 # Lotte vervult de owner-rol
    cockpit2.dispatch(dd, "proj_add", {
        "owner": [role], "scope": ["Productpagina live"], "trekker": [f"person:{lotte.id}"],
        "next": ["/"]}, username="guest")
    pp = cockpit2.render_person(cockpit2._Stores(dd), lotte.id, tab="projecten")
    assert "Productpagina live" in pp and "Projecten" in pp
    assert "swim" in pp and "pcol" in pp                        # DEZELFDE kanban-component ...
    assert "<ul class='clean'>" not in pp                       # ... geen aparte lijst-render


def test_persoonspagina_projecten_trekker_is_geen_eigendom(tmp_path):
    # narrowing: p.person is GEEN filtergrond. Een project van een rol die Lotte NIET vervult
    # verschijnt niet op haar projecten-tab, ook al is zij de trekker.
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__website_developer"            # Lotte NIET aan deze rol toegewezen
    cockpit2.dispatch(dd, "proj_add", {
        "owner": [role], "scope": ["Niet-van-Lotte"], "trekker": [f"person:{lotte.id}"],
        "next": ["/"]}, username="guest")
    pp = cockpit2.render_person(cockpit2._Stores(dd), lotte.id, tab="projecten")
    assert "Niet-van-Lotte" not in pp                          # trekker ≠ eigendom


def test_persoonspagina_context_tab_ingelogd(tmp_path):
    # context-tab: union van note-attachments over de rollen, met tool/doc-onderscheid
    st = _st(tmp_path)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__creator_of_shoes"
    st.assign.assign(role, "person", lotte.id)
    st.att.add(role, "note", title="Figma-plugin", subtype="tool")
    st.att.add(role, "note", title="Merkgids", subtype="doc")
    st.att.add(role, "note", title="Oude notitie")             # geen subtype → default 'doc'
    pg = cockpit2.render_person(st, lotte.id, tab="context", username="dev@nooch.earth")
    assert "Context (3)" in pg
    assert "Figma-plugin" in pg and "Merkgids" in pg and "Oude notitie" in pg
    assert "🛠" in pg and "📄" in pg                            # visueel tool/doc-onderscheid
    assert pg.count(">doc<") == 2                              # note zonder subtype telt als doc


def test_persoonspagina_context_drempel_zonder_sessie(tmp_path):
    # AUTHZ-drempel: geen sessie (guest / None) → "log in", geen inhoud, geen note-lek
    st = _st(tmp_path)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__creator_of_shoes"
    st.assign.assign(role, "person", lotte.id)
    st.att.add(role, "note", title="Geheim", subtype="doc")
    for sess in ("guest", None):
        pg = cockpit2.render_person(st, lotte.id, tab="context", username=sess)
        assert "Log in om context te zien" in pg
        assert "Geheim" not in pg                              # geen lek zonder sessie


def test_persoonspagina_metrics_tab_readonly(tmp_path):
    st = _st(tmp_path)
    lotte = st.people.by_name("Lotte Mulder")
    role = "mother_earth__nooch__creator_of_shoes"
    st.assign.assign(role, "person", lotte.id)
    st.metrics.add_tile(role, "shopify", "Orders", "none", "getal")
    pg = cockpit2.render_person(st, lotte.id, tab="metrics")        # geen csrf → zuivere read-only lens
    assert "Orders" in pg and "tile-grid" in pg                     # DEZELFDE _metrics_tab_html-render ...
    assert "<ul class='clean'>" not in pg                           # ... niet de oude lijst
    assert "+ KPI maken" not in pg and "action=" not in pg          # read-only: geen schrijfpad


def test_persoonspagina_checklist_afvink_alleen_filler(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    node = "mother_earth__nooch__website_developer"
    dev = st.people.add("Dev", "dev@nooch.earth")
    st.assign.assign(node, "person", dev.id)
    st.people.add("Buiten", "buiten@nooch.earth")
    cid = cockpit2._Stores(dd).checklists.add(node, "Wekelijkse review", "week", target_type="all")["id"]
    # niet-filler → geweigerd, geen rapport geschreven
    _, deny = cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "next": ["/"]},
                                username="buiten@nooch.earth")
    assert "Geen toegang" in deny
    assert not cockpit2._Stores(dd).checklists.get(cid).get("reports")
    # filler → gelukt, by = de afvinker (mens), met timestamp
    _, ok = cockpit2.dispatch(dd, "cl_report", {"cid": [cid], "ok": ["1"], "next": ["/"]},
                              username="dev@nooch.earth")
    assert "genoteerd" in ok
    rep = list(cockpit2._Stores(dd).checklists.get(cid)["reports"].values())[0]
    assert rep["by"] == "dev@nooch.earth" and rep.get("at", 0) > 0


def test_checklist_persona_afvink_met_timestamp(tmp_path):
    # AI-persona kan afvinken via report(by=<persona>) — uitvoerbewijs met timestamp
    st = _st(tmp_path)
    node = "mother_earth__nooch__creator_of_shoes"
    cid = st.checklists.add(node, "AI-check", "week", target_type="all")["id"]
    pa = st.personas.add("Codie", "ENTP", "x")
    assert st.checklists.report(cid, True, by=f"persona:{pa.id}")
    rep = list(st.checklists.get(cid)["reports"].values())[0]
    assert rep["by"] == f"persona:{pa.id}" and rep.get("at", 0) > 0


def test_cirkel_kan_geen_project_bevatten(tmp_path):
    # model-regel: een cirkel doet geen uitvoerend werk → geen project owned by een cirkel
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    nxt, msg = cockpit2.dispatch(dd, "proj_add", {
        "owner": ["mother_earth__nooch"], "scope": ["Jaarplan 2027"], "trekker": [""], "next": ["/"]}, username="guest")
    assert "cirkel kan geen project" in msg.lower()
    assert cockpit2._Stores(dd).projects.all() == []        # niets aangemaakt


def test_project_status_done_delete(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Bug-sprint"], "trekker": [""],
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    # status → wacht
    cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["wacht"], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "blocked"
    # → done
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["status"] == "done"
    # verwijderen
    cockpit2.dispatch(dd, "proj_delete", {"pid": [pid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid) is None


def test_project_detail_checklist_en_feed(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Detail-test"], "col": ["actief"],
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    # omschrijving + label via edit
    cockpit2.dispatch(dd, "proj_edit", {"pid": [pid], "scope": ["Detail-test"],
                                        "description": ["Een nette omschrijving"], "label": ["groen"],
                                        "trekker": [""], "next": ["/"]}, username="guest")
    # named checklist + items + afvinken
    cockpit2.dispatch(dd, "checklist_add", {"pid": [pid], "title": ["Stappen"], "next": ["/"]}, username="guest")
    clid = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["id"]
    cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["Stap 1"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["Stap 2"], "next": ["/"]}, username="guest")
    item1 = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]["id"]
    cockpit2.dispatch(dd, "check_toggle", {"pid": [pid], "clid": [clid], "item": [item1], "next": ["/"]}, username="guest")
    # opmerking in de feed
    cockpit2.dispatch(dd, "proj_comment", {"pid": [pid], "comment": ["Eerste voortgang"], "next": ["/"]}, username="guest")

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
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    cockpit2.dispatch(dd, "proj_edit", {"pid": [pid], "scope": ["Met label"], "label": ["koraal"],
                                        "trekker": [""], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "checklist_add", {"pid": [pid], "title": ["c"], "next": ["/"]}, username="guest")
    clid = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["id"]
    cockpit2.dispatch(dd, "check_add", {"pid": [pid], "clid": [clid], "text": ["a"], "next": ["/"]}, username="guest")
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
                                       "trekker": [f"person:{lotte.id}"], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Zonder trekker"], "col": ["actief"],
                                       "trekker": [""], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t", group="persoon")
    # swimlanes per persoon: Lotte en 'Geen trekker'
    assert "swim-h" in page and "Lotte Mulder" in page and "Geen trekker" in page


def test_circle_toont_directe_rollen_plus_ii(tmp_path):
    # cirkel toont projecten van haar DIRECTE rollen + Individueel Initiatief; geen eigen werk
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    cockpit2.dispatch(dd, "proj_add", {"owner": ["mother_earth__nooch__website_developer"],
                                       "scope": ["Rolproject"], "col": ["actief"], "next": ["/"]}, username="guest")
    # Individueel Initiatief: een project direct onder de cirkel via de ii:-pseudo-eigenaar
    cockpit2.dispatch(dd, "proj_add", {"owner": ["ii:mother_earth__nooch"],
                                       "scope": ["Eigen initiatief"], "col": ["actief"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "projects",
                                csrf_token="t", group="rol")
    assert "Rolproject" in page and "Website Developer" in page and "swim-h" in page
    assert "Individueel Initiatief" in page and "Eigen initiatief" in page   # II-lane bij een II-project


def test_circle_aggregeert_geen_subcirkel(tmp_path):
    # een project op een rol in subcirkel Nooch hoort NIET op het bord van Mother Earth
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    cockpit2.dispatch(dd, "proj_add", {"owner": ["mother_earth__nooch__website_developer"],
                                       "scope": ["Diep project"], "col": ["actief"], "next": ["/"]}, username="guest")
    me = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth", "projects", csrf_token="t", group="rol")
    assert "Diep project" not in me                  # subcirkel niet geaggregeerd
    assert "Subcirkels" in me and "eigen projectenbord" in me


def test_individual_initiative_owner(tmp_path):
    # een project oppakken als Individueel Initiatief (persoon, geen rol)
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    stefan = st.people.by_name("Stefan Wobben")
    ii = "ii:mother_earth__nooch"
    cockpit2.dispatch(dd, "proj_add", {"owner": [ii], "scope": ["Ad hoc stunt"], "col": ["actief"],
                                       "trekker": [f"person:{stefan.id}"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch", "projects",
                                csrf_token="t", group="rol")
    assert "Ad hoc stunt" in page and "Individueel Initiatief" in page


def test_leeg_bord_toont_geen_lege_lanes(tmp_path):
    # lege rol: geen swimlane-ruis, wel een '+ project'
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch__circle_rep", "projects", csrf_token="t")
    assert "<div class='swim'>" not in page       # geen lege lanes gerenderd
    assert "Nog geen projecten" in page and "qadd-top" in page   # wel een inline '+ project'


def test_inline_add_project_rol_en_cirkel(tmp_path):
    st = _st(tmp_path)
    role = "mother_earth__nooch__website_developer"
    page = cockpit2.render_node(st, role, "projects", csrf_token="t")
    assert "qadd-top" in page and "Te bereiken uitkomst" in page and "proj_add" in page
    # op een cirkel kun je de rol kiezen in de inline-add
    cpage = cockpit2.render_node(st, "mother_earth__nooch", "projects", csrf_token="t")
    assert "qadd-top" in cpage and "<select name='owner'>" in cpage


def test_modal_overlay_en_fragment(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Modaltest"], "col": ["actief"],
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    # board bevat de overlay + fragment-fetch
    board = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "id='ovl'" in board and "fragment=1" in board and "ovl-body" in board
    # fragment = alleen de detail-inhoud, geen volledige pagina
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "<!doctype" not in frag.lower() and "Modaltest" in frag and "Checklist" in frag
    # kolommen scrollen (pcol-scroll) en er is een inline '+ project' (geen aparte modal)
    assert "pcol-scroll" in board and "qadd-top" in board


def test_project_archiveren_default(tmp_path):
    # archiveren = blijft bestaan, uit het actieve board; herstellen kan
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Oud project"], "trekker": [""],
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    cockpit2.dispatch(dd, "proj_archive", {"pid": [pid], "next": ["/"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(pid)
    assert p is not None and p["archived"] is True          # blijft bestaan
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "Gearchiveerd (1)" in page and "Oud project" in page
    # herstellen
    cockpit2.dispatch(dd, "proj_unarchive", {"pid": [pid], "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["archived"] is False


def test_project_ai_trekker(tmp_path):
    # verbetering t.o.v. GlassFrog: een AI-inwoner als trekker
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    noochie = st.personas.add("Noochie")
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["SEO-audit"],
                                       "trekker": [f"persona:{noochie.id}"], "next": ["/"]}, username="guest")
    page = cockpit2.render_node(cockpit2._Stores(dd), role, "projects", csrf_token="t")
    assert "SEO-audit" in page and "Noochie" in page and "(AI)" in page


def test_persoonspagina_mijn_rollen(tmp_path):
    st = _st(tmp_path)
    lotte = st.people.by_name("Lotte Mulder")
    page = cockpit2.render_person(st, lotte.id)
    assert "Lotte Mulder" in page and "Rollen" in page          # rollen-tab (kop was "Mijn rollen")
    assert "Creator of Shoes" in page                          # een van haar rollen


def test_members_tab(tmp_path):
    st = _st(tmp_path)
    page = cockpit2.render_node(st, "mother_earth__nooch", "members")
    for naam in ("Lotte Mulder", "Stefan Wobben", "Nina Wolter", "Matthijs Boesten"):
        assert naam in page


def test_strategie_in_overview_en_tab_verwijderd(tmp_path):
    # strategy-tab is vervallen: de inhoud staat in de overview-tab, zonder aparte tab-knop
    st = _st(tmp_path)
    C = "mother_earth__nooch"
    st.strategies.set(C, {"core_sentence": "Kernzin ABC", "vision": "Visie", "beliefs": ["b1"]})
    page = cockpit2.render_node(st, C, "overview", csrf_token="TOK")
    assert "Kernzin ABC" in page          # strategie-inhoud nu in overview
    assert ">Purpose<" in page            # eigen Purpose-sectie behouden (geen dubbele chain)
    assert "&tab=strategy" not in page    # geen strategy-tab-knop meer in de tab-bar
