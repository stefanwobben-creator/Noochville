"""Login veilig (17 oktober 2026, besluit Stefan):

- `next` bij /login en /wachtwoord is alleen een relatief pad dat met één `/` begint. `//`, `\\`, een
  schema (`https:`, `javascript:`) en gecodeerde varianten (`%2f%2f`) worden "/";
- het `#anker` reist mee over de login: de pagina onthoudt `location.hash`, de server plakt het
  (getoetst) achter `next`;
- elke login laat een tijdstip achter op de people-rij (de laatste 30, geen IP, geen nieuwe store);
- een onbekend e-mailadres kost even veel bcrypt-werk als een bekend: de responstijd verraadt niets.
"""
from __future__ import annotations

import os
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2
from nooch_village.people import PeopleStore

from tests.test_password_change import EMAIL, _bootstrap, _req, _seed_person

PW = "eigenWachtwoord42"

GELDIG = ["/", "/project?pid=abc123", "/pagina?id=NOTE-1", "/search?q=a%20b",
          "/messages?k=dm%3Aa%7Cb", "/a:b"]
ONGELDIG = ["", "//evil.com", "///evil.com", "/\\evil.com", "\\evil.com", "https://evil.com",
            "http:evil.com", "javascript:alert(1)", "JavaScript:alert(1)", "evil.com",
            "/%2f%2fevil.com", "/%2F%2Fevil.com", "%2f%2fevil.com", "/%252f%252fevil.com",
            "/%5cevil.com", "/%5C%5Cevil.com", "/%09/evil.com", "/x%0d%0aSet-Cookie:a=b",
            "/ok path", "/x\ty", " /x", "/x\n"]


@pytest.mark.parametrize("pad", GELDIG)
def test_een_relatief_pad_blijft(pad):
    assert _auth.veilig_pad(pad) == pad


@pytest.mark.parametrize("pad", ONGELDIG)
def test_alles_buiten_village_wordt_de_voordeur(pad):
    assert _auth.veilig_pad(pad) == "/"


def test_geen_tekst_is_ook_de_voordeur():
    assert _auth.veilig_pad(None) == "/" and _auth.veilig_pad(["/x"]) == "/"


@pytest.mark.parametrize("anker,uit", [("#feit-1a2b", "#feit-1a2b"), ("#vraag-plastic", "#vraag-plastic"),
                                       ("#kop=Over%20ons", "#kop=Over%20ons"), ("", ""), ("#", ""),
                                       ("#a\"><script>", ""), ("feit-1", ""), ("#" + "a" * 201, "")])
def test_alleen_een_net_anker_reist_mee(anker, uit):
    assert _auth.veilig_anker(anker) == uit


# ── de echte handler ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def server(tmp_path):
    dd = _bootstrap(tmp_path)
    p = _seed_person(dd, must_change=False, pw=PW)
    sessions = _auth.SessionStore()
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                cockpit2.make_handler(dd, "TESTTOKEN", sessions=sessions, users=users))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, p, httpd.server_address[1], sessions
    httpd.shutdown()


def _login(port, nxt, anker="", pw=PW):
    body = urllib.parse.urlencode({"email": EMAIL, "password": pw, "next": nxt, "anker": anker})
    return _req(port, "POST", "/login", body=body)


@pytest.mark.parametrize("nxt", ONGELDIG)
def test_na_inloggen_nooit_naar_buiten(server, nxt):
    _dd, _p, port, _s = server
    r, _ = _login(port, nxt)
    assert r.status == 303 and r.getheader("Location") == "/"


def test_na_inloggen_terug_naar_het_pad_met_het_anker(server):
    _dd, _p, port, _s = server
    r, _ = _login(port, "/project?pid=abc123", "#feit-1a2b")
    assert r.status == 303 and r.getheader("Location") == "/project?pid=abc123#feit-1a2b"
    r, _ = _login(port, "/project?pid=abc123", "#x\"><script>")          # vies anker valt weg
    assert r.getheader("Location") == "/project?pid=abc123"


def test_een_fout_wachtwoord_houdt_pad_en_anker_vast(server):
    _dd, _p, port, _s = server
    r, html = _login(port, "/pagina?id=NOTE-1", "#feit-9", pw="fout")
    assert r.status == 200 and "incorrect" in html
    assert "name='next' value='/pagina?id=NOTE-1'" in html.replace('"', "'")
    assert "name='anker' id='anker' value='#feit-9'" in html.replace('"', "'")


