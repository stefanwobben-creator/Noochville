"""CSRF per sessie (17 oktober 2026, besluit Stefan).

Het vaste, server-brede token is vervangen door een token per sessie: HMAC-SHA256 over het sessie-id
met het geheim uit csrf.json (`auth.csrf_voor`). csrf.json blijft bestaan, als sleutel. Plus een
tokencheck op POST /wachtwoord, ook bij een verplichte wijziging zonder huidig wachtwoord."""
from __future__ import annotations

import http.client
import os
import re
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2
from nooch_village.people import PeopleStore

from tests.test_password_change import EMAIL, TEMP, _bootstrap, _seed_person

GEHEIM = "server-geheim-uit-csrf-json"
PW = "eigenWachtwoord42"
ANDER = "lotte@nooch.earth"


# ── de afleiding ──────────────────────────────────────────────────────────────────────────────

def test_een_token_per_sessie_en_per_geheim():
    a, b = "sessietoken-A", "sessietoken-B"
    assert _auth.csrf_voor(GEHEIM, a) == _auth.csrf_voor(GEHEIM, a)          # stabiel binnen een sessie
    assert _auth.csrf_voor(GEHEIM, a) != _auth.csrf_voor(GEHEIM, b)
    assert _auth.csrf_voor(GEHEIM, a) != _auth.csrf_voor("ander-geheim", a)
    assert _auth.csrf_voor(GEHEIM, a) not in (GEHEIM, a, _auth.SessionStore._hash(a))
    assert _auth.csrf_voor(GEHEIM, "") == "" and _auth.csrf_voor("", a) == ""


# ── de echte handler ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def server(tmp_path):
    dd = _bootstrap(tmp_path)
    _seed_person(dd, must_change=False, pw=PW)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    lotte = ps.add("Lotte", ANDER)
    ps.set_password(lotte.id, _auth.hash_password(PW), must_change=False)
    sessions = _auth.SessionStore()
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                cockpit2.make_handler(dd, GEHEIM, sessions=sessions, users=users))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, httpd.server_address[1], sessions
    httpd.shutdown()


