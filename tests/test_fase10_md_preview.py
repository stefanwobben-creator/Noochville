"""Punt 4b — de voorbeeld-knop naast de editor-werkbalk.

Het probleem: zodra het inline formulier openstaat zie je `**vet**` als `**vet**`, en op een lange
wiki-pagina bewerk je dus een hele pagina in broncode.

De keuze die deze tests bewaken is niet de knop maar **waar de weergave vandaan komt**: van de
server, via `_md`, en niet van een markdown-parser in JavaScript. Een tweede renderer loopt uiteen
zodra er één opmaakregel bij komt — `reference, don't copy` — en zou bovendien het escapen opnieuw
goed moeten doen.
"""
from __future__ import annotations

import pathlib
import re
import secrets
import tempfile
import threading
import time
import socketserver
import urllib.parse
import urllib.request

import pytest

from nooch_village import cockpit2
from nooch_village.cockpit2_util import md_editor

REPO = pathlib.Path(__file__).resolve().parents[1]
JS = (REPO / "nooch_village" / "static" / "nooch.js").read_text()


def test_de_weergave_komt_van_de_server_en_niet_uit_een_tweede_parser():
    """Structureel: de JS mag wél `/md-preview` aanroepen, maar geen eigen opmaak-regels dragen."""
    assert "/md-preview" in JS
    blok = re.search(r"function mdPreview\(root\)\s*\{(.*?)\n  \}", JS, re.S)
    assert blok, "mdPreview is niet te vinden"
    # Geen markdown-syntax in de JS: dat zou het begin van een tweede renderer zijn.
    for syntax in ("**", "~~", "## ", "replace(/"):
        assert syntax not in blok.group(1), f"opmaak-logica in JS: {syntax!r}"


def test_de_knop_zit_in_elke_editor():
    html = md_editor("body", "**vet**")
    assert "data-md-preview" in html          # de editor is als container herkenbaar
    assert "data-md-toggle" in html           # de knop
    assert "editor-prev" in html              # het vak waar de weergave in komt
    assert "<textarea" in html                # en het tekstvak blijft gewoon bestaan


def _server():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    csrf = secrets.token_hex(8)
    httpd = socketserver.ThreadingTCPServer(
        ("127.0.0.1", 0), cockpit2.make_handler(dd, csrf, None, None))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(.3)
    return httpd, csrf, httpd.server_address[1]


def _post(poort, velden):
    data = urllib.parse.urlencode(velden).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{poort}/md-preview", data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_het_voorbeeld_is_precies_wat_md_ervan_maakt():
    """Niet "lijkt erop": letterlijk dezelfde uitvoer als de renderer die ook opslaat."""
    from nooch_village.cockpit2_util import _md
    httpd, csrf, poort = _server()
    try:
        tekst = "## Kop\n- een\n- twee\n\n**vet** en *cursief*"
        code, html = _post(poort, {"csrf": csrf, "tekst": tekst})
        assert code == 200
        assert _md(tekst) in html
    finally:
        httpd.shutdown()


def test_zonder_csrf_geen_voorbeeld():
    """Hij schrijft niets, maar hij is wel een endpoint dat willekeurige tekst terugkaatst.
    Fail-closed, zelfde regel als de wizard-endpoints ernaast."""
    httpd, _csrf, poort = _server()
    try:
        code, _ = _post(poort, {"csrf": "fout", "tekst": "x"})
        assert code == 403
    finally:
        httpd.shutdown()


def test_het_opslagmodel_is_niet_aangeraakt():
    """Besluit: "zonder het opslagmodel aan te raken". De preview-tak mag geen store kennen."""
    src = pathlib.Path(cockpit2.__file__).read_text()
    blok = re.search(r'if path == "/md-preview":(.*?)\n            # ──', src, re.S)
    assert blok, "de /md-preview-tak is niet te vinden"
    for verboden in ("_Stores(", ".update(", ".add(", "st."):
        assert verboden not in blok.group(1), f"de preview raakt opslag aan: {verboden!r}"
