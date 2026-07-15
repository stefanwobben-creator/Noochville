"""De /inbox-pagina en de verwerk/archiveer-acties, end-to-end via cockpit2 (bootstrap + dispatch)."""
from __future__ import annotations

from nooch_village import cockpit2


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_inbox_toont_mention_met_bron_en_verwerkflow(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    pid = st.projects.create("mother_earth__nooch__website_developer", "Checkout flow", "human")
    e = st.projects.add_feed_entry(pid, "kijk hier even naar @jij", kind="comment", author_type="human")
    st.notif.add("person", person.id, pid, e["id"], by="noochie", snippet="kijk hier even naar @jij")
    html = cockpit2.render_inbox(st, [("person", person.id)], csrf_token="t")
    assert "kijk hier even naar" in html          # de tweeregelige samenvatting
    assert "nieuw" in html and "Checkout flow" in html   # kleurstatus + bron-link
    # de verwerk-flow ter plekke: de vijf-uitkomsten-kiezer (wall_outcome) + de FYI-klep (notif_done)
    assert "Verwerk ▸" in html and "wall_outcome" in html
    assert "notif_done" in html and "afgehandeld, geen uitkomst" in html


def test_inbox_zonder_bron_toont_alleen_fyi(tmp_path):
    # geen bron-comment (lege entry_id) → geen uitkomst-kiezer, wel de FYI-afhandeling
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    st.notif.add("person", person.id, "", by="noochie", snippet="losse tip")
    html = cockpit2.render_inbox(st, [("person", person.id)], csrf_token="t")
    assert "wall_outcome" not in html and "notif_done" in html


def test_inbox_verwerk_via_uitkomst_maakt_project_en_zet_verwerkt(tmp_path):
    # De kern van het nieuwe blok: één klik in de inbox maakt de uitkomst (project) ÉN zet de mention op
    # verwerkt met die uitkomst als historie. Hergebruikt de wall_outcome-handler met een nid.
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    owner = "mother_earth__nooch__website_developer"
    src = st.projects.create(owner, "Bron", "human")
    e = st.projects.add_feed_entry(src, "@jij pak dit op", kind="comment", author_type="human")
    n = st.notif.add("person", person.id, src, e["id"], by="dialoog", snippet="@jij pak dit op")
    cockpit2.dispatch(dd, "wall_outcome",
                      {"csrf": ["t"], "pid": [src], "item": [e["id"]], "nid": [n["id"]],
                       "otype": ["project"], "owner": [owner], "content": ["Onderzoek doen"],
                       "toelichting": ["want relevant"], "next": ["/inbox"]},
                      username="guest")
    st2 = cockpit2._Stores(dd)
    # 1) er is een nieuw project met de opgegeven inhoud als scope
    nieuw = [p for p in st2.projects._projects.values()
             if p.get("owner") == owner and p.get("scope") == "Onderzoek doen"]
    assert len(nieuw) == 1
    # 2) de mention is verwerkt, met de uitkomst als vastgelegde historie
    nn = st2.notif._find(n["id"])
    assert st2.notif.status_of(nn) == "verwerkt" and "project" in (nn.get("outcome") or "")


def test_inbox_afgehandeld_geen_uitkomst(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    n = st.notif.add("person", person.id, "", by="noochie", snippet="fyi")
    cockpit2.dispatch(dd, "notif_done", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    nn = st2.notif._find(n["id"])
    assert st2.notif.status_of(nn) == "verwerkt" and nn.get("outcome") == "afgehandeld, geen uitkomst"


def test_inbox_verwerkt_toont_historie_en_archiveer(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    n = st.notif.add("person", person.id, "", by="noochie", snippet="hoi")
    st.notif.mark_item_processed(n["id"], outcome="project: iets", by="Stefan")
    html = cockpit2.render_inbox(cockpit2._Stores(dd), [("person", person.id)], csrf_token="t")
    assert "uitkomst: project: iets" in html and "Stefan" in html    # historie zichtbaar
    assert "notif_archive" in html                                    # archiveren mag nu


def test_inbox_verwerk_en_archiveer_lifecycle(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    n = st.notif.add("person", person.id, "", by="noochie", snippet="hoi")
    # nieuw → gelezen
    cockpit2.dispatch(dd, "notif_read", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    assert cockpit2._Stores(dd).notif.status_of(cockpit2._Stores(dd).notif._find(n["id"])) == "gelezen"
    # → verwerkt
    cockpit2.dispatch(dd, "notif_processed", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    assert cockpit2._Stores(dd).notif.status_of(cockpit2._Stores(dd).notif._find(n["id"])) == "verwerkt"
    # archiveren (mag pas als verwerkt) → uit de open wachtrij
    cockpit2.dispatch(dd, "notif_archive", {"nid": [n["id"]], "next": ["/inbox"]}, username="guest")
    st2 = cockpit2._Stores(dd)
    assert st2.notif._find(n["id"])["archived"] is True
    assert st2.notif.open_for_targets([("person", person.id)]) == []


def test_inbox_leeg_toont_uitleg(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_inbox(cockpit2._Stores(dd), [("person", "niemand")], csrf_token="t")
    assert "Je inbox is leeg" in html
