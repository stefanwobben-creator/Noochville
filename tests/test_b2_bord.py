"""B2: het bord (12 oktober 2026, prototype v2).

De compacte kaart (titel, metaregel, dunne balk; het status-vakje met zijn bestaande
tegenspraak-logica), de lege kolom als smalle strook (naam en aantal, sleepdoel, toetsenbord), de
zoekknop naast de hamburger op een telefoon, en geen horizontale scroll op 390px voor /projects en
/open-questions. Het gedrag in Chromium; zonder playwright of Chromium slaat dat deel over.
"""
from __future__ import annotations

import pathlib
import re
import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import cockpit2
from nooch_village.views import projects as P

CSS = (pathlib.Path(cockpit2.__file__).parent / "static" / "nooch.css").read_text(encoding="utf-8")
ROL = "mother_earth__nooch__financial_controller"


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    lid = st.people.add("Lotte Mulder", "lotte@nooch.earth")
    st.assign.assign(ROL, "person", lid.id)
    doel = st.doelen.add("Zandloperdoel")
    pid = st.projects.create(ROL, "Een project met een doel en een deadline", "human", person=lid.id)
    st.projects.set_doel(pid, doel["id"])
    st.projects.set_due(pid, "2026-11-30")
    return dd, pid


def _kaart(dd, pid, csrf="T"):
    st = cockpit2._Stores(dd)
    return P._proj_card(st, st.projects.get(pid), csrf, "/projects")


# ── de compacte kaart ───────────────────────────────────────────────────────

def test_de_kaart_heeft_titel_metaregel_en_balk_en_geen_doel_etiket(dorp):
    dd, pid = dorp
    k = _kaart(dd, pid)
    assert "Een project met een doel en een deadline" in k
    assert "chip doel" not in k and "Zandloperdoel" not in k          # besluit: doel-etiket weg
    meta = re.search(r"<div class='muted pmeta'>(.*?)</div>", k).group(1)
    assert "aria-label='Lotte Mulder'" in meta and ">LM<" in meta     # initialen, naam in aria-label
    assert "due" in meta                                               # de deadline staat in de metaregel
    assert k.index("pmeta") < k.index("pbadge") if "pbadge" in k else True


def test_het_status_vakje_komt_alleen_uit_de_bestaande_tegenspraak_logica(dorp, monkeypatch):
    """De kaart zet geen eigen status-vakje: wat `_kaart_status` geeft, staat erop, en anders niets.
    De voorwaarden (allemaal tegelijk): status in `_ACTIEF_STATUSSEN`, er staat nog een stap open, de
    eigenaar is een rol (geen individueel initiatief), en `governance.wordt_opgepakt` zegt nee."""
    dd, pid = dorp
    monkeypatch.setattr(P, "_kaart_status", lambda st, p: "<span class='pstatus x'>MERK</span>")
    assert "MERK" in _kaart(dd, pid)
    monkeypatch.setattr(P, "_kaart_status", lambda st, p: "")
    assert "pstatus" not in _kaart(dd, pid)


def test_het_sleep_hintje_blijft_maar_kost_geen_hoogte(dorp):
    dd, pid = dorp
    assert "pcard-hint" in _kaart(dd, pid)                             # verplaatsen blijft vindbaar
    assert "pcard-hint" not in _kaart(dd, pid, csrf="")                # zonder sleep-JS geen belofte
    regel = re.search(r":root \.pcol \.pcard \.pcard-hint \{([^}]*)\}", CSS).group(1)
    assert "position: absolute" in regel


def test_de_titel_stopt_na_twee_regels_en_staat_volledig_in_title_en_op_de_projectpagina(dorp):
    dd, _pid = dorp
    st = cockpit2._Stores(dd)
    lang = "Een heel lange projecttitel " * 8 + "met het einde HIER"
    pid = st.projects.create(ROL, lang.strip(), "human")
    k = _kaart(dd, pid)
    kop = re.search(r"<div class='ptitle' title='([^']*)'>", k)
    assert kop and kop.group(1) == lang.strip()                       # volledig in title
    regel = re.search(r":root \.pcol \.pcard \.ptitle \{([^}]*)\}", CSS).group(1)
    assert "-webkit-line-clamp: 2" in regel and "overflow: hidden" in regel
    pagina = P.render_project(cockpit2._Stores(dd), pid, csrf_token="T", username="guest")
    assert "met het einde HIER" in pagina                             # en volledig op de projectpagina


