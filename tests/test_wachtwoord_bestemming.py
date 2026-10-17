"""Na een GEDWONGEN wachtwoordwijziging landt de gebruiker waar hij heen wilde (17 oktober 2026).

Wie met `must_change_password` via een deeplink of `/l` binnenkwam, ging na het wijzigen naar "/":
de poort stuurde naar `/wachtwoord` zonder bestemming. Nu reist het pad mee als `next` (getoetst met
`veilig_pad`) en het `#anker` via de pagina (`veilig_anker`), net als bij `/login`."""
from __future__ import annotations

import os
import re
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2
from nooch_village.people import PeopleStore

from tests.test_login_veilig import ONGELDIG
from tests.test_password_change import EMAIL, TEMP, _bootstrap, _req, _seed_person

NIEUW = "MijnEigenNieuwe77"


@pytest.fixture
def server(tmp_path):
    dd = _bootstrap(tmp_path)
    _seed_person(dd, must_change=True)
    sessions = _auth.SessionStore()
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                cockpit2.make_handler(dd, "T", sessions=sessions, users=users))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, httpd.server_address[1], sessions
    httpd.shutdown()


def _token(port, tok, pad="/wachtwoord"):
    _r, html = _req(port, "GET", pad, cookie=tok)
    return re.search(r'name="csrf" value="([^"]*)"', html).group(1), html


def _wijzig(port, tok, nxt=None, anker=None, nieuw=NIEUW):
    csrf, _ = _token(port, tok)
    velden = {"new": nieuw, "confirm": nieuw, "csrf": csrf}
    if nxt is not None:
        velden["next"] = nxt
    if anker is not None:
        velden["anker"] = anker
    return _req(port, "POST", "/wachtwoord", cookie=tok, body=urllib.parse.urlencode(velden))


def test_de_poort_neemt_de_bestemming_mee(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    r, _ = _req(port, "GET", "/project?pid=abc123&back=%2Fnode", cookie=tok)
    assert r.status == 303
    assert r.getheader("Location") == "/wachtwoord?next=" + urllib.parse.quote("/project?pid=abc123&back=%2Fnode", safe="")
    r, _ = _req(port, "GET", "/", cookie=tok)                                  # voordeur: geen next
    assert r.getheader("Location") == "/wachtwoord"


def test_het_formulier_draagt_de_bestemming_en_bewaart_het_anker(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    _csrf, html = _token(port, tok, "/wachtwoord?next=" + urllib.parse.quote("/pagina?id=NOTE-1", safe=""))
    assert 'name="next" value="/pagina?id=NOTE-1"' in html
    assert 'name="anker" id="anker" value=""' in html and "a.value=location.hash" in html


def test_na_de_wijziging_naar_de_bestemming_met_anker(server):
    dd, port, sessions = server
    tok = sessions.create(EMAIL)
    r, _ = _wijzig(port, tok, nxt="/pagina?id=NOTE-1", anker="#feit-1a2b")
    assert r.status == 303 and r.getheader("Location") == "/pagina?id=NOTE-1#feit-1a2b"
    assert not PeopleStore(os.path.join(dd, "people.json")).must_change(EMAIL)


@pytest.mark.parametrize("nxt", ONGELDIG)
def test_een_bestemming_buiten_village_wordt_de_voordeur(server, nxt):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    r, _ = _wijzig(port, tok, nxt=nxt, anker="#x\"><script>")
    assert r.status == 303 and r.getheader("Location") == "/"


def test_zonder_next_naar_de_standaardpagina(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    r, _ = _wijzig(port, tok)
    assert r.status == 303 and r.getheader("Location") == "/"


def test_na_een_fout_blijven_bestemming_en_anker_staan(server):
    _dd, port, sessions = server
    tok = sessions.create(EMAIL)
    r, html = _wijzig(port, tok, nxt="/pagina?id=NOTE-1", anker="#feit-9", nieuw="kort")
    assert r.status == 200 and "at least 10" in html
    assert 'name="next" value="/pagina?id=NOTE-1"' in html and 'name="anker" id="anker" value="#feit-9"' in html


def test_in_chromium_landt_een_deeplink_na_de_gedwongen_wijziging_op_zijn_plek(server):
    """De hele keten: deeplink met anker zonder sessie → login met het tijdelijke wachtwoord → de poort
    stuurt naar /wachtwoord (bestemming als `next`, anker via de browser) → wijzigen → terug op de
    deeplink, mét anker."""
    sync_api = pytest.importorskip("playwright.sync_api")
    _dd, port, _s = server
    basis = f"http://127.0.0.1:{port}"
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:                                # noqa: BLE001
            pytest.skip(f"geen Chromium: {e}")
        pg = browser.new_page()
        pg.goto(f"{basis}/project?pid=abc123#feit-1a2b")
        pg.fill("#u", EMAIL)
        pg.fill("#p", TEMP)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        pg.wait_for_url(re.compile(r".*/wachtwoord\?next=.*"))
        assert pg.input_value("#anker") == "#feit-1a2b"
        pg.fill("#n", NIEUW)
        pg.fill("#n2", NIEUW)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        assert pg.url == f"{basis}/project?pid=abc123#feit-1a2b"
        browser.close()
