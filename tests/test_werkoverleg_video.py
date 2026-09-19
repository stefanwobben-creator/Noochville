"""LiveKit-primitieven die BLIJVEN nadat video uit het werkoverleg is gehaald (de dorp-brede call
bar hergebruikt ze): `verwijder_livekit_room` faalt fail-soft zonder creds, en de static-whitelist
serveert alleen de gevendorde client-bundle (geen path-traversal).

Wat hier bewust NIET meer staat: de wo_close-room-opheffen en de AI-presence-tiles zijn met de
video-kolom uit het werkoverleg verdwenen (zie feature/livekit-uit-werkoverleg)."""
from __future__ import annotations

from nooch_village import cockpit2




def test_static_whitelist_weigert_onbekend_pad():
    # Stond op livekit-client.umd.min.js; die is met de call bar weg (fase 6). De eis is
    # dat een BEKEND bestand door de whitelist komt en een onbekend niet.
    assert cockpit2._STATIC_TYPES.get("nooch.css")             # bekend bestand mag
    assert cockpit2._STATIC_TYPES.get("../config/settings.ini") is None   # traversal/onbekend geweigerd
