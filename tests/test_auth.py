"""Auth — e-mail-gebaseerde login bovenop people.json, sessies, cookies, tijdelijke wachtwoorden."""
from __future__ import annotations

import json
import time

import pytest

from nooch_village import auth
from nooch_village.people import PeopleStore


def _people_file(tmp_path, password="geheim123"):
    """Schrijf een people.json met één ingelogde persoon en één zonder wachtwoord."""
    data = {
        "p1": {
            "id": "p1", "name": "Stefan Wobben", "email": "Stefan@Nooch.Earth",
            "password_hash": auth.hash_password(password),
            "invited_at": time.time(), "last_login": 0.0,
        },
        "p2": {  # bestaat wel, maar heeft (nog) geen wachtwoord → kan niet inloggen
            "id": "p2", "name": "Dan Morgan", "email": "",
            "password_hash": "", "invited_at": 0.0, "last_login": 0.0,
        },
    }
    path = tmp_path / "people.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


# ── UserStore ─────────────────────────────────────────────────────────────

def test_verify_by_email_correct_wachtwoord(tmp_path):
    store = auth.UserStore(_people_file(tmp_path, "geheim123"))
    assert store.verify_by_email("stefan@nooch.earth", "geheim123") is True


def test_verify_by_email_fout_wachtwoord(tmp_path):
    store = auth.UserStore(_people_file(tmp_path, "geheim123"))
    assert store.verify_by_email("stefan@nooch.earth", "fout") is False


def test_verify_email_is_hoofdletterongevoelig(tmp_path):
    store = auth.UserStore(_people_file(tmp_path, "geheim123"))
    # bestand heeft 'Stefan@Nooch.Earth'; login met willekeurige casing moet werken
    assert store.verify_by_email("STEFAN@NOOCH.EARTH", "geheim123") is True


def test_onbekende_email(tmp_path):
    store = auth.UserStore(_people_file(tmp_path))
    assert store.verify_by_email("niemand@nooch.earth", "x") is False


def test_persoon_zonder_wachtwoord_kan_niet_inloggen(tmp_path):
    store = auth.UserStore(_people_file(tmp_path))
    assert store.get_by_email("") is None        # lege e-mail wordt niet geïndexeerd
    assert store.verify_by_email("", "") is False


def test_get_by_email(tmp_path):
    store = auth.UserStore(_people_file(tmp_path))
    rec = store.get_by_email("stefan@nooch.earth")
    assert rec is not None and rec["name"] == "Stefan Wobben"


def test_empty_op_ontbrekend_bestand(tmp_path):
    store = auth.UserStore(str(tmp_path / "bestaat-niet.json"))
    assert store.empty() is True


def test_store_ziet_nieuw_toegevoegde_persoon_zonder_herstart(tmp_path):
    """UserStore leest people.json vers in: een persoon die ná init een wachtwoord krijgt,
    kan meteen inloggen."""
    path = _people_file(tmp_path)
    store = auth.UserStore(path)
    people = PeopleStore(path)
    nieuw = people.add("Nina Wolter", "nina@nooch.earth")
    people.set_password(nieuw.id, auth.hash_password("welkom01"))
    assert store.verify_by_email("nina@nooch.earth", "welkom01") is True


# ── SessionStore ────────────────────────────────────────────────────────────

def test_session_create_en_get():
    sessions = auth.SessionStore()
    token = sessions.create("stefan@nooch.earth")
    assert sessions.get_username(token) == "stefan@nooch.earth"


def test_session_onbekend_token():
    sessions = auth.SessionStore()
    assert sessions.get_username("neptoken") is None


def test_session_delete():
    sessions = auth.SessionStore()
    token = sessions.create("stefan@nooch.earth")
    sessions.delete(token)
    assert sessions.get_username(token) is None


def test_session_verloopt(monkeypatch):
    sessions = auth.SessionStore(ttl=10)
    token = sessions.create("stefan@nooch.earth")
    # spring voorbij de TTL
    base = time.monotonic()
    monkeypatch.setattr(auth.time, "monotonic", lambda: base + 11)
    assert sessions.get_username(token) is None


# ── Wachtwoord-helpers ───────────────────────────────────────────────────────

def test_hash_password_is_verifieerbaar():
    import bcrypt
    h = auth.hash_password("geheim123")
    assert h != "geheim123"
    assert bcrypt.checkpw(b"geheim123", h.encode())


def test_generate_temp_password_lengte_en_uniek():
    a = auth.generate_temp_password()
    b = auth.generate_temp_password()
    assert len(a) == 10
    assert a != b
    # geen verwarrende tekens
    assert not (set(a) & set("0Ol1"))


# ── Cookies ───────────────────────────────────────────────────────────────

def test_set_cookie_flags():
    c = auth.set_cookie("abc")
    assert "nv_session=abc" in c
    assert "HttpOnly" in c and "Secure" in c and "SameSite=Strict" in c


def test_clear_cookie_max_age_nul():
    c = auth.clear_cookie()
    assert "Max-Age=0" in c


def test_get_session_token_uit_header():
    class H:
        def get(self, k, default=""):
            return "foo=bar; nv_session=tok123; other=x" if k == "Cookie" else default
    assert auth.get_session_token(H()) == "tok123"


def test_get_session_token_afwezig():
    class H:
        def get(self, k, default=""):
            return default
    assert auth.get_session_token(H()) is None


# ── PeopleStore auth-velden ──────────────────────────────────────────────────

def test_people_by_email_en_touch_login(tmp_path):
    path = _people_file(tmp_path)
    people = PeopleStore(path)
    p = people.by_email("stefan@nooch.earth")
    assert p is not None and p.last_login == 0.0
    people.touch_login("stefan@nooch.earth")
    assert PeopleStore(path).by_email("stefan@nooch.earth").last_login > 0


def test_people_set_password(tmp_path):
    path = _people_file(tmp_path)
    people = PeopleStore(path)
    people.set_password("p2", auth.hash_password("welkom01"), invited_at=123.0)
    reloaded = PeopleStore(path).get("p2")
    assert reloaded.password_hash != "" and reloaded.invited_at == 123.0


def test_people_negeert_onbekende_velden(tmp_path):
    """Een oud people.json zonder auth-velden laadt zonder fout (dataclass-defaults)."""
    path = tmp_path / "people.json"
    path.write_text(json.dumps({"x": {"id": "x", "name": "Oud", "email": "", "extra": "negeer"}}))
    p = PeopleStore(str(path)).get("x")
    assert p.name == "Oud" and p.password_hash == ""
