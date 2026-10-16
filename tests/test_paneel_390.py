"""Het "+ Add fact"-paneel en het checkformulier op 390 px (16 oktober 2026).

`.datepop` stond absoluut onder zijn knop; op een telefoon werd de pagina daardoor breder dan het
scherm zodra je het paneel opende (Full Green, "Dyes & chemicals": 477 px). Op een smal scherm staat
het paneel nu in de stroom. Gemeten in Chromium; slaat over zonder Chromium.
"""
from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import cockpit2

from tests.test_w1_antwoorden import _feit, _pagina


def test_open_panelen_op_390_maken_de_pagina_niet_breder(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    dd, aid = _pagina(tmp_path, [_feit("F1", "Self-reported: 30% PLA fibre made from maize")])
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:                         # noqa: BLE001
                pytest.skip(f"geen Chromium: {e}")
            pg = browser.new_page(viewport={"width": 390, "height": 844})
            pg.goto(f"http://127.0.0.1:{httpd.server_address[1]}/pagina?id={aid}")
            breedte = "document.documentElement.scrollWidth"
            assert pg.evaluate(breedte) == 390
            # "+ Add fact" bij een open vraag zonder feiten (staat rechts in de regel)
            pg.locator("#vraag-chem summary", has_text="+ Add fact").first.click()
            assert pg.evaluate("document.querySelector('#vraag-chem details[open] .datepop') !== null")
            assert pg.evaluate(breedte) == 390
            # het checkformulier van een feit
            pg.locator("#feit-F1 summary.btn.sm").first.click()
            assert pg.evaluate("document.querySelector('#feit-F1 details[open] .datepop') !== null")
            assert pg.evaluate(breedte) == 390
            browser.close()
    finally:
        httpd.shutdown()
