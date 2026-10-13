"""Bord-uitlijning (13 oktober 2026): het bord is een vast raster.

Besluit Stefan:
  - elke status staat in elke lane op dezelfde plek en met dezelfde breedte;
  - een lege kolom is een lage balk van ca. 36px met de naam horizontaal, op zijn eigen plek;
  - hij blijft een sleepdoel en bereikbaar met het toetsenbord;
  - "+ add project" in een scrollende kolom ligt niet meer tegen de laatste kaart aan.

Statisch (CSS en markup) plus één meting in Chromium die overslaat als er geen Chromium is.
"""
from __future__ import annotations

import re
import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import cockpit2
from nooch_village.views.projects import _PROJ_COLS
from tests.test_b3_lijn import _regel

ROL_A = "mother_earth__nooch__creator_of_shoes"


def test_het_bord_is_een_raster_van_vier_vaste_sporen():
    r = _regel(":root .pboard")
    assert "display: grid" in r
    assert f"grid-template-columns: repeat({len(_PROJ_COLS)}, minmax(160px, 1fr))" in r
    assert "align-items: start" in r and "overflow-x: auto" in r


def test_een_lege_kolom_is_een_lage_horizontale_balk():
    r = _regel(":root .pcol[data-leeg]")
    assert "min-height: 36px" in r and "flex-direction: row" in r
    # niet meer de smalle verticale strook (B2): geen eigen breedte, geen gedraaide kop
    assert "flex: 0 0" not in r and "min-width" not in r
    assert "writing-mode" not in _regel(":root .pcol[data-leeg] .pcol-h")


def test_ruimte_tussen_de_laatste_kaart_en_add_project():
    assert "margin-top: var(--s2)" in _regel(":root .pcol > .addlink")


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rollen = [r.id for r in st.records.all() if r.id.startswith("mother_earth__nooch__")][:2]
    # lane 1: alleen Active; lane 2: Active, Waiting en Future — zo verschilt per lane welke leeg is
    st.projects.create(rollen[0], "Kaart in lane een", "human", status="running")
    st.projects.create(rollen[1], "Kaart running", "human", status="running")
    st.projects.create(rollen[1], "Kaart future", "human", status="future")
    st.projects.block(st.projects.create(rollen[1], "Kaart blocked", "human", status="running"), rollen[0])
    return dd


def _html(dd):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_elke_lane_heeft_alle_vier_kolommen_in_vaste_volgorde_en_lege_blijven_bereikbaar(dorp):
    import http.client
    httpd = _html(dorp)
    try:
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=20)
        c.request("GET", "/projects")
        html = c.getresponse().read().decode()
    finally:
        httpd.shutdown()
    lanes = html.split("<div class='swim'>")[1:]
    assert len(lanes) >= 2
    for lane in lanes:
        kolommen = re.findall(r"<div class='pcol' data-to='(\w+)'([^>]*)>", lane)
        assert [k for k, _a in kolommen] == [key for _l, key, _s in _PROJ_COLS]
        for _k, attrs in kolommen:
            if "data-leeg" in attrs:                       # sleepdoel (data-to) + toetsenbord
                assert "tabindex='0'" in attrs and "aria-label=" in attrs


def test_in_chromium_staat_elke_status_op_dezelfde_plek(dorp):
    sync_api = pytest.importorskip("playwright.sync_api")
    httpd = _html(dorp)
    basis = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:                         # noqa: BLE001
                pytest.skip(f"geen Chromium: {e}")
            for breedte in (1300, 390):
                pg = browser.new_page(viewport={"width": breedte, "height": 900})
                pg.goto(basis + "/projects")
                meting = pg.evaluate("""() => {
                  const pos = {}, lege = [];
                  for (const c of document.querySelectorAll('.swim .pcol')) {
                    const b = c.getBoundingClientRect();
                    (pos[c.dataset.to] = pos[c.dataset.to] || new Set()).add(Math.round(b.left) + '/' + Math.round(b.width));
                    if (c.hasAttribute('data-leeg')) lege.push(Math.round(b.height));
                  }
                  return {plekken: Object.fromEntries(Object.entries(pos).map(([k, v]) => [k, v.size])), lege,
                          pagina: document.documentElement.scrollWidth};
                }""")
                assert set(meting["plekken"].values()) == {1}, (breedte, meting)
                assert meting["lege"] and all(30 <= h <= 40 for h in meting["lege"]), (breedte, meting)
                assert meting["pagina"] == breedte, (breedte, meting)      # het bord scrollt, niet de pagina
                pg.close()
            browser.close()
    finally:
        httpd.shutdown()
