"""B1: het palet "Go to, or create…" (11 oktober 2026, prototype v2).

Rechten met ECHTE inlogsessies: een gebruiker zonder Finance en zonder Admin ziet die regels niet in
de palet-HTML; het palet en de zijbalk vragen dezelfde rechtenfunctie. Het gedrag (`/`, Esc, de
focus-trap, pijltjes) in een echte browser; zonder playwright of Chromium slaat dat deel over.
"""
from __future__ import annotations

import http.client
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

STEFAN, FC, LID = "stefan@nooch.earth", "fc@nooch.earth", "lid@nooch.earth"
FC_ROL = "mother_earth__nooch__financial_controller"


@pytest.fixture
def server(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Stefan Wobben", STEFAN)
    st.assign.assign(FC_ROL, "person", st.people.add("Fien Controller", FC).id)
    st.people.add("Gewoon Lid", LID)
    sessies = _auth.SessionStore()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield dd, sessies, httpd.server_address[1]
    httpd.shutdown()


def _get(poort, pad, sessie):
    c = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
    c.request("GET", pad, headers={"Cookie": f"nv_session={sessie}"})
    r = c.getresponse()
    return r.status, r.read().decode()


@pytest.mark.parametrize("wie, finance, admin", [(LID, False, False), (FC, True, False), (STEFAN, True, True)])
def test_het_palet_toont_finance_en_admin_alleen_voor_wie_het_mag(server, wie, finance, admin):
    dd, sessies, poort = server
    s = sessies.create(wie)
    status, palet = _get(poort, "/palet?q=", s)
    assert status == 200
    assert ("href='/finance'" in palet) is finance and ("Finance" in palet) is finance
    assert ("href='/admin'" in palet) is admin
    # dezelfde rechtenfunctie als de zijbalk: Admin staat in allebei, of in geen van beide
    _s, pagina = _get(poort, "/projects", s)
    assert ("href='/admin'" in pagina.split("<aside class='c2-side'>")[1].split("</aside>")[0]) is admin
    # en wie het niet mag, krijgt op de pagina zelf nog steeds een 404
    assert _get(poort, "/admin", s)[0] == (200 if admin else 404)


def test_het_palet_filtert_op_de_zoekterm_en_zoekt_vanaf_twee_tekens(server):
    dd, sessies, poort = server
    s = sessies.create(LID)
    _st, alles = _get(poort, "/palet?q=", s)
    for label in ("Projects", "Messages", "My actions", "Wiki", "Tools", "Open questions", "Goals",
                  "Bill of materials", "New project", "New action"):
        assert label in alles, label
    assert "Today" not in alles                              # het scherm bestaat nog niet
    _st, proj = _get(poort, "/palet?q=" + urllib.parse.quote("proj"), s)
    assert "Projects" in proj and "New project" in proj and "Messages" not in proj
    _st, niets = _get(poort, "/palet?q=" + urllib.parse.quote("zzqx"), s)
    assert "gs-empty" in niets or "no hits" in niets


def test_de_markup_van_de_dialoog():
    from nooch_village.cockpit2_util import _nav
    h = _nav()
    assert "<div class='ovl' id='c2-palet' hidden role='dialog' aria-modal='true'" in h
    for stuk in ("ovl-box ovl-box--palet", "data-palet-dicht", "for='gs-input'",
                 "placeholder='Go to, or create"):
        assert stuk in h, stuk


def test_het_palet_draagt_geen_ovl_x_zodat_de_andere_overlays_blijven_sluiten():
    """Bord, werkoverleg en wizard pakken `document.querySelector('.ovl-x')`: het EERSTE kruisje in
    het document. Het palet staat in de chrome vóór de pagina; met een eigen `.ovl-x` zou dat van
    hen worden en ging hun overlay niet meer dicht."""
    from nooch_village.cockpit2_util import _nav
    assert "ovl-x" not in _nav()


def test_de_focus_trap_is_herbruikbaar_en_het_werkoverleg_blijft_ongemoeid():
    import pathlib
    js = (pathlib.Path(cockpit2.__file__).parent / "static" / "nooch.js").read_text(encoding="utf-8")
    assert "NV.focusTrap = function (box, terug)" in js
    assert js.count("NV.focusTrap(") == 2                     # de definitie en het palet
    assert "__ovlWireForms" in js                             # de overlay-afhandeling bestaat nog


# ── het gedrag in een echte browser ─────────────────────────────────────────────────────────

def test_toetsen_en_focus_in_een_echte_browser(server):
    sync_api = pytest.importorskip("playwright.sync_api")
    dd, sessies, poort = server
    basis = f"http://127.0.0.1:{poort}"
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:                               # Chromium niet geïnstalleerd
            pytest.skip(f"geen Chromium: {e}")
        ctx = browser.new_context(viewport={"width": 1300, "height": 900})
        ctx.add_cookies([{"name": "nv_session", "value": sessies.create(STEFAN), "url": basis}])
        pg = ctx.new_page()
        pg.goto(basis + "/projects")
        pal = pg.locator("#c2-palet")
        # `/` vanuit de pagina opent het palet, met de focus in het veld
        pg.keyboard.press("/")
        pal.wait_for(state="visible")
        assert pg.evaluate("document.activeElement.id") == "gs-input"
        pg.wait_for_selector("#gs-drop a.gs-hit")
        # pijltje omlaag: de eerste treffer
        pg.keyboard.press("ArrowDown")
        assert pg.evaluate("document.activeElement.classList.contains('gs-hit')")
        # Tab blijft binnen het palet (focus-trap), ook vele keren achter elkaar
        for _ in range(30):
            pg.keyboard.press("Tab")
            assert pg.evaluate("!!document.activeElement.closest('#c2-palet')")
        # Esc sluit, en de focus gaat terug naar de zoekknop
        pg.keyboard.press("Escape")
        pal.wait_for(state="hidden")
        assert pg.evaluate("document.activeElement.id") == "c2-zoek"
        # `/` in een invoerveld doet niets
        pg.goto(basis + "/search")
        pg.click("#zoek-q")
        pg.keyboard.press("/")
        assert pal.is_hidden() and pg.input_value("#zoek-q").endswith("/")
        # een klik op de zoekknop opent hem ook
        pg.click("#c2-zoek")
        pal.wait_for(state="visible")
        browser.close()
