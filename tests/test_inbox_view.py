"""De /inbox-lijst, de /inbox/verwerk-wizard, en de verwerk-acties, end-to-end via cockpit2."""
from __future__ import annotations

from nooch_village import cockpit2

_OWNER = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _mens(st):
    """De eerste persoon, mét e-mail — de dispatch herkent de ingelogde mens daarop, en een actie
    'voor jezelf' moet ergens kunnen landen."""
    p = st.people.all()[0]
    if not getattr(p, "email", ""):
        st.people.update(p.id, email="stefan@nooch.earth")
        p = st.people.get(p.id)
    return p


def _spanning(st, person, snippet="@jij kijk hier even naar"):
    """Een inbox-item met een echte bron-comment (project + entry), zoals een @mention 'm maakt."""
    src = st.projects.create(_OWNER, "Bron-project", "human")
    e = st.projects.add_feed_entry(src, snippet, kind="comment", author_type="human")
    n = st.notif.add("person", person.id, src, e["id"], by="dialoog", snippet=snippet)
    return src, e["id"], n


def test_inbox_lijst_is_kaal(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    _spanning(st, person, "@jij een hele lange tekst " + "x" * 200)
    html = cockpit2.render_inbox(st, [("person", person.id)], csrf_token="t")
    assert "…" in html                                    # titel afgekapt op één regel
    assert "/inbox/verwerk?nid=" in html                  # Verwerk-link naar de wizard-pagina
    assert "notif_delete" in html                         # prullenbak
    assert "wall_outcome" not in html                     # geen inline formulieren meer in de rij


def test_verwerk_pagina_toont_spanning_en_wizard(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    _, _, n = _spanning(st, person)
    html = cockpit2.render_verwerk(st, n, csrf_token="t")
    assert "Tension" in html and "What do you do with this?" in html
    # TWEE CONCRETE FLOWS, met de één-regel-uitleg naast het label — die uitleg IS de pedagogie:
    # aan het verschil tussen 'één handeling' en 'werk dat een rol draagt' leer je roldenken.
    assert "Action" in html and "comes back in the inbox" in html
    assert "Project" in html and "for a role you fill yourself" in html
    assert "notif_outcome" in html and "notif_klaar" in html
    # de oude abstracte bakken zijn weg
    for oud in ("What do you need?", "Do something yourself", "Have someone else do something",
                "Share, get or record info", "coming in step 2"):
        assert oud not in html, oud


def test_verwerk_outcome_stapelt_en_houdt_open(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    person = _mens(st)
    src, eid, n = _spanning(st, person)
    # één uitkomst: een actie voor jezelf (geen doel gekozen → je eigen inbox)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                       "content": ["Onderzoek doen"],
                       "next": [f"/inbox/verwerk?nid={n['id']}"]}, username=person.email)
    st2 = cockpit2._Stores(dd)
    nn = st2.notif._find(n["id"])
    assert len(st2.notif.verwerkingen_of(nn)) == 1
    assert st2.notif.status_of(nn) == "gelezen"           # open gebleven, stapelen kan door


def test_verwerk_meerdere_uitkomsten_in_record(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    person = _mens(st)
    src, eid, n = _spanning(st, person)
    for _ in range(2):
        cockpit2.dispatch(dd, "notif_outcome",
                          {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                           "content": ["Vast te leggen inzicht"],
                           "next": [f"/inbox/verwerk?nid={n['id']}"]}, username=person.email)
    nn = cockpit2._Stores(dd).notif._find(n["id"])
    assert len(cockpit2._Stores(dd).notif.verwerkingen_of(nn)) == 2   # twee uitkomsten uit één spanning


def test_verwerk_klaar_sluit_item(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    _, _, n = _spanning(st, person)
    cockpit2.dispatch(dd, "notif_klaar", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    nn = cockpit2._Stores(dd).notif._find(n["id"])
    assert cockpit2._Stores(dd).notif.status_of(nn) == "verwerkt"


def test_klaar_met_nul_uitkomsten_legt_geen_uitkomst_vast(tmp_path):
    # Sluiten zonder iets te doen: 'Klaar' zet 'geen uitkomst' in het record (zichtbaar voor de raad).
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    n = st.notif.add("person", person.id, "", by="noochie", snippet="fyi")
    cockpit2.dispatch(dd, "notif_klaar", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    nn = st2.notif._find(n["id"])
    assert st2.notif.status_of(nn) == "verwerkt"
    vs = st2.notif.verwerkingen_of(nn)
    assert vs and vs[0]["otype"] == "none" and vs[0]["label"] == "geen uitkomst"


def test_klaar_viert_de_zojuist_verwerkte_spanning(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    _, _, n = _spanning(st, person)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["note"], "note_role": [_OWNER],
                       "content": ["Inzicht vastleggen"], "next": [f"/inbox/verwerk?nid={n['id']}"]},
                      username="guest")
    nxt, _ = cockpit2.dispatch(dd, "notif_klaar", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    assert nxt == f"/inbox?done={n['id']}"                # redirect markeert de zojuist-verwerkte spanning
    html = cockpit2.render_inbox(cockpit2._Stores(dd), [("person", person.id)], csrf_token="t", done=n["id"])
    assert "rdr-vier" in html and "rdr-kader" in html and "This is what you recorded" in html


def test_prullenbak_haalt_uit_wachtrij(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    n = st.notif.add("person", person.id, "", by="noochie", snippet="ruis")
    cockpit2.dispatch(dd, "notif_delete", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.notif._find(n["id"])["deleted"] is True
    assert st2.notif.open_for_targets([("person", person.id)]) == []


def test_verwerkt_toont_record_en_archiveer(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    n = st.notif.add("person", person.id, "", by="noochie", snippet="hoi")
    st.notif.add_outcome(n["id"], intent="self", otype="project", label="project: iets", by="Stefan")
    st.notif.mark_done(n["id"], by="Stefan")
    html = cockpit2.render_inbox(cockpit2._Stores(dd), [("person", person.id)], csrf_token="t")
    assert "project: iets" in html and "notif_archive" in html


def test_inbox_leeg_toont_uitleg(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_inbox(cockpit2._Stores(dd), [("person", "niemand")], csrf_token="t")
    assert "Your inbox is empty" in html


def test_verwerk_onbekend_item(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_verwerk(cockpit2._Stores(dd), None, csrf_token="t")
    assert "no longer exists" in html


def test_inbox_chrome_bevat_launcher_drawer_modal(tmp_path):
    html = cockpit2.render_inbox_chrome(csrf_token="tok")
    assert "ibx-launch" in html and "ibx-drawer" in html and "ibx-frame" in html   # launcher + drawer + modal-iframe
    assert "ibxOpen" in html and "ibxRefresh" in html                              # de drawer-JS
    assert '"tok"' in html and "src='/callbar'" not in html                        # csrf ingebed, geen call bar


def test_inbox_frag_geeft_count_en_rijen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    _spanning(st, person, "@jij kijk hier")
    frag = cockpit2.render_inbox_frag(st, [("person", person.id)], csrf_token="t")
    assert "data-count='1'" in frag and "ibx-row" in frag and "kijk hier" in frag


def test_notif_add_zelf_spanning_toevoegen(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    cockpit2.dispatch(dd, "notif_add", {"text": ["eigen gedachte"], "role": [_OWNER], "next": ["/inbox"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    hits = [n for n in st2.notif.for_targets([("role", _OWNER)]) if n.get("snippet") == "eigen gedachte"]
    assert len(hits) == 1 and hits[0]["by"] == "zelf"


def test_actie_naar_een_andere_rol_landt_in_diens_inbox(tmp_path):
    """FLOW 1 met `@`. Dezelfde routing als het werkoverleg en de wizard (`route_werk`): een
    mens-vervulde rol krijgt het in zijn inbox. De inbox heeft dus GEEN eigen routing — een tweede
    kopie van die regel zou na één wijziging uit de pas lopen."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = _mens(st)
    _, _, n = _spanning(st, person)
    st.assign.assign(_OWNER, "person", person.id)          # mens op de rol → hij leest een inbox
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"],
                       "doel": [f"role:{_OWNER}"], "content": ["wat denk jij?"],
                       "next": [f"/inbox/verwerk?nid={n['id']}"]}, username=person.email)
    st2 = cockpit2._Stores(dd)
    gekregen = [x for x in st2.notif.for_targets([("role", _OWNER)])
                if x.get("snippet") == "wat denk jij?"]
    assert len(gekregen) == 1
    assert (gekregen[0].get("herkomst") or "").startswith("↳")     # wélgevormd: waar komt het vandaan


def test_actie_gekoppeld_aan_een_project_wordt_een_checklist_stap(tmp_path):
    """De project-checklist is de bestaande checklist van dat project — geen tweede lijst."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    src, _eid, n = _spanning(st, person)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["action"], "pid_link": [src],
                       "content": ["de bron nog even nakijken"],
                       "next": [f"/inbox/verwerk?nid={n['id']}"]}, username="guest")
    p = cockpit2._Stores(dd).projects.get(src)
    stappen = [i.get("text") for cl in (p.get("checklists") or []) for i in (cl.get("items") or [])]
    assert "de bron nog even nakijken" in stappen
