"""LiveKit token-endpoint (dorp-brede call bar): de server bepaalt room + identity (NOOIT uit de
request), room is de vaste dorp-room `village`, en de authz is iedereen-ingelogd. Dummy-creds via
monkeypatch; token gedecodeerd met het dummy-secret om de claims te toetsen."""
from __future__ import annotations

import inspect
import json
import jwt
from nooch_village import cockpit2

_SECRET = "devsecret_at_least_32_chars_long_xx"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _creds(monkeypatch, url="wss://demo.livekit.cloud"):
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", _SECRET)
    if url is None:
        monkeypatch.delenv("LIVEKIT_URL", raising=False)
    else:
        monkeypatch.setenv("LIVEKIT_URL", url)


def _known(st, email="lotte@nooch.earth"):
    p = st.people.by_name("Lotte Mulder")
    st.people.update(p.id, email=email)
    return p


def test_herkende_gebruiker_krijgt_village_token(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    p = _known(st)
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "lotte@nooch.earth")
    assert status == 200 and payload["server_url"] == "wss://demo.livekit.cloud"
    assert payload["identity"] == p.id                        # identity teruggegeven aan de client
    claims = jwt.decode(payload["token"], _SECRET, algorithms=["HS256"])
    assert claims["sub"] == p.id                              # identity = ingelogde gebruiker
    assert claims["video"]["room"] == "village"               # één dorp-brede room, server-afgeleid


def test_onbekende_gebruiker_geen_token(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)                                     # geen persoon met dit e-mailadres
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "niemand@nergens.nl")
    assert status == 403 and "token" not in payload


def test_guest_krijgt_token_bij_auth_uit(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, _ = _st(tmp_path)
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "guest")
    assert status == 200 and payload["identity"] == "guest"
    claims = jwt.decode(payload["token"], _SECRET, algorithms=["HS256"])
    assert claims["sub"] == "guest" and claims["video"]["room"] == "village"


def test_room_en_identity_niet_uit_request(tmp_path, monkeypatch):
    # issue_livekit_token accepteert geen room/identity/circle-parameter → een request kan ze
    # onmogelijk zetten; het token draagt de server-afgeleide dorp-room.
    params = inspect.signature(cockpit2.issue_livekit_token).parameters
    assert "room" not in params and "identity" not in params and "circle" not in params
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    _known(st)
    _, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "lotte@nooch.earth")
    claims = jwt.decode(payload["token"], _SECRET, algorithms=["HS256"])
    assert claims["video"]["room"] == "village"


def test_tab_suffix_maakt_identity_uniek_per_tab(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    p = _known(st)
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "lotte@nooch.earth", tab="ab12")
    assert status == 200 and payload["identity"] == f"{p.id}#tab-ab12"
    claims = jwt.decode(payload["token"], _SECRET, algorithms=["HS256"])
    assert claims["sub"] == f"{p.id}#tab-ab12"                 # per-tab uniek, base intact
    # zonder tab → kale base (geen suffix)
    _, plain = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "lotte@nooch.earth")
    assert plain["identity"] == p.id


def test_tab_suffix_kan_base_niet_overschrijven(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    p = _known(st)
    # een kwaadaardige tab-waarde wordt gesanitiseerd tot [a-z0-9] en ALLEEN achter de base geplakt;
    # de base blijft de server-bepaalde persoon-id → geen impersonatie.
    _, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "lotte@nooch.earth",
                                              tab="#tab-admin/../x")
    assert payload["identity"].startswith(f"{p.id}#tab-") and payload["identity"] != "admin"
    assert cockpit2._tab_suffix("#tab-admin/../x") == "tabadminx"   # gesanitiseerd, geen separators


def test_ontbrekende_creds_fail_closed_zonder_secret_lek(tmp_path, monkeypatch):
    _creds(monkeypatch, url=None)                             # KEY/SECRET wel, LIVEKIT_URL niet
    dd, st = _st(tmp_path)
    _known(st)
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), "lotte@nooch.earth")
    assert status == 503 and "token" not in payload
    assert _SECRET not in json.dumps(payload)                 # secret lekt nergens in de respons
