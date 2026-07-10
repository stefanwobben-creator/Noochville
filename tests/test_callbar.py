"""Dorp-brede call bar: het server-side mute-pad faalt fail-soft (geen creds → geen crash), de
dispatch-tak lk_mute is bereikbaar en netjes, en de bar-chrome is well-formed (verborgen tot LiveKit
geconfigureerd is, csrf ingebed, geen inline styles)."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.callbar import _callbar_chrome


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_mute_fail_soft_zonder_creds(monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    assert cockpit2.livekit_mute_participant("iemand", True) is False   # geen creds → False, geen exception


def test_mute_lege_identity_is_false(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://demo.livekit.cloud")       # url wel, maar identity leeg
    assert cockpit2.livekit_mute_participant("", True) is False         # geen call, meteen False


def test_lk_mute_dispatch_tak(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    dd = _dd(tmp_path)
    # lege identity → no-op (lege melding), geen crash
    nxt, msg = cockpit2.dispatch(dd, "lk_mute", {"identity": [""], "next": ["/"]}, username="guest")
    assert msg == ""
    # echte identity maar geen creds → fail-soft-melding (niet gelukt), geen exception
    _, msg2 = cockpit2.dispatch(dd, "lk_mute", {"identity": ["x"], "muted": ["1"], "next": ["/"]}, username="guest")
    assert "niet gelukt" in msg2
    assert "lk_mute" in cockpit2.ACTIONS


def test_callbar_chrome_wellformed():
    html = _callbar_chrome("csrf123")
    assert "id='c2-callbar'" in html and "hidden" in html               # start verborgen
    assert "/livekit-token" in html and "csrf123" in html               # token-fetch + csrf ingebed
    assert "cb-audio" in html                                           # audio-render-container aanwezig
    assert "style=" not in html                                         # geen inline styles (ratchet)