def test_de_loginpagina_toetst_next_en_bewaart_location_hash(server):
    _dd, _p, port, _s = server
    _r, html = _req(port, "GET", "/login?next=" + urllib.parse.quote("//evil.com"))
    assert 'name="next" value="/"' in html
    assert "a.value=location.hash" in html
    _r, html = _req(port, "GET", "/login?next=" + urllib.parse.quote('/x?a="><script>'))
    assert "<script>alert" not in html and '"><script>' not in html


@pytest.mark.parametrize("nxt,waar", [("https://evil.com", "/"), ("//evil.com", "/"),
                                      ("/%2f%2fevil.com", "/"), ("/project?pid=1", "/project?pid=1")])
def test_wachtwoord_next_nooit_naar_buiten(server, nxt, waar):
    _dd, _p, port, sessions = server
    tok = sessions.create(EMAIL)
    nieuw = "EenNieuwWachtwoord77"
    body = urllib.parse.urlencode({"current": PW, "new": nieuw, "confirm": nieuw, "next": nxt})
    r, _ = _req(port, "POST", "/wachtwoord", cookie=tok, body=body)
    assert r.status == 303 and r.getheader("Location") == waar


# ── logins vastleggen ─────────────────────────────────────────────────────────────────────────

def test_een_login_laat_een_tijdstip_achter_zonder_ip(server):
    dd, p, port, _s = server
    _login(port, "/")
    _login(port, "/")
    ps = PeopleStore(os.path.join(dd, "people.json"))
    assert len(ps.logins(p.id)) == 2
    rij = ps._items[p.id]
    assert all(isinstance(t, float) for t in rij["logins"])                 # alleen een tijdstip
    assert not any("ip" in k.lower() or "addr" in k.lower() for k in rij)


def test_hooguit_dertig_logins_de_oudste_valt_weg(tmp_path):
    ps = PeopleStore(str(tmp_path / "people.json"))
    p = ps.add("Lotte", "lotte@nooch.earth")
    for _ in range(35):
        ps.touch_login("LOTTE@nooch.earth")
    tijden = PeopleStore(str(tmp_path / "people.json")).logins(p.id)
    assert len(tijden) == 30 and tijden == sorted(tijden)


# ── geen tijdverschil tussen bekend en onbekend ───────────────────────────────────────────────

def test_een_onbekend_adres_doet_ook_een_bcrypt_vergelijking(tmp_path, monkeypatch):
    dd = _bootstrap(tmp_path)
    _seed_person(dd, must_change=False, pw=PW)
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    users.verify_by_email("niemand@nooch.earth", "x")                      # dummy-hash aanmaken
    tel = []
    echt = _auth.bcrypt.checkpw
    monkeypatch.setattr(_auth.bcrypt, "checkpw", lambda pw, h: tel.append(h) or echt(pw, h))
    assert users.verify_by_email("niemand@nooch.earth", "x") is False
    assert users.verify_by_email(EMAIL, "fout") is False
    assert len(tel) == 2
    assert tel[0].startswith(b"$2b$12$") and tel[1].startswith(b"$2b$12$")  # dezelfde kosten


def test_in_chromium_landt_een_deeplink_met_anker_na_inloggen_op_zijn_plek(server):
    """De hele keten in een echte browser: `/project?pid=…#feit-1a2b` zonder sessie → 303 naar
    /login (de browser houdt het anker vast) → de pagina zet het in het verborgen veld → inloggen →
    terug op hetzelfde adres MÉT anker."""
    sync_api = pytest.importorskip("playwright.sync_api")
    _dd, _p, port, _s = server
    basis = f"http://127.0.0.1:{port}"
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:                                # noqa: BLE001
            pytest.skip(f"geen Chromium: {e}")
        pg = browser.new_page()
        pg.goto(f"{basis}/project?pid=abc123#feit-1a2b")
        assert "/login?next=" in pg.url and pg.url.endswith("#feit-1a2b")
        assert pg.input_value("#anker") == "#feit-1a2b"
        pg.fill("#u", EMAIL)
        pg.fill("#p", PW)
        with pg.expect_navigation():
            pg.click("button[type=submit]")
        assert pg.url == f"{basis}/project?pid=abc123#feit-1a2b"
        browser.close()
