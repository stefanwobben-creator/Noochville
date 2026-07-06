"""Verplichte wachtwoordwijziging bij eerste login / na admin-reset.

Poort (echte handler + HTTPServer, redirects niet gevolgd zodat we de 303 zien): een ingelogde met de
`must_change_password`-flag mag alleen naar /wachtwoord tot hij een eigen wachtwoord kiest. Plus de
people/auth-eenheden (flag zetten/wissen, migratie, beleid, de no-op sessie-haak).
"""
from __future__ import annotations
import http.client
import json
import os
import threading
import time
from http.server import HTTPServer

from nooch_village import auth as _auth
from nooch_village import cockpit2
from nooch_village.people import PeopleStore

EMAIL = "stefan@nooch.earth"
TEMP = "TEMPpw1234"


def _bootstrap(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _seed_person(dd, must_change=True, pw=TEMP):
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.add("Stefan", EMAIL)
    ps.set_password(p.id, _auth.hash_password(pw), must_change=must_change)
    return p


def _server(dd, sessions):
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "TESTTOKEN", sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _req(port, method, path, cookie=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {}
    if cookie:
        headers["Cookie"] = f"nv_session={cookie}"
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(method, path, body=body, headers=headers)
    r = conn.getresponse()
    text = r.read().decode("utf-8", "replace")
    conn.close()
    return r, text


def _flag(dd) -> bool:
    return PeopleStore(os.path.join(dd, "people.json")).must_change(EMAIL)


# ── de poort (HTTP) ─────────────────────────────────────────────────────────────────────────────
def test_geflagde_gebruiker_wordt_overal_naar_wachtwoord_gestuurd(tmp_path):
    dd = _bootstrap(tmp_path); _seed_person(dd, must_change=True)
    sessions = _auth.SessionStore(); tok = sessions.create(EMAIL)
    httpd, port = _server(dd, sessions)
    try:
        r, _ = _req(port, "GET", "/", cookie=tok)
        assert r.status == 303 and (r.getheader("Location") or "") == "/wachtwoord"
        r2, _ = _req(port, "GET", f"/node?id=mother_earth", cookie=tok)   # ook een gewone route
        assert r2.status == 303 and (r2.getheader("Location") or "") == "/wachtwoord"
        # /wachtwoord zelf mag wél (anders redirect-lus)
        r3, body = _req(port, "GET", "/wachtwoord", cookie=tok)
        assert r3.status == 200 and "Wachtwoord wijzigen" in body and "tijdelijk wachtwoord" in body
    finally:
        httpd.shutdown()


def test_niet_geflagde_gebruiker_gaat_gewoon_door(tmp_path):
    dd = _bootstrap(tmp_path); _seed_person(dd, must_change=False)
    sessions = _auth.SessionStore(); tok = sessions.create(EMAIL)
    httpd, port = _server(dd, sessions)
    try:
        r, _ = _req(port, "GET", "/", cookie=tok)
        assert not (r.status == 303 and (r.getheader("Location") or "") == "/wachtwoord")
    finally:
        httpd.shutdown()


def test_geldige_wijziging_wist_flag_en_laat_door(tmp_path):
    dd = _bootstrap(tmp_path); _seed_person(dd, must_change=True)
    sessions = _auth.SessionStore(); tok = sessions.create(EMAIL)
    httpd, port = _server(dd, sessions)
    try:
        body = f"current={TEMP}&new=MijnNieuwe99&confirm=MijnNieuwe99&next=/"
        r, _ = _req(port, "POST", "/wachtwoord", cookie=tok, body=body)
        assert r.status == 303 and (r.getheader("Location") or "") == "/"
        assert _flag(dd) is False                                    # flag gewist
        r2, _ = _req(port, "GET", "/", cookie=tok)                   # sessie behouden, niet meer gegate
        assert not (r2.status == 303 and (r2.getheader("Location") or "") == "/wachtwoord")
    finally:
        httpd.shutdown()


def test_fout_wachtwoord_en_beleid_blokkeren_de_wijziging(tmp_path):
    dd = _bootstrap(tmp_path); _seed_person(dd, must_change=True)
    sessions = _auth.SessionStore(); tok = sessions.create(EMAIL)
    httpd, port = _server(dd, sessions)
    try:
        cases = [
            (f"current=FOUT&new=MijnNieuwe99&confirm=MijnNieuwe99", "Huidig wachtwoord onjuist"),
            (f"current={TEMP}&new=MijnNieuwe99&confirm=Anders99xx", "komen niet overeen"),
            (f"current={TEMP}&new=kort&confirm=kort", "minimaal 10"),
            (f"current={TEMP}&new={TEMP}&confirm={TEMP}", "ander wachtwoord dan het huidige"),
        ]
        for body, needle in cases:
            r, txt = _req(port, "POST", "/wachtwoord", cookie=tok, body=body)
            assert r.status == 200 and needle in txt
            assert _flag(dd) is True                                 # nog steeds geflagd, niets gewijzigd
    finally:
        httpd.shutdown()


# ── people-eenheden ─────────────────────────────────────────────────────────────────────────────
def test_set_password_markeert_moet_wijzigen(tmp_path):
    ps = PeopleStore(str(tmp_path / "people.json"))
    p = ps.add("A", "a@x.nl")
    ps.set_password(p.id, "h")                                       # default must_change=True
    assert ps.get(p.id).must_change_password is True and ps.get(p.id).invited_at > 0
    ps.set_own_password(p.id, "h2")                                  # self-service wist de flag
    assert ps.get(p.id).must_change_password is False and ps.get(p.id).password_hash == "h2"


def test_ontbrekend_veld_is_geen_verplichting(tmp_path):
    # legacy-record zonder het veld → default False (geen retroactieve forcering)
    path = str(tmp_path / "people.json")
    json.dump({"p": {"id": "p", "name": "B", "email": "b@x.nl", "password_hash": "h"}},
              open(path, "w"))
    assert PeopleStore(path).must_change("b@x.nl") is False


def test_backfill_flagt_uitstaande_temps_en_spaart_gewijzigde(tmp_path):
    path = str(tmp_path / "people.json")
    now = time.time()
    json.dump({
        "temp": {"id": "temp", "name": "T", "email": "t@x.nl", "password_hash": "h",
                 "invited_at": now, "last_login": 0.0},                    # uitstaand temp → flag
        "used": {"id": "used", "name": "U", "email": "u@x.nl", "password_hash": "h",
                 "invited_at": now - 100, "last_login": now},              # eigen wachtwoord → spaar
        "geen": {"id": "geen", "name": "G", "email": "g@x.nl", "password_hash": "",
                 "invited_at": 0.0, "last_login": 0.0},                    # geen wachtwoord → skip
    }, open(path, "w"))
    ps = PeopleStore(path)
    assert ps.backfill_must_change() == 1
    assert ps.must_change("t@x.nl") is True and ps.must_change("u@x.nl") is False
    assert PeopleStore(path).backfill_must_change() == 0                   # idempotent


# ── auth-eenheden ───────────────────────────────────────────────────────────────────────────────
def test_password_change_page_forced_en_error():
    forced = _auth.password_change_page(forced=True)
    assert "tijdelijk wachtwoord" in forced and 'action="/wachtwoord"' in forced
    assert "onjuist" in _auth.password_change_page(error="onjuist")


def test_invalidate_user_is_noop_en_breekt_niets(tmp_path):
    s = _auth.SessionStore(); tok = s.create(EMAIL)
    assert s.invalidate_user(EMAIL, keep_token=tok) == 0                   # no-op nu
    assert s.get_username(tok) == EMAIL                                    # eigen sessie intact
