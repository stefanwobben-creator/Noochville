"""Bord-uitlijning (13 oktober 2026): het bord is een vast raster met één kolomkop (ontwerp B).

Besluit Stefan (variant B):
  - één kolomkop-rij bovenaan het bord: statusvorm, woord en het totaal over alle zichtbare lanes;
    sticky, en in DEZELFDE scrollcontainer als de lanes zodat hij op 390px meescrolt;
  - elke lane: vier vaste kolommen op dezelfde x-positie en breedte als de kop;
  - een lege kolom: geen balk, geen label, geen tint — een stille stippellijn (1px dotted --hair),
    zwart tijdens het slepen, bereikbaar met Tab ("Active, 0 projects"), "+" alleen bij hover of focus;
  - "+ add project" in een scrollende kolom ligt niet meer tegen de laatste kaart aan.

Statisch (CSS en markup) plus één meting in Chromium die overslaat als er geen Chromium is.
"""
from __future__ import annotations

import re
import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import cockpit2
from tests.test_b3_lijn import CSS
from nooch_village.views.projects import _PROJ_COLS
from tests.test_b3_lijn import _regel

ROL_A = "mother_earth__nooch__creator_of_shoes"


def test_het_bord_is_een_raster_van_vier_vaste_sporen():
    r = _regel(":root .pboard")
    assert "display: grid" in r
    assert f"grid-template-columns: repeat({len(_PROJ_COLS)}, minmax(160px, 1fr))" in r
    assert "align-items: start" in r
    assert "overflow: visible" in r                    # niet per lane scrollen: het bord als geheel


def test_kop_en_lanes_delen_een_scrollcontainer_en_de_kop_plakt():
    assert "position: sticky" in _regel(":root [data-kop]") and "top: 0" in _regel(":root [data-kop]")
    bord = _regel(":root [data-bord]")
    assert "overflow: auto" in bord and "max-height" in bord
    # vanaf 1000px past het bord: dan geen eigen scrollvlak, en plakt de kop tegen de pagina
    assert re.search(r"@media \(min-width: 1000px\) \{ :root \[data-bord\] \{ overflow: visible; max-height: none; \} \}", CSS)
    assert "overscroll-behavior" not in bord           # anders scroll je er op een telefoon niet meer uit
    assert "position: sticky" in _regel(":root [data-bord] .swim-h")


def test_een_lege_kolom_is_een_stille_stippellijn():
    r = _regel(":root .pcol[data-leeg]")
    assert "border: 1px dotted var(--hair)" in r and "min-height: 32px" in r
    # 13 oktober: dezelfde tint als zijn status (geen eigen achtergrond) en mee tot de hoogte van de lane
    assert "background" not in r and "align-self: stretch" in r
    assert "background" not in _regel(":root body:has(.pdrag-ghost) .pcol[data-leeg]")
    assert "display: none" in _regel(":root .pcol[data-leeg] .pcol-h")          # geen label
    assert "opacity: 0" in _regel(":root .pcol[data-leeg] .addlink")             # "+" niet als ruis
    assert "opacity: 1" in _regel(":root .pcol[data-leeg]:hover .addlink")
    assert "opacity: 1" in _regel(":root .pcol[data-leeg]:focus-within .addlink")
    assert "border-color: var(--nu-text)" in _regel(":root body:has(.pdrag-ghost) .pcol[data-leeg]")
    assert "outline" in _regel(":root .pcol[data-leeg]:focus-visible")


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
    # ook een Done in lane 2: zo staat elke status ergens gevuld en ergens leeg (tintvergelijking)
    st.projects.complete(st.projects.create(rollen[1], "Kaart done", "human", status="running"))
    return dd


def _html(dd):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_een_kop_rij_en_vier_kolommen_per_lane_en_lege_blijven_bereikbaar(dorp):
    import http.client
    httpd = _html(dorp)
    try:
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=20)
        c.request("GET", "/projects")
        html = c.getresponse().read().decode()
    finally:
        httpd.shutdown()
    bord = html.split("<div data-bord>", 1)[1]
    kop = re.search(r"<div class='pboard' data-kop>(.*?)</div></div>", bord).group(1)
    cellen = re.findall(r"<div class='pcol-h' data-to='(\w+)'>[^<(]+\((\d+)\)</div>", kop + "</div>")
    assert [k for k, _n in cellen] == [key for _l, key, _s in _PROJ_COLS]
    assert sum(int(n) for _k, n in cellen) == 5                  # het totaal over alle zichtbare lanes
    lanes = bord.split("<div class='swim'>")[1:]
    assert len(lanes) >= 2
    for lane in lanes:
        kolommen = re.findall(r"<div class='pcol' data-to='(\w+)'([^>]*)>", lane)
        assert [k for k, _a in kolommen] == [key for _l, key, _s in _PROJ_COLS]
        for _k, attrs in kolommen:
            if "data-leeg" in attrs:                       # sleepdoel (data-to) + toetsenbord + naam
                assert "tabindex='0'" in attrs and re.search(r"aria-label='\w+, 0 projects'", attrs)


