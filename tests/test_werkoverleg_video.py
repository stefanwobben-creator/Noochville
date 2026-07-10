"""LiveKit-primitieven die BLIJVEN nadat video uit het werkoverleg is gehaald (de dorp-brede call
bar hergebruikt ze): `verwijder_livekit_room` faalt fail-soft zonder creds, en de static-whitelist
serveert alleen de gevendorde client-bundle (geen path-traversal).

Wat hier bewust NIET meer staat: de wo_close-room-opheffen en de AI-presence-tiles zijn met de
video-kolom uit het werkoverleg verdwenen (zie feature/livekit-uit-werkoverleg)."""
from __future__ import annotations

from nooch_village import cockpit2


def test_verwijder_livekit_room_fail_soft_zonder_creds(monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    assert cockpit2.verwijder_livekit_room("wo-x-1") is False       # geen creds → False, geen exception


def test_static_whitelist_weigert_onbekend_pad():
    assert cockpit2._STATIC_TYPES.get("livekit-client.umd.min.js")  # bekend bestand mag
    assert cockpit2._STATIC_TYPES.get("../config/settings.ini") is None   # traversal/onbekend geweigerd
