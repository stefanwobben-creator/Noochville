"""Dorp-brede call bar in een iframe: het server-side mute-pad faalt fail-soft, de dispatch-tak lk_mute
is bereikbaar, de standalone /callbar-pagina is well-formed (transparant, csrf ingebed, tab-suffix +
BroadcastChannel-logica, geen inline styles), en de iframe-glue heeft een strikte origin-check."""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.callbar import render_callbar, _callbar_frame


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_mute_fail_soft_zonder_creds(monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    assert cockpit2.livekit_mute_participant("iemand", True) is False   # geen creds → False, geen exception


def test_mute_lege_identity_is_false(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://demo.livekit.cloud")       # url wel, maar identity leeg
    assert cockpit2.livekit_mute_participant("", True) is False


def test_presence_fail_soft_zonder_creds(monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    assert cockpit2.livekit_presence() == (0, [])                       # geen creds → (0, []), geen exception


def test_lk_mute_dispatch_tak(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    dd = _dd(tmp_path)
    nxt, msg = cockpit2.dispatch(dd, "lk_mute", {"identity": [""], "next": ["/"]}, username="guest")
    assert msg == ""                                                    # lege identity → no-op
    _, msg2 = cockpit2.dispatch(dd, "lk_mute", {"identity": ["x"], "muted": ["1"], "next": ["/"]}, username="guest")
    assert "niet gelukt" in msg2                                        # geen creds → fail-soft-melding
    assert "lk_mute" in cockpit2.ACTIONS


def test_render_callbar_standalone_wellformed():
    html = render_callbar("csrf123")
    assert html.startswith("<!doctype html>") and "<html" in html      # eigen document
    assert "c2-callbar" in html                                        # bar-markup
    assert "background:transparent" in html                            # transparante iframe-body
    assert "/livekit-token?tab=" in html and "csrf123" in html         # token-fetch mét tab + csrf ingebed
    # ── lazy connect (kostenbewust): GEEN auto-connect meer op page-load ──
    assert "/livekit-presence" in html                                 # presence via goedkope poll
    assert "function joinCall" in html and "connect(publish)" in html   # verbinden pas op de Join-gesture
    assert "room.disconnect" in html                                    # verlaten koppelt écht los (minuten stoppen)
    assert "Join gesprek" in html                                       # niet-verbonden default toont Join
    assert "BroadcastChannel" in html and "sessionStorage" in html     # multi-tab-coördinatie + tab-suffix
    assert "15000" in html                                             # claim-verval 15s bij crash
    assert "visibilitychange" in html                                  # throttle-proof: verval-check bij tabwissel/focus
    assert "ander tabblad" in html and "disabled" not in html          # subtiele hint, GEEN uitgegrijsde knop
    assert "cb-audio" in html                                          # audio-render-container
    assert "overflow-x:auto" in html and "flex:none" in html           # tile-rij scrollt, controls gepind (geen afkap)
    assert "style=" not in html                                        # geen inline styles (ratchet)


def test_cb_frame_heeft_expliciete_width():
    """De iframe-strook krijgt een expliciete breedte: zonder dat rekt Firefox 'm wel maar valt Chrome
    terug op ~intrinsieke breedte (replaced element met left+right + width:auto) → bar kapt rechts af."""
    from nooch_village.cockpit2_util import _EXTRA_CSS
    frame_rule = next(r for r in _EXTRA_CSS.split("}") if ".cb-frame{" in r)
    assert "width:calc(100% - 2.6rem)" in frame_rule


def test_callbar_frame_heeft_iframe_en_origincheck():
    f = _callbar_frame()
    assert "<iframe" in f and "src='/callbar'" in f
    assert "allow='camera; microphone'" in f and "hidden" in f          # permissions + start verborgen
    assert "e.origin!==location.origin" in f and "e.source!==f.contentWindow" in f  # strikte origin+source-check
    assert "has-callbar" in f and "c2-toast" in f                       # glue: reveal + toast
    assert "style=" not in f                                            # geen inline styles
