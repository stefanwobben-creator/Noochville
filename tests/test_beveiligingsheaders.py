"""Beveiligingsheaders op HTML-antwoorden (17 oktober 2026, besluit Stefan).

CSP met alleen `frame-src` (gepubliceerde Google Slides) en `frame-ancestors 'none'`, plus
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` en `Referrer-Policy:
strict-origin-when-cross-origin`. Geen `script-src`: inline scripts blijven werken."""
from __future__ import annotations

import http.client
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

from tests.test_password_change import EMAIL, _bootstrap, _seed_person

VERWACHT = {
    "Content-Security-Policy": "frame-src https://docs.google.com/presentation/; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@pytest.fixture
def server(tmp_path):
    dd = _bootstrap(tmp_path)
    _seed_person(dd, must_change=False, pw="eigenWachtwoord42")
    sessions = _auth.SessionStore()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessions,
                                users=_auth.UserStore(os.path.join(dd, "people.json"))))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], sessions
    httpd.shutdown()


def _get(port, pad, tok=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", pad, headers={"Cookie": f"nv_session={tok}"} if tok else {})
    r = c.getresponse()
    return r, r.read().decode()


@pytest.mark.parametrize("pad,sessie", [("/login", False), ("/l?p=%2F", False),
                                         ("/wachtwoord", True), ("/today", True), ("/projects", True)])
def test_de_paginas_laden_en_dragen_de_headers(server, pad, sessie):
    port, sessions = server
    r, html = _get(port, pad, sessions.create(EMAIL) if sessie else None)
    assert r.status == 200 and "<html" in html.lower()
    for naam, waarde in VERWACHT.items():
        assert r.getheader(naam) == waarde, (pad, naam, r.getheader(naam))
    assert r.getheader("Content-Type") == "text/html; charset=utf-8"


def test_ook_een_foutpagina_en_zonder_sessie(server):
    port, _s = server
    r, _ = _get(port, "/bestaat-niet-xyz")                      # zonder sessie: redirect naar /login
    assert r.status == 303
    r, _ = _get(port, "/login?next=/x")
    assert r.getheader("X-Frame-Options") == "DENY"


def test_er_is_geen_script_src_inline_scripts_blijven_werken():
    csp = dict(cockpit2.HTML_BEVEILIGING)["Content-Security-Policy"]
    assert "script-src" not in csp and "default-src" not in csp
    assert csp.startswith("frame-src ") and cockpit2.FRAME_SRC == ("https://docs.google.com/presentation/",)


def test_in_chromium(server):
    """(1) Inline scripts draaien nog (het anker-script van /login vult zijn veld). (2) Een iframe
    naar een niet-toegestane origin wordt door `frame-src` geblokkeerd — vóór er een verzoek uitgaat.
    (3) Een andere site mag Village niet inframen (`frame-ancestors 'none'`)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    port, sessions = server
    basis = f"http://127.0.0.1:{port}"
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:                                # noqa: BLE001
            pytest.skip(f"geen Chromium: {e}")
        pg = browser.new_page()
        pg.goto(f"{basis}/login#feit-1")
        assert pg.input_value("#anker") == "#feit-1"                          # (1)
        geblokkeerd = pg.evaluate("""() => new Promise(ok => {
            document.addEventListener('securitypolicyviolation',
                e => ok({richtlijn: e.violatedDirective, url: e.blockedURI}), {once: true});
            const f = document.createElement('iframe');
            f.src = 'https://example.com/';
            document.body.appendChild(f);
            setTimeout(() => ok(null), 3000);
        })""")
        assert geblokkeerd and geblokkeerd["richtlijn"].startswith("frame-src"), geblokkeerd   # (2)
        # (3) een pagina van een ANDERE origin (tweede server, andere poort) probeert Village te
        # inframen. Gemeten: zonder `frame-ancestors`/`X-Frame-Options` rendert de loginpagina er
        # gewoon in; met de headers wordt het een foutpagina (`chrome-error://`).
        class Buiten(BaseHTTPRequestHandler):
            def do_GET(self):
                b = f"<iframe id='f' src='{basis}/login'></iframe>".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b)

            def log_message(self, *a):
                pass

        buiten = ThreadingHTTPServer(("127.0.0.1", 0), Buiten)
        threading.Thread(target=buiten.serve_forever, daemon=True).start()
        try:
            pg.goto(f"http://127.0.0.1:{buiten.server_address[1]}/")
            pg.wait_for_timeout(1500)
            kader = next(f for f in pg.frames if f != pg.main_frame)
            assert kader.url.startswith("chrome-error://"), kader.url
            assert "sign in" not in (kader.evaluate("document.body ? document.body.innerText : ''") or "").lower()
        finally:
            buiten.shutdown()
        browser.close()
