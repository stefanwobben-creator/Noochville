"""Call bar — UIT DE APP-SHELL (11 aug 2026), de wiring eronder blijft intact.

De strook werkte niet betrouwbaar, en een balk die het soms doet is erger dan geen balk: je gaat
'm gebruiken op het moment dat het ertoe doet. Hij is daarom uit de shell-injectie gehaald; de
/callbar-route, `_callbar_frame` en de LiveKit-helpers blijven bestaan (dood maar intact), zodat
terugzetten één regel is en er geen halve opruiming in de weg zit.

Wat deze tests bewaken: het server-side mute-pad faalt nog steeds fail-soft, de dispatch-tak
lk_mute is bereikbaar, de standalone /callbar-pagina is well-formed — én de bar komt op GEEN
enkele geserveerde pagina meer terug."""
from __future__ import annotations

import http.client
import threading
from http.server import HTTPServer

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
    assert "failed" in msg2                                        # geen creds → fail-soft-melding
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
    assert "another tab" in html and "disabled" not in html          # subtiele hint, GEEN uitgegrijsde knop
    assert "cb-audio" in html                                          # audio-render-container
    assert "overflow-x:auto" in html and "flex:none" in html           # tile-rij scrollt, controls gepind (geen afkap)
    assert "style=" not in html                                        # geen inline styles (ratchet)


def test_geen_shell_css_meer_voor_de_strook():
    """De parent-shell-regels (.cb-frame, body.has-callbar) zijn weg. Zolang die bleven staan, hield
    een pagina ruimte gereserveerd voor iets dat er niet meer is — en moest een volgende restyle
    uitzoeken waar ze bij hoorden."""
    from nooch_village.cockpit2_util import _EXTRA_CSS
    from nooch_village.web_base import _CSS
    assert ".cb-frame{" not in _EXTRA_CSS
    assert "body.has-callbar" not in _EXTRA_CSS
    assert "cb-frame" not in _CSS                    # ook niet in de inline head-CSS


def test_callbar_frame_bestaat_nog_maar_wordt_nergens_geinjecteerd():
    """De glue blijft bestaan (terugzetten = één regel), maar mag niet meer in de shell hangen."""
    f = _callbar_frame()
    assert "<iframe" in f and "src='/callbar'" in f
    assert "allow='camera; microphone'" in f and "hidden" in f          # permissions + start verborgen
    assert "e.origin!==location.origin" in f and "e.source!==f.contentWindow" in f  # strikte origin+source-check
    assert "has-callbar" in f and "c2-toast" in f                       # glue: reveal + toast
    assert "style=" not in f                                            # geen inline styles


# ── GUARD: de bar staat op geen enkele geserveerde pagina meer ───────────────

def _server(dd):
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "TESTTOKEN"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read().decode("utf-8")
    conn.close()
    return r.status, body


def test_guard_geen_callbar_op_de_geserveerde_paginas(tmp_path):
    """DE guard, op de ECHTE respons: de injectie zit in `_send`, dus een view-render alleen zou
    niets bewijzen — die bevatte de bar sowieso nooit."""
    dd = _dd(tmp_path)
    httpd, port = _server(dd)
    try:
        for pad in ("/metrics2", "/admin", "/signals", "/inwoners", "/founder"):
            status, body = _get(port, pad)
            assert status == 200, (pad, status)
            assert "cb-frame" not in body, pad
            assert "id='cb-frame'" not in body and 'id="cb-frame"' not in body, pad
            assert "src='/callbar'" not in body, pad
            assert "has-callbar" not in body, pad
    finally:
        httpd.shutdown()


def test_guard_de_rest_van_de_chrome_blijft_staan(tmp_path):
    """De bar eruit mag de rest van de shell niet meenemen: footer, inbox-drawer en de topbalk
    horen er nog te staan, en de pagina moet gewoon afsluiten."""
    dd = _dd(tmp_path)
    httpd, port = _server(dd)
    try:
        status, body = _get(port, "/metrics2")
        assert status == 200
        assert "c2-foot" in body                        # footer (Metrics/People-links)
        assert "ibx-" in body                            # inbox-drawer staat er nog
        assert "</body>" in body and body.rstrip().endswith("</html>")
    finally:
        httpd.shutdown()


def test_guard_geen_dangling_js_naar_het_verdwenen_element(tmp_path):
    """Zonder de iframe mag er ook geen script meer naar 'cb-frame' zoeken — dat zou een stille
    console-fout geven op elke pagina."""
    dd = _dd(tmp_path)
    httpd, port = _server(dd)
    try:
        _, body = _get(port, "/")
        assert "getElementById('cb-frame')" not in body
        assert "cb-ready" not in body and "cb-toast" not in body
    finally:
        httpd.shutdown()
