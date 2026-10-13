"""/bom op een telefoon (B3 fase e, commit 2, 13 oktober 2026).

Op 390px maakte de stuklijst de hele pagina 797px breed. Elke brede tabel staat nu in zijn eigen
scrollcontainer (`.c2-scroll`), op een pagina met `c2-main--vol` — hetzelfde patroon als Finance
(#718). Statisch (markup) plus één meting in Chromium die overslaat als er geen Chromium is.
"""
from __future__ import annotations

import re
import threading
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import cockpit2


@pytest.fixture
def dd(tmp_path):
    pad = str(tmp_path / "poc")
    cockpit2._bootstrap(pad)
    return pad


def _server(dd):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_elke_tabel_op_bom_staat_in_een_eigen_scrollcontainer(dd):
    from nooch_village.views.bom import render_bom
    html = render_bom(cockpit2._Stores(dd), csrf_token="T", username="guest")
    assert "class='c2-main c2-main--vol'" in html
    tabellen = len(re.findall(r"<table class='mtab'", html))
    assert tabellen >= 1
    assert len(re.findall(r"<div class='c2-scroll'><table class='mtab'", html)) == tabellen


def test_op_390_wordt_de_pagina_niet_breder_dan_het_scherm(dd):
    sync_api = pytest.importorskip("playwright.sync_api")
    httpd = _server(dd)
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:                         # noqa: BLE001
                pytest.skip(f"geen Chromium: {e}")
            pg = browser.new_page(viewport={"width": 390, "height": 844})
            pg.goto(f"http://127.0.0.1:{httpd.server_address[1]}/bom")
            assert pg.locator("table.mtab").count() >= 1
            assert pg.evaluate("document.documentElement.scrollWidth") == 390
            browser.close()
    finally:
        httpd.shutdown()
