"""Herziene project-detailmodal: overzicht-kop met status-schakelaar en meta-grid."""
from __future__ import annotations

from nooch_village import cockpit2


def _setup(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    pid = st.projects.create(rid, "Nieuwe checkout flow", "human", description="x")
    return dd, pid


def test_detail_overzicht_kop(tmp_path):
    dd, pid = _setup(tmp_path)
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "<!doctype" not in frag.lower()
    # Details: tweekoloms, read-only rol/persoon + aangemaakt/zichtbaarheid (status in het …-menu)
    for k in ("pgrid", "pdisc", "details-cols",
              "<span class='dk'>Rol</span>", "<span class='dk'>Persoon</span>",
              "<span class='dk'>Aangemaakt</span>", "<span class='dk'>Zichtbaar</span>"):
        assert k in frag
    assert "Voortgang" not in frag and "<dt>Status</dt>" not in frag
    # statuswissel via het …-menu
    assert "cardmenu" in frag and "Actief" in frag and "Done" in frag


def test_status_menu_markeert_huidige(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["actief"], "csrf": ["t"], "next": ["/"]})
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "class='menuitem on'" in frag


def test_detail_readonly_geen_menu(tmp_path):
    dd, pid = _setup(tmp_path)
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="", fragment=True)
    assert "cardmenu" not in frag and "details-cols" in frag


def test_redesign_layout(tmp_path):
    dd, pid = _setup(tmp_path)
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    # full-width header met titel inline + …-menu (status/archiveren/verwijderen)
    assert "pcard-head" in frag and "titleform" in frag and "title-edit" in frag
    assert "cardmenu" in frag and "menu-h" in frag and "Archiveren" in frag and "Verwijderen" in frag
    # Details ingeklapt zonder status; omschrijving inline; bijlagen; rechterkolom = dialoog
    assert "detailsbox" in frag and "descform" in frag and "Bijlagen" in frag
    assert "pdisc" in frag and "Dialoog" in frag
    # geen apart 'Acties'-blok
    assert "Acties" not in frag


def test_bijlage_cards_trello(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "attach_add", {"pid": [pid], "url": ["https://nooch.earth/blog"],
                                         "title": ["Nooch blog"], "next": ["/"]})
    cockpit2.dispatch(dd, "attach_add", {"pid": [pid], "url": ["https://example.com/x"],
                                         "title": [""], "next": ["/"]})
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "attcard" in frag and "Nooch blog" in frag      # met titel
    assert "example.com" in frag                            # zonder titel -> domein
    assert "+ link" in frag and "Bijlagen" in frag
    # verwijderen
    aid = cockpit2._Stores(dd).projects.get(pid)["attachments"][0]["id"]
    cockpit2.dispatch(dd, "attach_remove", {"pid": [pid], "aid": [aid], "next": ["/"]})
    assert len(cockpit2._Stores(dd).projects.get(pid)["attachments"]) == 1


def test_attach_add_vereist_url(tmp_path):
    dd, pid = _setup(tmp_path)
    assert cockpit2._Stores(dd).projects.attach_add(pid, url="", title="x") is None


def test_emoji_reactie(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"], "text": ["hoi"], "next": ["/"]})
    eid = cockpit2._Stores(dd).projects.get(pid)["log"][0]["id"]
    cockpit2.dispatch(dd, "react_add", {"pid": [pid], "item": [eid], "emoji": ["👍"], "next": ["/"]})
    cockpit2.dispatch(dd, "react_add", {"pid": [pid], "item": [eid], "emoji": ["👍"], "next": ["/"]})
    assert cockpit2._Stores(dd).projects.get(pid)["log"][0]["reactions"] == {"👍": 2}
    frag = cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="t", fragment=True)
    assert "emoji-pick" in frag and "class='rx'" in frag and "👍 2" in frag
    # zoekbare picker met gecureerde set
    assert "emo-search" in frag and "emo-grid" in frag and "🚀" in frag
    node = cockpit2.render_node(cockpit2._Stores(dd), "mother_earth__nooch__website_developer",
                                "projects", csrf_token="t")
    assert "emoFilter" in node


def test_done_project_blijft_bewerkbaar(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "csrf": ["t"], "next": ["/"]})
    cockpit2.dispatch(dd, "proj_describe", {"pid": [pid], "description": ["toch nog"], "next": ["/"]})
    assert cockpit2._Stores(dd).projects.get(pid)["description"] == "toch nog"


def test_inline_edits_partieel(tmp_path):
    dd, pid = _setup(tmp_path)
    cockpit2.dispatch(dd, "proj_describe", {"pid": [pid], "description": ["beschrijving"], "next": ["/"]})
    cockpit2.dispatch(dd, "proj_rename", {"pid": [pid], "scope": ["Titel 2"], "next": ["/"]})
    p = cockpit2._Stores(dd).projects.get(pid)
    # rename mag de eerder gezette omschrijving NIET wissen
    assert p["scope"] == "Titel 2" and p["description"] == "beschrijving"