def test_in_chromium_staat_elke_status_onder_zijn_kopcel(dorp):
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
                  const kop = {};
                  for (const h of document.querySelectorAll('[data-kop] .pcol-h')) {
                    const b = h.getBoundingClientRect(); kop[h.dataset.to] = [Math.round(b.left), Math.round(b.width)];
                  }
                  const vol = {};
                  for (const c of document.querySelectorAll('.swim .pcol:not([data-leeg])'))
                    vol[c.dataset.to] = getComputedStyle(c).backgroundColor;
                  const afwijkend = [], lege = [], tint = [];
                  for (const s of document.querySelectorAll('.swim')) {
                    const lane = s.querySelector('.pboard').getBoundingClientRect();
                    for (const c of s.querySelectorAll('.pcol')) {
                      const b = c.getBoundingClientRect(), k = kop[c.dataset.to];
                      if (!k || Math.abs(k[0] - Math.round(b.left)) > 1 || Math.abs(k[1] - Math.round(b.width)) > 1)
                        afwijkend.push(c.dataset.to);
                      if (c.hasAttribute('data-leeg')) {
                        lege.push([Math.round(b.height), Math.round(Math.max(32, lane.height))]);
                        tint.push([c.dataset.to, getComputedStyle(c).backgroundColor, vol[c.dataset.to] || null]);
                      }
                    }
                  }
                  return {kop: Object.keys(kop).length, afwijkend, lege, tint, pagina: document.documentElement.scrollWidth};
                }""")
                assert meting["kop"] == len(_PROJ_COLS), (breedte, meting)
                assert meting["afwijkend"] == [], (breedte, meting)          # elke cel onder zijn kopcel
                # een lege cel is even hoog als zijn lane (minimaal 32px) ...
                assert meting["lege"] and all(abs(h - lane) <= 1 for h, lane in meting["lege"]), (breedte, meting)
                # ... en heeft dezelfde achtergrond als een gevulde kolom van dezelfde status
                vergeleken = [t for t in meting["tint"] if t[2] is not None]
                assert len(vergeleken) == len(meting["tint"]), (breedte, meting)   # elke status had een gevulde
                assert all(eigen == gevuld for _s, eigen, gevuld in vergeleken), (breedte, meting)
                assert meting["pagina"] == breedte, (breedte, meting)      # het bord scrollt, niet de pagina
                pg.close()
            browser.close()
    finally:
        httpd.shutdown()


def test_op_390_valt_de_kop_niet_onder_de_menu_en_zoekknop(tmp_path):
    """Besluit 13 oktober: op een telefoon mag de kolomkop niet onder de vaste menu- en zoekknop
    liggen — in beginstand en na 200px verticaal scrollen binnen het bord. Gemeten als het snijvlak
    van de bounding boxes."""
    sync_api = pytest.importorskip("playwright.sync_api")
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rollen = [r.id for r in st.records.all() if r.id.startswith("mother_earth__nooch__")][:8]
    for i, rol in enumerate(rollen):                   # genoeg lanes om het bord echt te laten scrollen
        for j in range(3):
            st.projects.create(rol, f"Kaart {i}-{j}", "human", status="future")
    httpd = _html(dd)
    basis = f"http://127.0.0.1:{httpd.server_address[1]}"
    meet = """() => {
      const k = document.querySelector('[data-kop]').getBoundingClientRect();
      const knoppen = [...document.querySelectorAll('.c2-burger')].filter(e => e.checkVisibility());
      const snij = knoppen.map(e => { const b = e.getBoundingClientRect();
        return Math.max(0, Math.min(k.right, b.right) - Math.max(k.left, b.left))
             * Math.max(0, Math.min(k.bottom, b.bottom) - Math.max(k.top, b.top)); });
      return {knoppen: knoppen.length, snij, bord: Math.round(document.querySelector('[data-bord]').scrollTop)};
    }"""
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:                         # noqa: BLE001
                pytest.skip(f"geen Chromium: {e}")
            pg = browser.new_page(viewport={"width": 390, "height": 844})
            pg.goto(basis + "/projects")
            begin = pg.evaluate(meet)
            assert begin["knoppen"] == 2, begin              # anders meet deze toets niets
            assert begin["snij"] == [0, 0], begin
            pg.evaluate("document.querySelector('[data-bord]').scrollTop = 200")
            gescrold = pg.evaluate(meet)
            assert gescrold["bord"] == 200, gescrold          # het bord scrolde echt
            assert gescrold["snij"] == [0, 0], gescrold
            browser.close()
    finally:
        httpd.shutdown()
