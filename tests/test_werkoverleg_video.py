"""Brok 3 (server-side): AI-presence-tiles komen uit de persona-fillers en staan NIET in de
menselijke check-in-lijst; wo_close heft de LiveKit-room op met de server-afgeleide naam en het
afronden is fail-soft; de static-whitelist weigert onbekende paden (geen traversal)."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.overview import _members_of_circle
from nooch_village.views.werkoverleg import _wo_ai_presence

C = "mother_earth__nooch"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def test_ai_presence_tile_niet_in_checkin(tmp_path):
    dd, st = _st(tmp_path)
    codie = st.personas.add("Codie")
    st.assign.assign(C + "__marketing_lead", "persona", codie.id)
    crec = st.records.get(C)
    ai = _wo_ai_presence(cockpit2._Stores(dd), crec)
    assert "Codie" in ai and "wo-tile ai" in ai              # AI staat rechts als presence-tile
    members = _members_of_circle(cockpit2._Stores(dd), C)
    assert all(m.name != "Codie" for m in members)           # ... en NIET in de menselijke check-in-lijst


def test_wo_close_hef_room_op_met_juiste_naam(tmp_path, monkeypatch):
    dd, st = _st(tmp_path)
    m = st.werk.open(C)
    called = {}
    monkeypatch.setattr(cockpit2, "verwijder_livekit_room",
                        lambda room: called.__setitem__("room", room) or True)
    _, msg = cockpit2.dispatch(dd, "wo_close", {"circle": [C], "next": ["/"]}, username="guest")
    assert "gesloten" in msg
    assert called["room"] == f"wo-{C}-{int(m['started_at'])}"       # server-afgeleide room-naam
    assert cockpit2._Stores(dd).werk.get(C)["status"] == "closed"   # meeting is afgerond


def test_verwijder_livekit_room_fail_soft_zonder_creds(monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    assert cockpit2.verwijder_livekit_room("wo-x-1") is False       # geen creds → False, geen exception


def test_static_whitelist_weigert_onbekend_pad():
    assert cockpit2._STATIC_TYPES.get("livekit-client.umd.min.js")  # bekend bestand mag
    assert cockpit2._STATIC_TYPES.get("../config/settings.ini") is None   # traversal/onbekend geweigerd
