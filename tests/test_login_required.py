"""Login-required + schone login-pagina (fix/login-required-clean-loginscreen).

Uitgelogd → overal 303 naar /login (behalve /login en /logout, die staan vóór de auth-check).
Noochie-chrome alleen voor een sessie: ingelogd wél, login-pagina/uitgelogd niet, guest (auth uit) wél.
Gedreven via de echte handler + HTTPServer; http.client volgt redirects niet, zodat we de 303 zien."""
from __future__ import annotations
import http.client
import threading
from http.server import HTTPServer

from nooch_village import auth as _auth
from nooch_village import cockpit2

ROOT = "mother_earth"


def _bootstrap(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _server(dd, sessions=None):
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "TESTTOKEN", sessions=sessions))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, httpd.server_address[1]


def _get(port, path, cookie=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Cookie": f"nv_session={cookie}"} if cookie else {}
    conn.request("GET", path, headers=headers)
    r = conn.getresponse()
    body = r.read().decode("utf-8", "replace")
    conn.close()
    return r, body


def test_uitgelogd_wordt_naar_login_gestuurd(tmp_path):
    dd = _bootstrap(tmp_path)
    httpd, port = _server(dd, sessions=_auth.SessionStore())   # auth aan, geen cookie = uitgelogd
    try:
        r, _ = _get(port, "/")
        assert r.status == 303 and "/login" in (r.getheader("Location") or "")
        r2, _ = _get(port, f"/node?id={ROOT}")                 # ook een niet-eerder-publieke route
        assert r2.status == 303 and "/login" in (r2.getheader("Location") or "")
    finally:
        httpd.shutdown()


def test_login_pagina_zonder_noochie_chrome(tmp_path):
    dd = _bootstrap(tmp_path)
    httpd, port = _server(dd, sessions=_auth.SessionStore())
    try:
        r, body = _get(port, "/login")
        assert r.status == 200
        assert "noo-rail" not in body and "noo-cta" not in body
    finally:
        httpd.shutdown()


def test_ingelogde_pagina_heeft_chrome(tmp_path):
    dd = _bootstrap(tmp_path)
    sessions = _auth.SessionStore()
    token = sessions.create("dev@nooch.earth")
    httpd, port = _server(dd, sessions=sessions)
    try:
        r, body = _get(port, f"/node?id={ROOT}", cookie=token)
        assert r.status == 200 and "noo-rail" in body
    finally:
        httpd.shutdown()


def test_guest_auth_uit_heeft_chrome(tmp_path):
    dd = _bootstrap(tmp_path)
    httpd, port = _server(dd, sessions=None)                   # auth uit → _session_username == "guest"
    try:
        r, body = _get(port, f"/node?id={ROOT}")
        assert r.status == 200 and "noo-rail" in body
    finally:
        httpd.shutdown()
