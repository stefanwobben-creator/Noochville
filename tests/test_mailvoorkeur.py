"""Mailvoorkeur (17 oktober 2026, besluit Stefan): losse sleutel `mail: {week, verslag}` op de
people-rij (ontbreekt = AAN), `/account` met twee schakelaars (stand als tekst), alleen de eigen
voorkeur, CSRF verplicht; `mail.verstuur(..., voorkeur=…)` leest dezelfde helper; afmeldlink via `/l`."""
from __future__ import annotations

import http.client
import os
import re
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, mail
from nooch_village.people import MAIL_SOORTEN, PeopleStore

GEHEIM = "geheim-csrf"


# ── de opslag ─────────────────────────────────────────────────────────────────────────────────

def test_ontbrekend_is_aan_onbekend_is_uit(tmp_path):
    ps = PeopleStore(str(tmp_path / "people.json"))
    p = ps.add("Ada", "ada@x.nl")
    assert MAIL_SOORTEN == ("week", "verslag")
    assert ps.mail_voorkeur(p.id, "week") is True and ps.mail_voorkeur(p.id, "verslag") is True
    assert ps.mail_voorkeur(p.id, "spam") is False                           # onbekende soort: nooit
    assert ps.zet_mail_voorkeur(p.id, "week", False) is True
    ps2 = PeopleStore(str(tmp_path / "people.json"))
    assert ps2.mail_voorkeur(p.id, "week") is False and ps2.mail_voorkeur(p.id, "verslag") is True
    assert ps2._items[p.id]["mail"] == {"week": False}
    assert ps2.zet_mail_voorkeur(p.id, "spam", True) is False
    assert ps2.zet_mail_voorkeur("bestaat-niet", "week", True) is False
    assert ps2.get(p.id).name == "Ada"                                       # Person blijft schoon


# ── de verzendcode leest dezelfde helper ──────────────────────────────────────────────────────

def test_verstuur_met_voorkeur(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("MAIL_"):
            monkeypatch.delenv(k)
    mail._VENSTER.clear()
    dd = str(tmp_path)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.add("Ada", "ada@x.nl")
    st = lambda **kw: mail.verstuur("ada@x.nl", "Week 42", "x", data_dir=dd, **kw)["status"]   # noqa: E731
    assert st(voorkeur="week") == "dry-run"                                  # ontbrekend = aan
    ps.zet_mail_voorkeur(p.id, "week", False)
    uit = mail.verstuur("ada@x.nl", "Week 42", "x", data_dir=dd, voorkeur="week")
    assert uit == {"status": "refused", "reden": "turned off by the recipient (week)"}
    assert st(voorkeur="verslag") == "dry-run"                               # de andere soort staat nog aan
    assert st(voorkeur="spam") == "refused"
    assert mail.verstuur("onbekend@x.nl", "T", "x", data_dir=dd, voorkeur="week")["reden"] == "no person with this address"
    assert st() == "dry-run"                                                 # zonder soort (testmail): geen poort
    mail._VENSTER.clear()


def test_afmeldpad_via_l_naar_de_accountpagina():
    pad = mail.afmeld_pad("week")
    assert pad == "/l?p=%2Faccount%3Fuit%3Dweek" and mail.afmeld_pad("spam") == ""
    p = urllib.parse.parse_qs(urllib.parse.urlparse(pad).query)["p"][0]
    assert _auth.veilig_pad(p) == "/account?uit=week"                         # /l laat hem door


# ── de pagina en de actie, via de echte handler ───────────────────────────────────────────────

@pytest.fixture
def server(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    ada, bo = ps.add("Ada Lovelace", "ada@x.nl"), ps.add("Bo Bakker", "bo@x.nl")
    sessions = _auth.SessionStore()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, GEHEIM, sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, httpd.server_address[1], sessions, ada, bo
    httpd.shutdown()


def _req(port, methode, pad, tok=None, velden=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    kop = {"Cookie": f"nv_session={tok}"} if tok else {}
    body = None
    if velden is not None:
        body = urllib.parse.urlencode(velden)
        kop["Content-Type"] = "application/x-www-form-urlencoded"
    c.request(methode, pad, body=body, headers=kop)
    r = c.getresponse()
    return r, r.read().decode()


def _ps(dd):
    return PeopleStore(os.path.join(dd, "people.json"))


def test_de_pagina_toont_de_stand_als_tekst_en_wijzigt_niets(server):
    dd, port, sessions, ada, _bo = server
    tok = sessions.create("ada@x.nl")
    voor = open(os.path.join(dd, "people.json"), "rb").read()
    r, html = _req(port, "GET", "/account?uit=week", tok)
    assert r.status == 200
    assert open(os.path.join(dd, "people.json"), "rb").read() == voor          # GET wijzigt niets
    assert html.count("<span class='chip'>On</span>") == 2 and "Turn off" in html
    assert html.index("id='mail-week'") < html.index("id='mail-verslag'")      # afmeld-soort eerst
    assert "unsubscribe link" in html
    assert f"name='csrf' value='{_auth.csrf_voor(GEHEIM, tok)}'" in html
    assert " style=" not in html.split("<main", 1)[-1].split("id='mail-week'", 1)[1].split("</main>", 1)[0]
    _ps(dd).zet_mail_voorkeur(ada.id, "verslag", False)
    _r, html = _req(port, "GET", "/account", tok)
    assert "<span class='chip muted'>Off</span>" in html and "Turn on" in html


def test_alleen_de_eigen_voorkeur_en_csrf_verplicht(server):
    dd, port, sessions, ada, bo = server
    tok = sessions.create("ada@x.nl")
    goed = _auth.csrf_voor(GEHEIM, tok)
    basis = {"action": "mail_voorkeur_zet", "soort": "week", "aan": "0", "next": "/account"}
    r, _ = _req(port, "POST", "/action", tok, {**basis, "csrf": "fout"})
    assert r.status == 403 and _ps(dd).mail_voorkeur(ada.id, "week") is True
    r, _ = _req(port, "POST", "/action", None, {**basis, "csrf": goed})       # zonder sessie
    assert r.status == 403
    # een pid of persoon in het formulier doet niets: de persoon komt uit de sessie
    r, _ = _req(port, "POST", "/action", tok, {**basis, "csrf": goed, "pid": bo.id, "person": bo.id})
    assert r.status == 303 and r.getheader("Location").startswith("/account?msg=")
    assert _ps(dd).mail_voorkeur(ada.id, "week") is False and _ps(dd).mail_voorkeur(bo.id, "week") is True
    r, _ = _req(port, "POST", "/action", tok, {**basis, "csrf": goed, "soort": "spam"})
    assert "unknown" in urllib.parse.unquote(r.getheader("Location"))
    r, _ = _req(port, "POST", "/action", tok, {**basis, "csrf": goed, "aan": "1",
                                                "next": "/account#mail-week"})
    assert r.getheader("Location").endswith("#mail-week") and _ps(dd).mail_voorkeur(ada.id, "week") is True


def test_zonder_persoon_een_melding_geen_formulier(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    from nooch_village.views.account import render_account
    html = render_account(cockpit2._Stores(dd), ik="", csrf_token="t")
    assert "Sign in as a person" in html and "mail_voorkeur_zet" not in html
