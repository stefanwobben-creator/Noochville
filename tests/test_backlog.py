"""Backlog Builder — store + dispatch-autorisatie (prototype; geen Noochie/LLM)."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.backlog import BacklogStore

WD = "mother_earth__nooch__website_developer"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


# ── store ─────────────────────────────────────────────────────────────────────

def test_store_add_get_all(tmp_path):
    s = BacklogStore(str(tmp_path / "b.json"))
    it = s.add("Zoekbalk kapot", "stuk", "bug", "website", "p1")
    assert it and it.staat == "ruw" and it.type == "bug" and it.domein == "website"
    assert it.impact is None and it.effort is None and it.inbrenger_id == "p1"
    assert s.get(it.id).titel == "Zoekbalk kapot"
    assert len(s.all()) == 1
    # lege titel → geen item; onbekend type/domein → veilige default
    assert s.add("", "x", "bug", "website", "p1") is None
    it2 = s.add("Idee X", "", "onzin", "elders", "p1")
    assert it2.type == "idee" and it2.domein == "village"


def test_store_update_staat(tmp_path):
    s = BacklogStore(str(tmp_path / "b.json"))
    it = s.add("T", "", "wens", "village", "p1")
    assert s.update_staat(it.id, "geformuleerd") is True
    assert s.get(it.id).staat == "geformuleerd"
    assert s.update_staat(it.id, "onbekend") is False        # ongeldige staat
    assert s.update_staat("bestaat-niet", "ruw") is False


def test_store_update_prioriteit(tmp_path):
    s = BacklogStore(str(tmp_path / "b.json"))
    it = s.add("T", "", "wens", "village", "p1")
    assert s.update_prioriteit(it.id, "hoog", "1d") is True
    g = s.get(it.id); assert g.impact == "hoog" and g.effort == "1d"
    # ongeldige waarde wist het label (None)
    s.update_prioriteit(it.id, "enorm", "3j")
    g = s.get(it.id); assert g.impact is None and g.effort is None


def test_store_persistentie(tmp_path):
    p = str(tmp_path / "b.json")
    it = BacklogStore(p).add("Bewaard", "", "idee", "website", "p1")
    assert BacklogStore(p).get(it.id).titel == "Bewaard"     # verse instantie leest van schijf


# ── dispatch + autorisatie ──────────────────────────────────────────────────

def _form(**kw):
    f = {"next": ["/"]}
    f.update({k: [v] for k, v in kw.items()})
    return f


def test_add_iedereen_ingelogd(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    p = st.people.add("Iemand", "iemand@nooch.earth")
    _, msg = cockpit2.dispatch(dd, "backlog_add",
                               _form(titel="Bug A", beschrijving="x", type="bug", domein="website"),
                               username="iemand@nooch.earth")
    assert "submitted" in msg
    items = cockpit2._Stores(dd).backlog.all()
    assert len(items) == 1 and items[0].inbrenger_id == p.id


def test_update_staat_alleen_website_developer(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    dev = st.people.add("Dev", "dev@nooch.earth"); st.assign.assign(WD, "person", dev.id)
    st.people.add("Buiten", "buiten@nooch.earth")
    bid = cockpit2._Stores(dd).backlog.add("T", "", "wens", "village", "").id
    # buitenstaander geweigerd
    _, deny = cockpit2.dispatch(dd, "backlog_update_staat", _form(bid=bid, staat="geformuleerd"),
                                username="buiten@nooch.earth")
    assert "No access" in deny and "Website Developer" in deny
    assert cockpit2._Stores(dd).backlog.get(bid).staat == "ruw"
    # rolvervuller mag
    _, ok = cockpit2.dispatch(dd, "backlog_update_staat", _form(bid=bid, staat="geformuleerd"),
                              username="dev@nooch.earth")
    assert "updated" in ok
    assert cockpit2._Stores(dd).backlog.get(bid).staat == "geformuleerd"


def test_update_prioriteit_alleen_website_developer(tmp_path):
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    st.people.add("Buiten", "buiten@nooch.earth")
    bid = cockpit2._Stores(dd).backlog.add("T", "", "wens", "village", "").id
    _, deny = cockpit2.dispatch(dd, "backlog_update_prioriteit", _form(bid=bid, impact="hoog", effort="1d"),
                                username="buiten@nooch.earth")
    assert "No access" in deny
    assert cockpit2._Stores(dd).backlog.get(bid).impact is None


def test_backlog_scherm_beheerder_versus_inbrenger(tmp_path):
    from nooch_village.views.backlog import render_backlog
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    dev = st.people.add("Dev", "dev@nooch.earth"); st.assign.assign(WD, "person", dev.id)
    st.people.add("Anon", "anon@nooch.earth")
    # WD-rolvervuller ziet beheer + indien-formulier
    page = render_backlog(cockpit2._Stores(dd), csrf="TOK", username="dev@nooch.earth")
    assert "Backlog Builder" in page and "Manage — all items by state" in page and "backlog_add" in page
    # buitenstaander ziet wel indienen, niet beheer
    page2 = render_backlog(cockpit2._Stores(dd), csrf="TOK", username="anon@nooch.earth")
    assert "backlog_add" in page2 and "Manage — all items by state" not in page2


def test_website_developer_heeft_weer_een_gewone_notes_tab(tmp_path):
    # De Backlog Builder verving hier de notes; daardoor was dit de enige rol zonder notes — en
    # sinds de wiki-laag dus ook zonder pagina's.
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    dev = st.people.add("Dev", "dev@nooch.earth"); st.assign.assign(WD, "person", dev.id)
    a = cockpit2._Stores(dd).att.add(WD, "note", title="Deploy-notities")
    page = cockpit2.render_node(cockpit2._Stores(dd), WD, "notes", csrf_token="TOK",
                                username="dev@nooch.earth")
    assert "Deploy-notities" in page and "artefact_add" in page      # gewone notes-tab
    assert f"/pagina?id={a.id}" in page                              # en dus een wiki-pagina
    assert "Manage — all items by state" not in page                 # geen backlog meer hier


def test_backlog_woont_onder_tools_van_de_rol(tmp_path):
    dd = _dd(tmp_path)
    page = cockpit2.render_node(cockpit2._Stores(dd), WD, "tools", csrf_token="TOK",
                                username="guest")
    assert "Backlog Builder" in page and "/backlog" in page