def _req(port, method, path, tok=None, velden=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    kop = {}
    if tok:
        kop["Cookie"] = f"nv_session={tok}"
    body = None
    if velden is not None:
        body = urllib.parse.urlencode(velden)
        kop["Content-Type"] = "application/x-www-form-urlencoded"
    c.request(method, path, body=body, headers=kop)
    r = c.getresponse()
    return r, r.read().decode("utf-8", "replace")


def _actie(port, tok, csrf):
    """Een onschuldige actie: een kanaal ontvolgen dat je niet volgt (wijzigt niets)."""
    return _req(port, "POST", "/action", tok, {"csrf": csrf, "action": "kanaal_ontvolg",
                                                "kanaal": "project:bestaat-niet", "next": "/"})[0].status


def _token_op_pagina(port, tok):
    _r, html = _req(port, "GET", "/wachtwoord", tok)
    return re.search(r'name="csrf" value="([^"]*)"', html).group(1)


def test_de_pagina_draagt_het_token_van_de_eigen_sessie(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    assert _token_op_pagina(port, tok) == _auth.csrf_voor(GEHEIM, tok)


def test_een_token_van_sessie_a_werkt_niet_in_sessie_b(server):
    _dd, port, sessions = server
    a, b = sessions.create(EMAIL), sessions.create(ANDER)
    assert _actie(port, a, _auth.csrf_voor(GEHEIM, a)) == 303                 # eigen token: door
    assert _actie(port, b, _auth.csrf_voor(GEHEIM, a)) == 403                 # andermans token: nee
    # ook twee sessies van DEZELFDE mens (twee apparaten) delen geen token
    a2 = sessions.create(EMAIL)
    assert _actie(port, a2, _auth.csrf_voor(GEHEIM, a)) == 403


def test_het_oude_vaste_token_werkt_niet_meer(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    assert _actie(port, tok, GEHEIM) == 403                                  # het geheim zelf is geen token
    assert _actie(port, tok, "") == 403


def test_na_uitloggen_en_opnieuw_inloggen_is_het_token_anders(server):
    _dd, port, _sessions = server

    def login():
        r, _ = _req(port, "POST", "/login", velden={"email": EMAIL, "password": PW, "next": "/"})
        assert r.status == 303
        return re.search(r"nv_session=([^;]+)", r.getheader("Set-Cookie")).group(1)

    eerste = login()
    oud = _token_op_pagina(port, eerste)
    _req(port, "GET", "/logout", eerste)
    assert _actie(port, eerste, oud) == 403                                   # sessie weg
    tweede = login()
    nieuw = _token_op_pagina(port, tweede)
    assert nieuw != oud
    assert _actie(port, tweede, oud) == 403 and _actie(port, tweede, nieuw) == 303


def test_wachtwoord_wijzigen_vraagt_het_token_ook_bij_een_verplichte_wijziging(server):
    dd, port, sessions = server
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.by_email(EMAIL)
    ps.set_password(p.id, _auth.hash_password(TEMP), must_change=True)
    tok = sessions.create(EMAIL)
    velden = {"new": "MijnNieuwe99x", "confirm": "MijnNieuwe99x", "next": "/"}
    r, txt = _req(port, "POST", "/wachtwoord", tok, velden)                  # zonder token
    assert r.status == 403 and "CSRF" in txt
    assert PeopleStore(os.path.join(dd, "people.json")).must_change(EMAIL)  # niets gewijzigd
    r, _ = _req(port, "POST", "/wachtwoord", tok, {**velden, "csrf": _auth.csrf_voor(GEHEIM, sessions.create(ANDER))})
    assert r.status == 403                                                   # token van een ander
    r, _ = _req(port, "POST", "/wachtwoord", tok, {**velden, "csrf": _auth.csrf_voor(GEHEIM, tok)})
    assert r.status == 303 and not PeopleStore(os.path.join(dd, "people.json")).must_change(EMAIL)


def test_een_fout_bij_wachtwoord_wijzigen_houdt_het_token_in_het_formulier(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    r, html = _req(port, "POST", "/wachtwoord", tok, {"current": "FOUT", "new": "MijnNieuwe99x",
                                                      "confirm": "MijnNieuwe99x",
                                                      "csrf": _auth.csrf_voor(GEHEIM, tok)})
    assert r.status == 200 and "incorrect" in html
    assert f'name="csrf" value="{_auth.csrf_voor(GEHEIM, tok)}"' in html


def test_zonder_sessies_blijft_het_vaste_token_gelden(tmp_path):
    """Auth uit (lokaal ontwikkelen, de meeste tests): geen sessie om aan te hangen, dus het
    meegegeven token blijft het token — exact het oude gedrag."""
    dd = _bootstrap(tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert _actie(httpd.server_address[1], None, "T") == 303
        assert _actie(httpd.server_address[1], None, "X") == 403
    finally:
        httpd.shutdown()


def test_zonder_sessie_is_het_token_nooit_leeg(server):
    """`compare_digest("", "")` is waar: een leeg token zou een leeg formulierveld goedkeuren zodra
    een route de sessiecheck vergeet. Zonder sessie dus een willekeurige waarde per verzoek."""
    _dd, port, sessions = server

    class Kop(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    h = cockpit2.make_handler("/dev/null", GEHEIM, sessions=sessions)
    nep = h.__new__(h)
    nep.headers = Kop()
    a, b = nep._csrf(), nep._csrf()
    assert a and b and a != b and not secrets_gelijk(a, "")
    nep.headers = Kop({"Cookie": "nv_session=verlopen-of-verzonnen"})
    assert nep._csrf() not in ("", GEHEIM)


def secrets_gelijk(x, y):
    import secrets
    return secrets.compare_digest(x, y)
