"""LiveKit token-endpoint: de server bepaalt room + identity (NOOIT uit de request-body) en
hergebruikt _member_gate als enige authz-bron. Dummy-creds via monkeypatch; token gedecodeerd
met het dummy-secret om de claims te toetsen."""
from __future__ import annotations

import inspect
import json
import jwt
from nooch_village import cockpit2

CIRCLE = "mother_earth__nooch"
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


def _member(st, email="lotte@nooch.earth"):
    p = st.people.by_name("Lotte Mulder")
    st.people.update(p.id, email=email)
    st.assign.assign(CIRCLE + "__creator_of_shoes", "person", p.id)   # rol in de cirkel
    return p


def test_niet_lid_krijgt_geen_token(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    st.werk.open(CIRCLE)
    st.people.add("Buiten", "buiten@nooch.earth")            # vervult geen rol in de cirkel
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), CIRCLE, "buiten@nooch.earth")
    assert status == 403 and "token" not in payload


def test_lid_krijgt_token_met_server_room_en_identity(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    m = st.werk.open(CIRCLE)
    p = _member(st)
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), CIRCLE, "lotte@nooch.earth")
    assert status == 200 and payload["server_url"] == "wss://demo.livekit.cloud"
    claims = jwt.decode(payload["token"], _SECRET, algorithms=["HS256"])
    assert claims["sub"] == p.id                             # identity = rol-vervuller uit de sessie
    assert claims["video"]["room"] == f"wo-{CIRCLE}-{int(m['started_at'])}"   # room = server-afgeleid


def test_room_en_identity_niet_uit_body(tmp_path, monkeypatch):
    # De pro-tip: issue_livekit_token accepteert geen room/identity-parameter → een body kan ze
    # onmogelijk zetten. En het token draagt de server-afgeleide waarden.
    params = inspect.signature(cockpit2.issue_livekit_token).parameters
    assert "room" not in params and "identity" not in params
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    st.werk.open(CIRCLE)
    p = _member(st)
    _, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), CIRCLE, "lotte@nooch.earth")
    claims = jwt.decode(payload["token"], _SECRET, algorithms=["HS256"])
    assert claims["video"]["room"].startswith(f"wo-{CIRCLE}-") and claims["sub"] == p.id


def test_geen_lopend_overleg(tmp_path, monkeypatch):
    _creds(monkeypatch)
    dd, st = _st(tmp_path)
    _member(st)                                              # lid, maar geen open overleg
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), CIRCLE, "lotte@nooch.earth")
    assert status == 409 and "token" not in payload


def test_ontbrekende_creds_fail_closed_zonder_secret_lek(tmp_path, monkeypatch):
    _creds(monkeypatch, url=None)                           # KEY/SECRET wel, LIVEKIT_URL niet
    dd, st = _st(tmp_path)
    st.werk.open(CIRCLE)
    _member(st)
    status, payload = cockpit2.issue_livekit_token(cockpit2._Stores(dd), CIRCLE, "lotte@nooch.earth")
    assert status == 503 and "token" not in payload
    assert _SECRET not in json.dumps(payload)               # secret lekt nergens in de respons
