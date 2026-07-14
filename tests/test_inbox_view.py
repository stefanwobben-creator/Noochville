"""De /inbox-pagina en de verwerk/archiveer-acties, end-to-end via cockpit2 (bootstrap + dispatch)."""
from __future__ import annotations

from nooch_village import cockpit2


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_inbox_toont_mention_met_bron_en_status(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    person = st.people.all()[0]
    pid = st.projects.create("mother_earth__nooch__website_developer", "Checkout flow", "human")
    st.notif.add("person", person.id, pid, by="noochie", snippet="kijk hier even naar @jij")
    html = cockpit2.render_inbox(st, [("person", person.id)], csrf_token="t")
    assert "kijk hier even naar" in html          # de tweeregelige samenvatting
    assert "nieuw" in html and "Checkout flow" in html   # kleurstatus + bron-link
    assert "notif_processed" in html              # de verwerk-knop


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
