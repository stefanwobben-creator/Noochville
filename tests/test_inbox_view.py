"""De /inbox-lijst, de /inbox/verwerk-wizard, en de verwerk-acties, end-to-end via cockpit2."""
from __future__ import annotations

from nooch_village import cockpit2

_OWNER = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


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
    assert "Spanning" in html and "Wat heb je nodig?" in html
    # intentie-labels + een diagnostische vraag + de enige sluitknop
    assert "Zelf iets doen" in html and "Is het resultaat complexer?" in html
    assert "notif_outcome" in html and "notif_klaar" in html
    assert "Niks nodig" not in html                       # 'Niks nodig'-knop is weg; Klaar regelt het
    assert "volgt in stap 2" in html                      # werkoverleg-uitkomst nog niet gebouwd


def test_verwerk_outcome_stapelt_en_houdt_open(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    src, eid, n = _spanning(st, person)
    # één uitkomst: een project op de eigenaar-rol (toelichting is optioneel, hier weggelaten)
    cockpit2.dispatch(dd, "notif_outcome",
                      {"csrf": ["t"], "nid": [n["id"]], "otype": ["project"], "owner": [_OWNER],
                       "content": ["Onderzoek doen"],
                       "next": [f"/inbox/verwerk?nid={n['id']}"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    nn = st2.notif._find(n["id"])
    # project bestaat, record heeft één entry, en het item is NIET gesloten (stapelen kan door)
    assert [p for p in st2.projects._projects.values() if p.get("scope") == "Onderzoek doen"]
    assert len(st2.notif.verwerkingen_of(nn)) == 1
    assert st2.notif.status_of(nn) == "gelezen"           # open gebleven, niet verwerkt


def test_verwerk_meerdere_uitkomsten_in_record(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    src, eid, n = _spanning(st, person)
    for _ in range(2):
        cockpit2.dispatch(dd, "notif_outcome",
                          {"csrf": ["t"], "nid": [n["id"]], "otype": ["note"], "note_role": [_OWNER],
                           "content": ["Vast te leggen inzicht"], "toelichting": ["want relevant"],
                           "next": [f"/inbox/verwerk?nid={n['id']}"]}, username="guest")
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
    assert "rdr-vier" in html and "rdr-kader" in html and "Dit legde je vast" in html


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
    assert "Je inbox is leeg" in html


def test_verwerk_onbekend_item(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_verwerk(cockpit2._Stores(dd), None, csrf_token="t")
    assert "bestaat niet meer" in html
