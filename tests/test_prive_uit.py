"""Privé-projecten staan uit (besluit Stefan, 11 oktober 2026).

De optie "Only for this circle" is nooit gebruikt (0 van 458). De server weigert de vlag bij
aanmaken en zetten — ook bij een handmatig POST-verzoek met een echte sessie — en de UI biedt hem niet
meer aan. De leesregels, de guard en de datavlag zelf blijven staan (#726).
"""
from __future__ import annotations

import http.client
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

ROL = "mother_earth__nooch__financial_controller"
LID = "lid@nooch.earth"


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Lid Persoon", LID).id)
    return dd


def _post(dd, velden, wie=LID):
    sessies = _auth.SessionStore()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        c.request("POST", "/action", body=urllib.parse.urlencode({"csrf": "T", "next": "/x", **velden}),
                  headers={"Cookie": f"nv_session={sessies.create(wie)}",
                           "Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        return r.status, urllib.parse.unquote(r.getheader("Location") or "")
    finally:
        httpd.shutdown()


def test_aanmaken_met_privé_vlag_wordt_geweigerd_ook_bij_een_handmatig_post(dorp):
    voor = len(cockpit2._Stores(dorp).projects.all())
    status, loc = _post(dorp, {"action": "proj_add", "owner": ROL, "scope": "Geheim project", "private": "1"})
    assert status == 303 and "Private projects are switched off" in loc
    assert len(cockpit2._Stores(dorp).projects.all()) == voor
    # zonder de vlag gaat het gewoon
    lid = cockpit2._Stores(dorp).people.by_email(LID).id
    _post(dorp, {"action": "proj_add", "owner": ROL, "scope": "Gewoon project", "trekker": f"person:{lid}"})
    nieuw = [p for p in cockpit2._Stores(dorp).projects.all() if p.get("scope") == "Gewoon project"]
    assert len(nieuw) == 1 and not nieuw[0].get("private")


def test_een_bestaand_project_privé_zetten_wordt_geweigerd(dorp):
    st = cockpit2._Stores(dorp)
    pid = st.projects.create(ROL, "Bestaand", "human")
    status, loc = _post(dorp, {"action": "proj_setprivate", "pid": pid, "private": "1"})
    assert "Private projects are switched off" in loc
    assert not cockpit2._Stores(dorp).projects.get(pid).get("private")


def test_een_oud_privé_project_kan_terug_naar_zichtbaar(dorp):
    st = cockpit2._Stores(dorp)
    pid = st.projects.create(ROL, "Oud privé", "human")
    st.projects.edit(pid, private=True, allow_done=True)        # de datavlag zelf bestaat nog
    _post(dorp, {"action": "proj_setprivate", "pid": pid, "private": ""})
    assert not cockpit2._Stores(dorp).projects.get(pid).get("private")


def test_route_werk_weigert_de_privé_vlag(dorp):
    with pytest.raises(ValueError):
        cockpit2.route_werk(cockpit2._Stores(dorp), tekst="iets", rol=ROL, prive=True)


def test_de_ui_biedt_de_optie_niet_meer(dorp):
    from nooch_village.views.projects import render_project
    from nooch_village.views import vangst
    st = cockpit2._Stores(dorp)
    pid = st.projects.create(ROL, "Zichtbaar", "human")
    html = render_project(st, pid, csrf_token="T", username="guest")
    assert "proj_setprivate" not in html and "Whole circle tree" in html
    oud = st.projects.create(ROL, "Oud privé", "human")
    st.projects.edit(oud, private=True, allow_done=True)
    assert "proj_setprivate" in render_project(cockpit2._Stores(dorp), oud, csrf_token="T", username="guest")
    bron = "\n".join(r for r in open(vangst.__file__, encoding="utf-8").read().splitlines()
                     if not r.strip().startswith("#"))
    assert "name='prive'" not in bron and "Only visible to this circle" not in bron
