"""/admin en het beheer van mensen: alleen de zicht-groep `admin` (besluit Stefan, 11 oktober 2026).

Getest met ECHTE INLOGSESSIES over HTTP, zoals een browser het doet: Stefan ziet het nav-item en de
pagina; een andere anchor lead en een gewoon lid zien geen item en krijgen een 404 — op /admin, op
een directe URL eronder, en op alle vier de people-acties; zonder sessie volgt de login.
"""
from __future__ import annotations

import http.client
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

STEFAN = "stefan@nooch.earth"
ANCHOR = "anchor@nooch.earth"
LID = "lid@nooch.earth"


@pytest.fixture
def server(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Stefan Wobben", STEFAN)
    st.assign.assign("mother_earth__circle_lead", "person", st.people.add("Andere Lead", ANCHOR).id)
    st.people.add("Gewoon Lid", LID)
    doel = st.people.add("Doel Persoon", "doel@nooch.earth")
    sessies = _auth.SessionStore()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, sessies, httpd.server_address[1], doel.id
    httpd.shutdown()


def _get(poort, pad, sessie=None):
    c = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
    c.request("GET", pad, headers={"Cookie": f"nv_session={sessie}"} if sessie else {})
    r = c.getresponse()
    return r.status, r.getheader("Location") or "", r.read().decode()


def _post(poort, velden, sessie):
    c = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
    c.request("POST", "/action", body=urllib.parse.urlencode({"csrf": _auth.csrf_voor("T", sessie), **velden}),
              headers={"Cookie": f"nv_session={sessie}", "Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode()


def test_stefan_ziet_het_item_en_de_pagina(server):
    dd, sessies, poort, _ = server
    s = sessies.create(STEFAN)
    status, _l, body = _get(poort, "/admin", s)
    assert status == 200 and "People" in body and "doel@nooch.earth" in body
    status, _l, body = _get(poort, "/projects", s)
    assert status == 200 and "href='/admin'" in body


@pytest.mark.parametrize("wie", [ANCHOR, LID])
def test_iemand_anders_ziet_geen_item_en_krijgt_404(server, wie):
    dd, sessies, poort, _ = server
    s = sessies.create(wie)
    for pad in ("/admin", "/admin/", "/admin/people", "/admin?x=1"):
        status, loc, body = _get(poort, pad, s)
        assert (status, loc) == (404, ""), pad                 # geen redirect, geen 403
        assert "doel@nooch.earth" not in body
    status, _l, body = _get(poort, "/projects", s)
    assert status == 200 and "href='/admin'" not in body and "<!--c2-admin-->" not in body


def test_onder_admin_bestaat_verder_niets_ook_niet_voor_stefan(server):
    dd, sessies, poort, _ = server
    assert _get(poort, "/admin/people", sessies.create(STEFAN))[0] == 404


def test_zonder_sessie_volgt_de_login(server):
    dd, sessies, poort, _ = server
    status, loc, _b = _get(poort, "/admin")
    assert status in (302, 303) and loc.startswith("/login")


@pytest.mark.parametrize("wie", [ANCHOR, LID])
def test_de_vier_acties_geven_404_en_veranderen_niets(server, wie):
    dd, sessies, poort, doel = server
    s = sessies.create(wie)
    voor = cockpit2._Stores(dd).people.get(doel)
    for velden in ({"action": "person_add", "voornaam": "Nieuw", "achternaam": "Iemand", "email": "nieuw@nooch.earth", "next": "/admin"},
                   {"action": "person_reset_password", "pid": doel, "next": "/admin"},
                   {"action": "person_edit", "pid": doel, "name": "Gewijzigd", "email": "x@nooch.earth", "next": "/admin"},
                   {"action": "person_remove", "pid": doel, "next": "/admin"}):
        status, body = _post(poort, velden, s)
        assert status == 404, velden["action"]
    st = cockpit2._Stores(dd)
    na = st.people.get(doel)
    assert na is not None and (na.name, na.email, na.password_hash) == (voor.name, voor.email, voor.password_hash)
    assert st.people.by_email("nieuw@nooch.earth") is None


def test_stefan_mag_de_vier_acties(server):
    dd, sessies, poort, doel = server
    s = sessies.create(STEFAN)
    assert _post(poort, {"action": "person_add", "voornaam": "Nieuw", "achternaam": "Iemand",
                         "email": "nieuw@nooch.earth", "next": "/admin"}, s)[0] == 200
    assert _post(poort, {"action": "person_reset_password", "pid": doel, "next": "/admin"}, s)[0] == 200
    assert _post(poort, {"action": "person_edit", "pid": doel, "name": "Gewijzigd", "email": "doel@nooch.earth",
                         "next": "/admin"}, s)[0] == 303
    assert cockpit2._Stores(dd).people.get(doel).name == "Gewijzigd"
    assert _post(poort, {"action": "person_remove", "pid": doel, "next": "/admin"}, s)[0] == 303
    st = cockpit2._Stores(dd)
    assert st.people.get(doel) is None and st.people.by_email("nieuw@nooch.earth") is not None
