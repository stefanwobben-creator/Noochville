"""Herontwerp A van de wiki-vragen (besluit Stefan, 16 oktober 2026).

- Elke vraag is één `<details>`; de `<summary>` is de tabelrij (vraag · antwoord · bewijs · aantal
  feiten) op één vast raster met de kolomkop: de status staat één keer op de pagina.
- Open, ongecheckt en conflict staan open; beantwoord en uitgesteld dicht (kop met antwoord,
  bewijs, aantal en bij uitgesteld de datum).
- Na een actie (Check, Re-check, Add fact, Edit, Undo, Remove) blijft de aangeraakte vraag open:
  elk formulier stuurt terug naar `#vraag-<k>`, en de redirect houdt het anker achter de melding.
- `#feit-<id>` opent ook de vraag eromheen. Enter/Spatie op een kop opent en sluit.
- De metakolom zakt vanzelf onder de tekst als de tekstkolom te smal wordt (geen media query).
"""
from __future__ import annotations

import re
import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import cockpit2, wiki
from nooch_village.views.wiki import render_pagina

from tests.test_w1_antwoorden import _check, _feit, _pagina


def _html(dd, aid, csrf="t"):
    return render_pagina(cockpit2._Stores(dd), aid, csrf_token=csrf, username="guest")


def _blok(h, k):
    return h.split(f"id='vraag-{k}'", 1)[1].split(" id='vraag-", 1)[0]


@pytest.fixture
def dorp(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "Self-reported: 30% PLA fibre"),
                                 _feit("F2", "A lab says it is not biobased"),
                                 _feit("F3", "Unclear brochure about certificates"),
                                 _feit("F4", "Weight per m2", gezien={"door": "S", "op": "2026-10-06",
                                                                     "achtergrond": True}),
                                 _feit("F5", "Loose note")])
    _check(dd, aid, "F1", plastic="yes", biobased="yes")
    _check(dd, aid, "F2", biobased="no")
    st = cockpit2._Stores(dd)
    cl = st.att.get(aid)
    meta = dict(cl.meta)
    meta["feiten"] = [dict(f, sectie="Certificate") if f["id"] == "F3" else f for f in meta["feiten"]]
    st.att.update(aid, meta=meta)
    cockpit2.dispatch(dd, "vraag_uitstel", {"aid": [aid], "soort": ["materiaal"], "k": ["water"],
                                            "tot": ["2026-12-01"], "next": ["/"]}, username="guest")
    return dd, aid


def test_een_kop_per_vraag_met_de_vier_kolommen_en_de_status_een_keer(dorp):
    dd, aid = dorp
    h = _html(dd, aid)
    assert h.count("<div class='wv-kop'><span class='muted'>Question</span>") == 1
    kop = _blok(h, "plastic").split("</summary>", 1)[0]
    assert "<strong>Contains plastic?</strong>" in kop and "Checked: yes</span>" in kop
    assert "<span class='muted'>self-reported</span>" in kop and "1 fact</span>" in kop
    # de status staat alleen in de kop: geen tweede statusregel in het blok
    assert _blok(h, "plastic").count("nu-status nu-status--") == 1


def test_open_ongecheckt_conflict_open_beantwoord_en_uitgesteld_dicht(dorp):
    dd, aid = dorp
    h = _html(dd, aid)
    def is_open(k):
        return re.search(rf"<details class='wiki-inline wv-vraag' id='vraag-{k}'( open)?>", h).group(1) == " open"
    assert is_open("chem")                                  # open zonder feit
    assert is_open("biobased")                              # conflict
    assert not is_open("plastic")                           # beantwoord
    assert not is_open("water")                             # uitgesteld
    assert "Deferred · research by 2026-12-01" in _blok(h, "water").split("</summary>", 1)[0]


def test_background_dicht_met_teller_en_feiten_zonder_vraag_open(dorp):
    dd, aid = dorp
    h = _html(dd, aid)
    assert "<details class='wiki-inline wv-vraag' id='vraag-achtergrond'>" in h
    assert "<strong>Background facts</strong>" in h and "id='feit-F4'" in h.split("id='vraag-achtergrond'", 1)[1]
    assert "<details class='wiki-inline wv-vraag' id='vraag-overig' open>" in h
    assert "id='feit-F5'" in h.split("id='vraag-overig'", 1)[1].split("id='vraag-achtergrond'", 1)[0]


def test_elk_formulier_van_een_feit_stuurt_terug_naar_zijn_vraag(dorp):
    dd, aid = dorp
    b = _blok(_html(dd, aid), "plastic")
    terug = f"{wiki.pagina_url(aid)}#vraag-plastic"
    acties = re.findall(r"name='next' value='([^']*)'><button class='[^']*' type='submit' name='action' value='(\w+)'", b)
    assert {a for _n, a in acties} >= {"pagina_feit_gezien", "pagina_feit_del"}            # Undo + Remove
    assert all(n == terug for n, _a in acties)
    assert b.count(f"name='next' value='{terug}'") >= 4      # + checkformulier, bewerkformulier, add fact


