"""`/l?p=<pad>` — de tussenpagina voor links in een mail (17 oktober 2026, besluit Stefan).

Openbaar en zonder effect: hij stuurt alleen door naar een relatief pad binnen Village (dezelfde toets
als `next` na het inloggen, `auth.veilig_pad`), met `location.replace(p + location.hash)` en een
gewone link als noscript-terugval. Doel: een klik vanuit Gmail-web komt bij `SameSite=Strict` zonder
cookie aan; de doorverwijzing vanaf Village zelf draagt de cookie wél. De cookie blijft Strict."""
from __future__ import annotations

import http.client
import json
import os
import re
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

from tests.test_login_veilig import GELDIG, ONGELDIG
from tests.test_password_change import EMAIL, _bootstrap, _seed_person


def _doel(html: str) -> str:
    m = re.search(r"<script>location\.replace\((.*) \+ location\.hash\);</script>", html)
    return json.loads(m.group(1).replace("\\u003c", "<"))


@pytest.mark.parametrize("pad", GELDIG)
def test_een_relatief_pad_wordt_het_doel(pad):
    h = _auth.doorstuur_pagina(pad)
    assert _doel(h) == pad
    assert f'<a href="{pad.replace("&", "&amp;")}">' in h                      # noscript-terugval


@pytest.mark.parametrize("pad", ONGELDIG)
def test_alles_buiten_village_wordt_de_voordeur(pad):
    h = _auth.doorstuur_pagina(pad)
    assert _doel(h) == "/" and '<a href="/">' in h


def test_een_pad_kan_de_pagina_niet_openbreken():
    h = _auth.doorstuur_pagina('/x</script><script>alert(1)</script>"><img src=x>')
    script = h.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "</script>" not in script and "<" not in script                     # <, geen echte <
    assert '"><img' not in h and "<img" not in h                               # attribuut ge-escaped


def test_de_pagina_toont_niets_en_houdt_zich_buiten_zoekmachines():
    h = _auth.doorstuur_pagina("/project?pid=1")
    assert 'name="robots" content="noindex"' in h and 'content="no-referrer"' in h
    assert "<noscript>" in h and h.count("<a ") == 1


# ── de echte handler ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def server(tmp_path):
    dd = _bootstrap(tmp_path)
    _seed_person(dd, must_change=False, pw="eigenWachtwoord42")
    sessions = _auth.SessionStore()
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                cockpit2.make_handler(dd, "T", sessions=sessions, users=users))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, httpd.server_address[1], sessions
    httpd.shutdown()


def _get(port, pad, cookie=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", pad, headers={"Cookie": f"nv_session={cookie}"} if cookie else {})
    r = c.getresponse()
    return r, r.read().decode()


def test_openbaar_zonder_sessie_en_zonder_cookie_te_zetten(server):
    _dd, port, _s = server
    r, html = _get(port, "/l?p=" + urllib.parse.quote("/project?pid=abc", safe=""))
    assert r.status == 200 and _doel(html) == "/project?pid=abc"
    assert r.getheader("Set-Cookie") is None
    assert "no-store" in (r.getheader("Cache-Control") or "")
    r, html = _get(port, "/l?p=" + urllib.parse.quote("https://evil.com", safe=""))
    assert r.status == 200 and _doel(html) == "/"
    r, html = _get(port, "/l")                                                  # geen p → voordeur
    assert _doel(html) == "/"


def test_wijzigt_niets(server):
    dd, port, _s = server
    voor = {f: open(os.path.join(dd, f), "rb").read() for f in sorted(os.listdir(dd))
            if os.path.isfile(os.path.join(dd, f))}
    _get(port, "/l?p=/project%3Fpid%3Dabc")
    na = {f: open(os.path.join(dd, f), "rb").read() for f in sorted(os.listdir(dd))
          if os.path.isfile(os.path.join(dd, f))}
    assert voor == na


def test_de_cookie_blijft_strict():
    assert "SameSite=Strict" in _auth.set_cookie("x")


def test_in_chromium_draagt_de_doorverwijzing_de_strict_cookie_wel(server):
    """Een klik van een ANDERE site (hier `localhost` → `127.0.0.1`, twee sites) naar een Village-
    pagina komt zonder Strict-cookie aan en landt op /login. Dezelfde klik via `/l` landt ingelogd op
    het doel, mét anker."""
    sync_api = pytest.importorskip("playwright.sync_api")
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    village = f"http://127.0.0.1:{port}"
    doel = "/pagina?id=NOTE-1"
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:                                # noqa: BLE001
            pytest.skip(f"geen Chromium: {e}")
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "nv_session", "value": tok, "domain": "127.0.0.1", "path": "/",
                          "httpOnly": True, "secure": False, "sameSite": "Strict"}])
        pg = ctx.new_page()
        # de "mail": een pagina op een andere site met twee links
        rechtstreeks = f"{village}{doel}#feit-9"
        via_l = f"{village}/l?p={urllib.parse.quote(doel, safe='')}#feit-9"
        pg.route(f"http://localhost:{port}/mail", lambda route: route.fulfill(
            status=200, content_type="text/html",
            body=f"<a id='r' href='{rechtstreeks}'>r</a> <a id='l' href='{via_l}'>l</a>"))
        pg.goto(f"http://localhost:{port}/mail")
        with pg.expect_navigation():
            pg.click("#r")
        assert "/login?next=" in pg.url                                         # Strict: geen cookie
        pg.goto(f"http://localhost:{port}/mail")
        pg.click("#l")
        pg.wait_for_url(re.compile(r".*/pagina\?id=NOTE-1#feit-9$"))
        assert pg.url == f"{village}{doel}#feit-9"                              # ingelogd op het doel
        browser.close()