# ── de lege kolom ───────────────────────────────────────────────────────────

def test_een_lege_kolom_is_een_strook_met_naam_aantal_en_toetsenbord(dorp):
    dd, pid = dorp
    st = cockpit2._Stores(dd)
    html = P._columns_html(st, [st.projects.get(pid)], ROL, "", "T", "/projects", quickadd=True)
    kolommen = re.findall(r"<div class='pcol' data-to='(\w+)'([^>]*)>", html)
    leeg = [(k, a) for k, a in kolommen if "data-leeg" in a]
    vol = [(k, a) for k, a in kolommen if "data-leeg" not in a]
    assert len(leeg) == 3 and len(vol) == 1
    for key, attrs in leeg:
        assert "tabindex='0'" in attrs and "role='group'" in attrs
        assert re.search(r"aria-label='[^']+, 0 projects'", attrs)
    # de strook houdt zijn "+ add project" (Done heeft er geen, ook niet als hij vol is)
    for key, _a in leeg:
        blok = html.split(f"data-to='{key}'", 1)[1].split("<div class='pcol'", 1)[0]
        assert ("+ add project" in blok) is (key != "done"), key


def test_de_strook_blijft_een_sleepdoel_dat_oplicht_tijdens_het_slepen():
    assert "body:has(.pdrag-ghost) .pcol[data-leeg]" in CSS
    assert re.search(r":root \.pcol\[data-leeg\]:focus-visible \{[^}]*outline", CSS)


# ── de zoekknop naast de hamburger ──────────────────────────────────────────

def test_de_mobiele_zoekknop():
    from nooch_village.cockpit2_util import _nav
    h = _nav()
    knop = re.search(r"<a class='c2-burger c2-burger--zoek'[^>]*>", h).group(0)
    assert "href='/search'" in knop and "data-palet-open" in knop and "aria-label='Search or jump to'" in knop
    regel = re.search(r"\.c2-burger--zoek \{([^}]*)\}", CSS).group(1)
    assert "width: 44px" in regel and "height: 44px" in regel


# ── in een echte browser ────────────────────────────────────────────────────

def test_390px_geen_horizontale_scroll_niets_afgedekt_en_het_palet_opent(dorp):
    sync_api = pytest.importorskip("playwright.sync_api")
    dd, _pid = dorp
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))   # guest: alles zichtbaar
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    basis = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"geen Chromium: {e}")
            pg = browser.new_page(viewport={"width": 390, "height": 844})
            for pad in ("/projects", "/open-questions"):
                pg.goto(basis + pad)
                breed, scherm = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
                assert breed <= scherm, f"{pad}: {breed}px op {scherm}px"
                # de twee knoppen linksboven dekken de kop niet af
                onder = pg.evaluate("Math.max(...[...document.querySelectorAll('.c2-burger')].map(b=>b.getBoundingClientRect().bottom))")
                kop = pg.evaluate("document.querySelector('.c2-main h1').getBoundingClientRect().top")
                assert kop >= onder, (pad, kop, onder)
                maten = pg.evaluate("[...document.querySelectorAll('.c2-burger')].map(b=>[b.offsetWidth,b.offsetHeight])")
                assert all(w >= 44 and h >= 44 for w, h in maten), maten
            pg.goto(basis + "/projects")
            pg.click(".c2-burger--zoek")
            pg.locator("#c2-palet").wait_for(state="visible")
            assert pg.evaluate("document.activeElement.id") == "gs-input"
            pg.keyboard.press("Escape")
            assert pg.evaluate("document.activeElement.classList.contains('c2-burger--zoek')")
            browser.close()
    finally:
        httpd.shutdown()
