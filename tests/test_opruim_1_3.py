"""Opruimlijst punt 1 tot 3 (12 oktober 2026).

1. De uitloglink in het gebruikersblok van de zijbalk.
2. Elk `.ovl-x` wordt gezocht BINNEN de eigen overlay. Getoetst met een lokaas: een tweede `.ovl-x`
   vóór de overlay in het document — precies wat de oude `document.querySelector('.ovl-x')` pakte.
   Voor alle drie de overlays: de kaart-modal van het bord, de wizard en het werkoverleg.
3. De weesprojecten-melding noemt de titel (`scope`), niet het id.
"""
from __future__ import annotations

import http.client
import threading
import types
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

LOKAAS = "<button type='button' class='ovl-x' id='lokaas'>x</button>"
ROL = "mother_earth__nooch__financial_controller"


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.projects.create(ROL, "Een kaart om te openen", "human")
    return dd


def _server(dd, sessies=None):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ── 1. uitloggen ────────────────────────────────────────────────────────────

def test_de_uitloglink_staat_bij_de_gebruiker_en_logt_uit(dorp):
    from nooch_village.cockpit2_util import _nav
    zij = _nav().split("<aside class='c2-side'>")[1].split("</aside>")[0]
    assert "href='/logout'" in zij and zij.index("c2-av") < zij.index("href='/logout'")
    sessies = _auth.SessionStore()
    st = cockpit2._Stores(dorp)
    st.people.add("Iemand", "iemand@nooch.earth")
    token = sessies.create("iemand@nooch.earth")
    httpd = _server(dorp, sessies)
    try:
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        c.request("GET", "/logout", headers={"Cookie": f"nv_session={token}"})
        r = c.getresponse(); r.read()
        assert r.status in (302, 303) and r.getheader("Location").startswith("/login")
        assert sessies.get_username(token) is None
    finally:
        httpd.shutdown()


# ── 2. elk kruisje binnen zijn eigen overlay ───────────────────────────────

def test_niemand_pakt_nog_het_eerste_kruisje_van_het_document():
    import pathlib
    root = pathlib.Path(cockpit2.__file__).parent
    for f in list((root / "views").glob("*.py")) + [root / "static" / "nooch.js"]:
        code = "\n".join(r for r in f.read_text(encoding="utf-8").splitlines() if not r.strip().startswith("#"))
        assert "document.querySelector('.ovl-x')" not in code, f.name


def _browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    return sync_api


def _met_lokaas(route):
    """Zet een tweede `.ovl-x` direct na <body>: vóór elke overlay in het document."""
    r = route.fetch()
    body = r.text().replace("<body>", "<body>" + LOKAAS, 1)
    route.fulfill(response=r, body=body)


def test_de_kaart_modal_en_de_wizard_sluiten_met_hun_eigen_kruisje(dorp):
    sync_api = _browser()
    httpd = _server(dorp)                                       # guest: de modal-JS staat aan
    basis = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"geen Chromium: {e}")
            pg = browser.new_page(viewport={"width": 1300, "height": 900})
            pg.route(basis + "/projects", _met_lokaas)
            pg.goto(basis + "/projects")
            assert pg.locator("#lokaas").count() == 1
            ovl = pg.locator("#ovl")
            # de kaart-modal
            pg.locator(".pcol .pcard").first.click()
            ovl.wait_for(state="visible")
            pg.locator("#ovl .ovl-x").click()
            ovl.wait_for(state="hidden")
            # de wizard (via "+ add project", in dezelfde overlay): zijn eigen ✕
            pg.locator("a.addlink.js-modal").first.click()
            ovl.wait_for(state="visible")
            pg.locator("#ovl .wz-x").click()
            ovl.wait_for(state="hidden")
            browser.close()
    finally:
        httpd.shutdown()


def test_het_werkoverleg_verlaten_klikt_het_eigen_kruisje(dorp):
    """De "leave meeting"-link zocht al binnen zijn overlay; deze toets houdt dat zo."""
    sync_api = _browser()
    from nooch_village.views.werkoverleg import render_werkoverleg
    st = cockpit2._Stores(dorp)
    st.werk.open("mother_earth__nooch")
    frag = render_werkoverleg(st, "mother_earth__nooch", "checkin", csrf_token="T", fragment=True)
    assert "wo-leave" in frag
    html = ("<!doctype html><html><body>" + LOKAAS.replace("'lokaas'", "'lokaas' onclick='window.__lokaasGeklikt=1'")
            + "<div class='ovl'><button type='button' class='ovl-x' onclick='window.eigen=1'>✕</button>"
            + frag + "</div></body></html>")
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"geen Chromium: {e}")
        pg = browser.new_page()
        pg.set_content(html)
        pg.locator("a.wo-leave").click()
        # (niet `window.lokaas`: dat is in een browser het element met id 'lokaas')
        assert pg.evaluate("[window.eigen||0, window.__lokaasGeklikt||0]") == [1, 0]
        browser.close()


# ── 3. de weesprojecten-melding ─────────────────────────────────────────────

def test_de_weesprojecten_melding_noemt_de_titel_niet_het_id(dorp):
    from nooch_village.village import Village
    st = cockpit2._Stores(dorp)
    pid = st.projects.create(ROL, "Herkenbare projecttitel", "human")
    meldingen = []
    nep = types.SimpleNamespace(
        context=types.SimpleNamespace(projects=st.projects),
        records=types.SimpleNamespace(get=lambda rid: types.SimpleNamespace(archived=True, slaapt=False)
                                      if rid == ROL else None),
        human_inbox=types.SimpleNamespace(add_means_gap=lambda k, tekst, **kw: meldingen.append(tekst)))
    Village._meld_weesprojecten(nep)
    assert meldingen and "Herkenbare projecttitel" in meldingen[0] and pid not in meldingen[0]