def test_de_redirect_houdt_het_anker_achter_de_melding(dorp):
    dd, aid = dorp
    import http.client, urllib.parse
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        body = urllib.parse.urlencode({"csrf": "T", "action": "pagina_feit_gezien", "aid": aid, "fid": "F1",
                                       "uit": "1", "next": f"/pagina?id={aid}#vraag-plastic"})
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        c.request("POST", "/action", body, {"Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse(); r.read()
    finally:
        httpd.shutdown()
    plek = r.getheader("Location")
    assert re.fullmatch(rf"/pagina\?id={aid}&msg=[^#]+#vraag-plastic", plek), plek


def test_from_the_bom_staat_in_de_zijbalk(dorp):
    dd, aid = dorp
    h = _html(dd, aid)
    rail = h.split("<aside class='pkaart-rail'>", 1)[1]
    assert "From the BOM" in rail and "From the BOM" not in h.split("<aside class='pkaart-rail'>", 1)[0]


# ── in de browser ──────────────────────────────────────────────────────────────

@pytest.fixture
def browser_pagina(dorp):
    sync_api = pytest.importorskip("playwright.sync_api")
    dd, aid = dorp
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:                                # noqa: BLE001
            httpd.shutdown()
            pytest.skip(f"geen Chromium: {e}")
        yield browser, f"http://127.0.0.1:{httpd.server_address[1]}", aid
        browser.close()
    httpd.shutdown()


def _open(pg, k):
    return pg.evaluate(f"document.getElementById('vraag-{k}').open")


def test_na_re_check_blijft_de_dichte_vraag_open(browser_pagina):
    """Eis 1, expliciet: Contains plastic? staat standaard dicht (beantwoord). Je opent hem, doet
    Re-check en verstuurt; na het herladen staat dezelfde vraag open."""
    browser, url, aid = browser_pagina
    pg = browser.new_page(viewport={"width": 1088, "height": 900})
    pg.goto(f"{url}/pagina?id={aid}")
    assert not _open(pg, "plastic")
    pg.locator("#vraag-plastic > summary").click()
    pg.locator("#feit-F1 .wv-meta summary.flink", has_text=re.compile("^Re-check$")).click()
    with pg.expect_navigation():
        pg.locator("#feit-F1 details[open] button[value=pagina_feit_gezien]").first.click()
    assert "#vraag-plastic" in pg.url and "msg=" in pg.url
    assert _open(pg, "plastic")


def test_na_undo_en_add_fact_blijft_de_vraag_open(browser_pagina):
    browser, url, aid = browser_pagina
    pg = browser.new_page(viewport={"width": 1088, "height": 900})
    pg.goto(f"{url}/pagina?id={aid}")
    pg.locator("#vraag-plastic > summary").click()
    pg.locator("#feit-F1 summary[aria-label='More actions']").click()
    with pg.expect_navigation():
        pg.locator("#feit-F1 button", has_text="Undo check").click()
    assert _open(pg, "plastic")
    # + Add fact bij "Dyes & chemicals"
    pg.locator("#vraag-chem summary", has_text="+ Add fact").click()
    pg.fill("#vraag-chem textarea[name=tekst]", "A new fact")
    with pg.expect_navigation():
        pg.locator("#vraag-chem button[value=pagina_feit_add]").click()
    assert "#vraag-chem" in pg.url and _open(pg, "chem")


def test_feit_anker_opent_de_vraag_eromheen(browser_pagina):
    browser, url, aid = browser_pagina
    pg = browser.new_page(viewport={"width": 1088, "height": 900})
    pg.goto(f"{url}/pagina?id={aid}#feit-F4")                     # in de dichte Background-sectie
    assert pg.evaluate("document.getElementById('vraag-achtergrond').open")


def test_enter_en_spatie_op_de_kop_openen_en_sluiten(browser_pagina):
    browser, url, aid = browser_pagina
    pg = browser.new_page(viewport={"width": 1088, "height": 900})
    pg.goto(f"{url}/pagina?id={aid}")
    pg.locator("#vraag-plastic > summary").focus()
    pg.keyboard.press("Enter")
    assert _open(pg, "plastic")
    pg.keyboard.press("Space")
    assert not _open(pg, "plastic")


def test_metakolom_naast_de_tekst_als_er_ruimte_is_anders_eronder(browser_pagina):
    """Geen media query: de feitrij beslist zelf. De inhoudskolom van een wikipagina is nu maximaal
    ±550 px, en tekst (min. 20rem) plus meta (15rem) past daar niet naast elkaar — de meta staat dan
    eronder. Is de rij breed genoeg (hier gesimuleerd op 900 px), dan staat hij ernaast."""
    browser, url, aid = browser_pagina
    for breedte, rij, naast in ((1088, None, False), (390, None, False), (1088, "900px", True)):
        pg = browser.new_page(viewport={"width": breedte, "height": 900})
        pg.goto(f"{url}/pagina?id={aid}")
        pg.locator("#vraag-plastic > summary").click()
        if rij:
            pg.evaluate(f"document.getElementById('feit-F1').style.width = '{rij}'")
        tekst = pg.locator("#feit-F1 > div").first.bounding_box()
        meta = pg.locator("#feit-F1 .wv-meta").bounding_box()
        assert (abs(meta["y"] - tekst["y"]) < 4) is naast, (breedte, rij)
        if not rij:
            assert pg.evaluate("document.documentElement.scrollWidth") == breedte
        pg.close()
